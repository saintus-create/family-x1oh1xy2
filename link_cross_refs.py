#!/usr/bin/env python3
"""
Batch-link Family Code cross-references into MDX pages.

Usage:
  python3 link_cross_refs.py [--dry-run] [--pages-dir DIR] [--json FILE]

The script reads fam_cross_references.json and modifies MDX files in place,
wrapping bare code/section mentions in <a href="..."> links where they appear
inside statute-card paragraph text.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Mapping from code abbreviation to leginfo URL builder.
CODE_URL_TEMPLATES = {
    "CCP": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum={section}.",
    "CIV": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum={section}.",
    "PEN": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=PEN&sectionNum={section}.",
    "PROB": "https://leginfo.legislature.ca.gov/faces/codes_displayexpandedbranch.xhtml?tocCode=PROB",
    "HSC": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=HSC&sectionNum={section}.",
    "VEH": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=VEH&sectionNum={section}.",
    "GOV": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum={section}.",
    "WIC": "https://leginfo.legislature.ca.gov/faces/codes_displayexpandedbranch.xhtml?tocCode=WIC",
    "USC": None,  # federal; leave as text or link externally
    "CJE": None,
    "CRC": "https://www.courts.ca.gov/rules/index.htm",
}

FULL_NAMES = {
    "CCP": "Code of Civil Procedure",
    "CIV": "Civil Code",
    "PEN": "Penal Code",
    "PROB": "Probate Code",
    "HSC": "Health and Safety Code",
    "VEH": "Vehicle Code",
    "GOV": "Government Code",
    "WIC": "Welfare and Institutions Code",
}


def build_ref_url(code: str, section: str) -> str | None:
    tmpl = CODE_URL_TEMPLATES.get(code)
    if tmpl is None:
        return None
    return tmpl.format(section=section)


def load_cross_references(path: str) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    return data.get("cross_references", [])


def extract_fam_section_number(fam_section: str) -> str:
    m = re.search(r"FAM\s*§\s*([\d\.]+)", fam_section)
    if m:
        return m.group(1)
    return fam_section


def linkify_refs(content: str, cross_refs: list[dict], page_fam_sections: set[str], dry_run: bool) -> str:
    """
    For each cross-reference whose fam_section is in this page, try to linkify
    the referenced_code + referenced_section in the text body.
    """
    # Build lookup: fam_section_text -> refs
    refs_by_fam: dict[str, list[dict]] = {}
    for ref in cross_refs:
        fam_sec = ref.get("fam_section", "")
        refs_by_fam.setdefault(fam_sec, []).append(ref)

    # For each FAM section referenced in this page, find corresponding refs
    # We'll just scan the body for the exact referenced_section text and wrap it.
    for fam_sec_label, refs in refs_by_fam.items():
        fam_num = extract_fam_section_number(fam_sec_label)
        if fam_num not in page_fam_sections:
            continue

        for ref in refs:
            code = ref.get("referenced_code", "")
            section = ref.get("referenced_section", "")
            url = ref.get("referenced_url") or build_ref_url(code, section)
            if not url:
                continue

            # Build the exact text to replace in the body.
            # We try a few patterns: bare Section N, Code § N, range mentions.
            # We only replace occurrences that are NOT already inside <a> or <Badge>.
            # Simple strategy: if the page contains the exact referenced fragment
            # in plain text (not already in a tag), wrap it in a link.
            frag = section.strip()
            # Avoid double-linking: skip if already linked.
            if f'href="{url}"' in content:
                continue

            # Replace occurrences not inside tags.
            # We use a regex negative-lookbehind/ahead for <...>, but simpler:
            # only do exact replacement on paragraph-like blocks.
            # Pattern: text that is not preceded by = or " or { or <
            pattern = re.compile(r"(?<![={\"<])(?<!href=\")(?<!</a>)\b" + re.escape(frag) + r"\b(?![}>])")

            def replacer(m):
                return f'<a href="{url}">{m.group(0)}</a>'

            new_content, n = pattern.subn(replacer, content)
            if n:
                if dry_run:
                    print(f"  [DRY-RUN] {fam_num}: would link '{frag}' ({n} occurrence(s))")
                else:
                    print(f"  Linked {fam_num}: '{frag}' ({n} occurrence(s))")
                content = new_content

    return content


def find_fam_sections_in_page(content: str) -> set[str]:
    return set(re.findall(r'<Badge intent="info" minimal>Sec\.\s*([\d\.]+)</Badge>', content))


def process_pages(pages_dir: str, json_path: str, dry_run: bool = False) -> None:
    cross_refs = load_cross_references(json_path)
    pages = sorted(Path(pages_dir).glob("*.mdx"))

    for page_path in pages:
        content = page_path.read_text()
        fam_sections = find_fam_sections_in_page(content)
        if not fam_sections:
            continue

        print(f"\nPage: {page_path.name}")
        print(f"  FAM sections present: {sorted(fam_sections)}")

        updated = linkify_refs(content, cross_refs, fam_sections, dry_run)
        if updated != content:
            if not dry_run:
                page_path.write_text(updated)
                print(f"  -> Updated.")
        else:
            print(f"  -> No changes.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Link FAM cross-references into MDX pages")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing")
    parser.add_argument("--pages-dir", default="fern/docs/pages", help="MDX pages directory")
    parser.add_argument("--json", default="fam_cross_references.json", help="Cross-references JSON file")
    args = parser.parse_args()

    base = Path("/Users/2024-jan/f/family-x1oh1xy2")
    pages_dir = base / args.pages_dir
    json_path = base / args.json

    if not pages_dir.exists():
        print(f"Pages dir not found: {pages_dir}", file=sys.stderr)
        return 1
    if not json_path.exists():
        print(f"JSON not found: {json_path}", file=sys.stderr)
        return 1

    process_pages(str(pages_dir), str(json_path), dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

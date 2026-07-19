#!/usr/bin/env python3
"""
03_extract_cross_refs.py
------------------------
Scan the extracted Family Code sections (family_code_sections.json) and build
a cross-reference index. For every section that mentions another section,
division, part, or external code (CCP, CIV, PEN, HSC, VEH, GOV, PROB, WIC),
emit a reference entry.

Output: fam_cross_references.json
  {
    "metadata": {...},
    "cross_references": [
       {"fam_section": "FAM § 65", "fam_text": "...",
        "referenced_code": "FAM", "referenced_section": "...",
        "referenced_url": "..."},
       ...
    ]
  }

Run:  python3 03_extract_cross_refs.py
"""
from __future__ import annotations
import json
import re
from pathlib import Path

REPO = Path.cwd()
SECTIONS_FILE = REPO / "family_code_sections.json"
OUT_FILE = REPO / "fam_cross_references.json"

# External code -> LegInfo URL builder
CODE_TEMPLATES = {
    "FAM": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=FAM&sectionNum={s}.",
    "CCP": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CCP&sectionNum={s}.",
    "CIV": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum={s}.",
    "PEN": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=PEN&sectionNum={s}.",
    "HSC": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=HSC&sectionNum={s}.",
    "VEH": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=VEH&sectionNum={s}.",
    "GOV": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum={s}.",
    "PROB": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=PROB&sectionNum={s}.",
    "WIC": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=WIC&sectionNum={s}.",
}

# "Section 760", "Sections 1100-1103", "Section 297.5", "Part 2", "Division 4"
SECTION_MENTION_RE = re.compile(
    r"(?:Section|Sec\.?|§)\s+(\d{1,5}(?:\.\d+)?)(?:\s*(?:to|through|[-–]|and)\s*(\d{1,5}(?:\.\d+)?))?",
    re.IGNORECASE,
)
CODE_SECTION_RE = re.compile(
    r"\b(CCP|CIV|PEN|HSC|VEH|GOV|PROB|WIC|FAM)\s+(?:Section|Sec\.?|§)\s+(\d{1,5}(?:\.\d+)?)",
    re.IGNORECASE,
)
DIVISION_RE = re.compile(r"Division\s+(\d{1,2}(?:\.\d+)?)", re.IGNORECASE)
PART_RE = re.compile(r"Part\s+(\d{1,3})", re.IGNORECASE)


def build_url(code: str, section: str) -> str | None:
    tmpl = CODE_TEMPLATES.get(code.upper())
    if not tmpl:
        return None
    return tmpl.format(s=section)


def main() -> None:
    if not SECTIONS_FILE.exists():
        raise SystemExit(f"Missing {SECTIONS_FILE}. Run 02_parse_statutes.py first.")
    data = json.loads(SECTIONS_FILE.read_text(encoding="utf-8"))
    sections = data["sections"]

    refs = []
    seen = set()

    for sec in sections:
        num = sec["sectionNumber"]
        text = sec["text"]
        fam_label = f"FAM § {num}"

        # FAM internal section mentions
        for m in SECTION_MENTION_RE.finditer(text):
            target = m.group(1)
            if target == num:
                continue
            url = build_url("FAM", target)
            key = (fam_label, "FAM", target)
            if key in seen:
                continue
            seen.add(key)
            refs.append(
                {
                    "fam_section": fam_label,
                    "fam_text": text[:160],
                    "referenced_code": "FAM",
                    "referenced_section": f"Section {target}",
                    "referenced_url": url,
                }
            )

        # External code section mentions
        for m in CODE_SECTION_RE.finditer(text):
            code = m.group(1).upper()
            target = m.group(2)
            if code == "FAM":
                continue
            url = build_url(code, target)
            key = (fam_label, code, target)
            if key in seen:
                continue
            seen.add(key)
            refs.append(
                {
                    "fam_section": fam_label,
                    "fam_text": text[:160],
                    "referenced_code": code,
                    "referenced_section": f"Section {target}",
                    "referenced_url": url,
                }
            )

        # Division / Part references (only if not already captured as a section)
        for m in DIVISION_RE.finditer(text):
            div = m.group(1)
            key = (fam_label, "DIV", div)
            if key in seen:
                continue
            seen.add(key)
            refs.append(
                {
                    "fam_section": fam_label,
                    "fam_text": text[:160],
                    "referenced_code": "FAM",
                    "referenced_section": f"Division {div}",
                    "referenced_url": f"https://leginfo.legislature.ca.gov/faces/codes_displayText.xhtml?lawCode=FAM&division={div}.",
                }
            )

    result = {
        "metadata": {
            "source": "California Family Code (FAM)",
            "generated_from": "family_code_sections.json",
            "section_count": len(sections),
            "cross_reference_count": len(refs),
        },
        "cross_references": refs,
    }
    OUT_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Built {len(refs)} cross-references -> {OUT_FILE}")


if __name__ == "__main__":
    main()

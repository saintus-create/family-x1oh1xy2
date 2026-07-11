#!/usr/bin/env python3
"""
Transfer Family Code section text from the public Family Code API into a local JSON cache.

This script scans the existing MDX pages for section badges, looks up each section
number via the Family Code API, and saves the canonical section text into a JSON file
that can be used by the docs site or downstream tooling.

Examples:
  python3 transfer_leginfo_text.py --dry-run
  python3 transfer_leginfo_text.py --limit 5
  python3 transfer_leginfo_text.py --out-file data/family_code_sections.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from html import unescape
from pathlib import Path
from typing import Any

SECTION_BADGE_RE = re.compile(r'<Badge intent="info" minimal>Sec\.\s*([^<]+)</Badge>')
DEFAULT_LEGINFO_BASE = "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=FAM&sectionNum={section}."
DEFAULT_PAGES_DIR = Path("fern/docs/pages")
DEFAULT_OUT_FILE = Path("family_code_sections.json")


def extract_sections_from_page(page_text: str) -> list[str]:
    sections = []
    for match in SECTION_BADGE_RE.finditer(page_text):
        section = match.group(1).strip()
        if section and section not in sections:
            sections.append(section)
    return sections


def clean_html_text(fragment: str) -> str:
    fragment = unescape(fragment)
    fragment = re.sub(r'<[^>]+>', ' ', fragment)
    fragment = re.sub(r'\s+', ' ', fragment)
    return fragment.strip().strip('"').strip()


def extract_leginfo_text(html_text: str, section_number: str) -> str:
    pattern = re.compile(
        rf'<h6[^>]*>\s*<b>\s*{re.escape(section_number)}\.?\s*</b>\s*</h6>\s*<p[^>]*>(.*?)</p>',
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(html_text)
    if not match:
        raise ValueError(f"Could not locate text for section {section_number} in LegInfo HTML")

    text = clean_html_text(match.group(1))
    if not text:
        raise ValueError(f"Empty section text extracted for {section_number}")
    return text


def fetch_section(leginfo_url_template: str, section_number: str) -> dict[str, Any]:
    safe_number = urllib.parse.quote(section_number, safe="")
    url = leginfo_url_template.format(section=safe_number)
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "family-code-transfer/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        html_text = response.read().decode("utf-8", "ignore")

    text = extract_leginfo_text(html_text, section_number)
    return {
        "sectionNumber": section_number,
        "text": text,
        "source_url": url,
    }


def collect_pages(pages_dir: Path) -> list[Path]:
    if not pages_dir.exists():
        raise FileNotFoundError(f"Pages directory not found: {pages_dir}")
    return sorted(pages_dir.glob("*.mdx"))


def transfer_text(
    pages_dir: Path,
    leginfo_url_template: str,
    out_file: Path,
    dry_run: bool,
    limit: int | None,
) -> int:
    pages = collect_pages(pages_dir)
    seen: set[str] = set()
    payload: list[dict[str, Any]] = []
    fetched_count = 0

    for page_path in pages:
        page_text = page_path.read_text()
        section_numbers = extract_sections_from_page(page_text)
        if not section_numbers:
            continue

        for section_number in section_numbers:
            if section_number in seen:
                continue
            seen.add(section_number)
            if limit is not None and fetched_count >= limit:
                break

            try:
                section_data = fetch_section(leginfo_url_template, section_number)
            except urllib.error.HTTPError as exc:
                print(f"[WARN] {section_number}: HTTP {exc.code} while fetching from LegInfo", file=sys.stderr)
                continue
            except urllib.error.URLError as exc:
                print(f"[WARN] {section_number}: network error: {exc}", file=sys.stderr)
                continue
            except ValueError as exc:
                print(f"[WARN] {section_number}: {exc}", file=sys.stderr)
                continue

            payload.append(section_data)
            fetched_count += 1
            print(f"Fetched section {section_number} ({fetched_count}/{len(seen)})")

            if limit is not None and fetched_count >= limit:
                break

        if limit is not None and fetched_count >= limit:
            break

    result_payload = {
        "metadata": {
            "source": "California LegInfo",
            "section_url_template": leginfo_url_template,
            "pages_scanned": len(pages),
            "sections_fetched": len(payload),
        },
        "sections": payload,
    }

    if dry_run:
        print(f"\nDry run complete. {len(payload)} sections would be written to {out_file}.")
        return 0

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(result_payload, indent=2, ensure_ascii=False) + "\n")
    print(f"\nWrote {len(payload)} sections to {out_file}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Transfer Family Code section text from LegInfo into a local JSON cache")
    parser.add_argument("--pages-dir", default=str(DEFAULT_PAGES_DIR), help="Directory containing MDX pages to scan")
    parser.add_argument("--leginfo-url-template", default=DEFAULT_LEGINFO_BASE, help="LegInfo URL template for fetching a section page")
    parser.add_argument("--out-file", default=str(DEFAULT_OUT_FILE), help="Path to the JSON file to write")
    parser.add_argument("--dry-run", action="store_true", help="Print the sections that would be fetched without writing output")
    parser.add_argument("--limit", type=int, default=None, help="Optional cap on how many sections to fetch")
    args = parser.parse_args()

    repo_root = Path.cwd()
    pages_dir = repo_root / args.pages_dir
    out_file = repo_root / args.out_file

    try:
        return transfer_text(
            pages_dir=pages_dir,
            leginfo_url_template=args.leginfo_url_template,
            out_file=out_file,
            dry_run=args.dry_run,
            limit=args.limit,
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

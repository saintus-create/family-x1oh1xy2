#!/usr/bin/env python3
"""
parse_cases.py
==============
Re-parses _case_raw.txt into clean structured JSON,
replacing the truncated _section_case_map.json and _case_entries.json.

Output files:
  cases_clean.json         — list of all cases with full text
  section_case_map_clean.json — { sec_num: [case, ...] }

Run:
    python3 parse_cases.py
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW_TXT = ROOT / "_case_raw.txt"
OUTPUT_CASES = ROOT / "cases_clean.json"
OUTPUT_MAP = ROOT / "section_case_map_clean.json"


# ── Compendium section headings ────────────────────────────────────────────
# These match the Roman-numeral section headers in _case_raw.txt
SECTION_HEADINGS = [
    ("I",    "What is Abuse"),
    ("II",   "Issuing DV Restraining Orders"),
    ("III",  "Modifying and Terminating"),
    ("IV",   "Renewing Restraining Orders"),
    ("V",    "Custody and Visitation"),
    ("VI",   "Mutual Restraining Orders"),
    ("VII",  "Juvenile Dependency"),
    ("VIII", "Special Immigrant Juvenile"),
    ("IX",   "Spousal Support"),
    ("X",    "Firearms and Orders"),
    ("XI",   "DV as a Tort"),
    ("XII",  "Attorney Fees and Costs"),
    ("XIII", "Vexatious Litigant"),
    ("XIV",  "Other Cases"),
]

# Maps roman numeral → compendium_section key used in docs
_ROMAN_MAP = {r: r for r, _ in SECTION_HEADINGS}

# Regex to match a case header line:
# "Name v. Name (year) volume Reporter page"
# e.g.: "X.K. v. M.C. (2025) 112 Cal.App.5th 1287"
_CASE_HEADER_RE = re.compile(
    r"^(?P<name>.+?)\s+"
    r"\((?P<year>\d{4})\)\s+"
    r"(?P<citation>\d+\s+Cal\.(?:App\.)?\d+(?:th|d|st)?\s+\d+(?:\.\d+)?)"
    r"(?:\s+Supp\.\s+\d+)?"
    r"\s*$"
)

# Statute line pattern
_STATUTE_RE = re.compile(
    r"^Statut(?:es?|es used(?: or affected)?)\s*[:\-]\s*(.+)$",
    re.IGNORECASE,
)


def clean_text(s: str) -> str:
    """Remove page-header noise injected between paragraphs in the PDF export."""
    lines = s.splitlines()
    out = []
    skip_next = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Skip page header blocks: blank line, "Case-Annotated...", "Family Violence...", blank, page number
        if stripped == "Case-Annotated Compendium of California Domestic Violence Laws":
            skip_next = 4
            continue
        if skip_next > 0:
            skip_next -= 1
            continue
        out.append(line)

    text = "\n".join(out)
    # Collapse 3+ blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_raw(path: Path) -> list[dict]:
    """
    Parse _case_raw.txt into a list of case dicts:
      { name, year, citation, description, statutes, compendium_section }
    """
    raw = path.read_text(encoding="utf-8", errors="replace")
    raw = clean_text(raw)

    lines = raw.splitlines()

    cases = []
    current_section = "I"  # default to first section

    # Track where we are
    i = 0
    n = len(lines)

    # Section heading patterns  e.g. "I. What Is "Abuse" Under the DVPA?"
    _section_head_re = re.compile(
        r"^(I{1,3}V?|VI{0,3}|IX|XI{0,3}|XIV?)\.\s+",
        re.IGNORECASE,
    )

    while i < n:
        line = lines[i].strip()

        # Detect compendium section change
        sh = _section_head_re.match(line)
        if sh:
            roman = sh.group(1).upper()
            if roman in _ROMAN_MAP:
                current_section = roman
            i += 1
            continue

        # Try to match a case header
        m = _CASE_HEADER_RE.match(line)
        if m:
            name = m.group("name").strip()
            year = m.group("year").strip()
            citation = m.group("citation").strip()
            # Normalize citation ordinal: "5th" should already be there
            # but some have "5" without ordinal — fix
            citation = re.sub(r"(\d)(th|d|st)?\s+(\d)", lambda x: x.group(0), citation)

            # Collect description lines until we hit a "Statutes" line or next case
            desc_lines = []
            statute_str = ""
            i += 1
            while i < n:
                dline = lines[i].strip()
                # Statute line marks end of this case
                sm = _STATUTE_RE.match(dline)
                if sm:
                    # Collect the full statute string (may continue on next line)
                    statute_str = sm.group(1).strip()
                    i += 1
                    # Continuation lines (indented or starting with known words)
                    while i < n:
                        cont = lines[i].strip()
                        if cont and not _CASE_HEADER_RE.match(cont) and not _section_head_re.match(cont):
                            # Check if it looks like a continuation (starts lowercase or with section numbers)
                            if re.match(r"^[a-z]|^\d|^Civil|^Code|^Penal|^Evidence|^Government|^Welfare", cont):
                                statute_str += " " + cont
                                i += 1
                                continue
                        break
                    break
                # Next case header — stop
                if _CASE_HEADER_RE.match(dline):
                    break
                # Compendium section heading — stop
                if _section_head_re.match(dline):
                    break
                desc_lines.append(lines[i])
                i += 1

            description = "\n".join(desc_lines).strip()
            # Remove trailing page-header leftovers
            description = clean_text(description)

            # Extract section numbers from statute string
            sec_nums = re.findall(r"\b(\d{3,4}(?:\.\d+)?)\b", statute_str)

            cases.append({
                "name": name,
                "year": year,
                "citation": citation,
                "description": description,
                "statutes": statute_str,
                "statute_nums": sec_nums,
                "compendium_section": current_section,
            })
            continue

        i += 1

    return cases


def build_section_map(cases: list[dict]) -> dict[str, list]:
    """Build { sec_num: [case_dict, ...] } from parsed cases."""
    result: dict[str, list] = {}
    for case in cases:
        for num in case.get("statute_nums", []):
            result.setdefault(num, [])
            # Avoid duplicates
            if not any(c["name"] == case["name"] and c["year"] == case["year"] for c in result[num]):
                result[num].append(case)
    return result


def main():
    print("Parsing _case_raw.txt...")
    cases = parse_raw(RAW_TXT)
    print(f"  Found {len(cases)} cases")

    if not cases:
        print("ERROR: no cases parsed. Check _case_raw.txt format.")
        return

    # Show a sample
    print(f"\nSample case:")
    c = cases[0]
    print(f"  Name     : {c['name']}")
    print(f"  Year     : {c['year']}")
    print(f"  Citation : {c['citation']}")
    print(f"  Section  : {c['compendium_section']}")
    print(f"  Statutes : {c['statutes'][:80]}")
    print(f"  Desc     : {c['description'][:120]}...")

    OUTPUT_CASES.write_text(json.dumps(cases, indent=2, ensure_ascii=False))
    print(f"\nWrote {len(cases)} cases -> {OUTPUT_CASES.name}")

    sec_map = build_section_map(cases)
    print(f"Section map covers {len(sec_map)} unique section numbers")
    OUTPUT_MAP.write_text(json.dumps(sec_map, indent=2, ensure_ascii=False))
    print(f"Wrote section map -> {OUTPUT_MAP.name}")


if __name__ == "__main__":
    main()

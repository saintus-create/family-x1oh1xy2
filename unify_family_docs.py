#!/usr/bin/env python3
"""
unify_family_docs.py
====================
Master automation script for the California Family Code Fern docs site.

What it does
------------
1. Audits all data sources (JSON files, case maps, cross-references).
2. Builds a unified, deduplicated section registry from
   family_code_sections_full.json and family_code_sections.json.
3. Cleans / proofreads every section text:
   • Strips OCR artefacts and header/footer noise.
   • Normalises subsection markers to (a), (b), (1), (A) em-dash style.
   • Fixes common OCR ligature & spacing errors.
   • Preserves exact statutory language — does NOT rewrite legal text.
4. Regenerates ALL .mdx section pages in fern/docs/pages/ with:
   • Correct YAML front-matter (title, description, slug).
   • Proper § headings, subsection indentation, legal typography HTML.
   • Inline case callouts from _section_case_map.json.
   • Cross-reference footer links from fam_cross_references.json.
   • Back-to-division breadcrumb.
5. Rebuilds the case-annotation pages (fern/docs/pages/case-annotations/).
6. Regenerates home.mdx with a polished division grid.
7. Rebuilds fern/docs.yml with clean, hierarchical navigation that
   mirrors the actual MDX pages on disk.

Usage
-----
    cd /path/to/family-x1oh1xy2
    python unify_family_docs.py              # full rebuild
    python unify_family_docs.py --audit      # audit only (no writes)
    python unify_family_docs.py --section 6203  # rebuild one section
"""

import argparse
import json
import os
import re
import sys
import textwrap
from collections import defaultdict
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# Paths (relative to this script's directory)
# ──────────────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
PAGES_DIR   = ROOT / "fern" / "docs" / "pages"
CASES_DIR   = PAGES_DIR / "case-annotations"
DOCS_YML    = ROOT / "fern" / "docs.yml"

SECTIONS_FULL_JSON  = ROOT / "family_code_sections_full.json"
SECTIONS_JSON       = ROOT / "family_code_sections.json"
CASE_ENTRIES_JSON   = ROOT / "_case_entries.json"
SECTION_CASE_MAP    = ROOT / "_section_case_map.json"
CROSS_REFS_JSON     = ROOT / "fam_cross_references.json"
KENT_CHAPTERS_JSON  = ROOT / "kent_chapters.json"


# ──────────────────────────────────────────────────────────────────────────────
# California Family Code — official division/part/chapter structure
# Source: leginfo.legislature.ca.gov
# ──────────────────────────────────────────────────────────────────────────────
DIVISION_STRUCTURE = {
    "preliminary-provisions": {
        "number": "Preliminary",
        "title": "Preliminary Provisions and Definitions",
        "slug": "preliminary-provisions",
        "section_prefix": "preliminary-provisions",
        "chapters": [
            {"title": "General Provisions",          "start": 1,   "end": 14},
            {"title": "Definitions",                 "start": 50,  "end": 155},
            {"title": "Indian Child Welfare Act",    "start": 170, "end": 197},
        ],
    },
    "marriage": {
        "number": "2",
        "title": "Marriage",
        "slug": "marriage",
        "section_prefix": "marriage",
        "chapters": [
            {"title": "General Provisions",          "start": 200,  "end": 310},
            {"title": "Rights and Obligations",      "start": 700,  "end": 756},
        ],
    },
    "division-2.5-domestic-partners": {
        "number": "2.5",
        "title": "Domestic Partner Registration",
        "slug": "division-2.5-domestic-partners",
        "section_prefix": "division-2.5-domestic-partners",
        "chapters": [
            {"title": "Domestic Partner Registration", "start": 297, "end": 299},
        ],
    },
    "division-3-marriage": {
        "number": "3",
        "title": "Premarital Agreements",
        "slug": "division-3-marriage",
        "section_prefix": "division-3-marriage",
        "chapters": [
            {"title": "Premarital Agreements",       "start": 1600, "end": 1617},
        ],
    },
    "division-4-rights-during-marriage": {
        "number": "4",
        "title": "Rights and Obligations During Marriage",
        "slug": "division-4-rights-during-marriage",
        "section_prefix": "division-4-rights-during-marriage",
        "chapters": [
            {"title": "Community Property",          "start": 760,  "end": 870},
            {"title": "Separate Property",           "start": 850,  "end": 856},
            {"title": "Quasi-Community Property",    "start": 910,  "end": 916},
            {"title": "Liability of Marital Property","start": 910, "end": 916},
            {"title": "Fiduciary Duties",            "start": 1100, "end": 1104},
        ],
    },
    "division-5-conciliation": {
        "number": "5",
        "title": "Conciliation Proceedings",
        "slug": "division-5-conciliation",
        "section_prefix": "division-5-conciliation",
        "chapters": [
            {"title": "Conciliation Court",          "start": 1800, "end": 1852},
        ],
    },
    "division-6-dissolution": {
        "number": "6",
        "title": "Nullity, Dissolution, and Legal Separation",
        "slug": "division-6-dissolution",
        "section_prefix": "division-6-dissolution",
        "chapters": [
            {"title": "General Provisions",          "start": 2000, "end": 2030},
            {"title": "Nullity of Marriage",         "start": 2200, "end": 2255},
            {"title": "Dissolution of Marriage",     "start": 2310, "end": 2346},
            {"title": "Legal Separation",            "start": 2345, "end": 2352},
            {"title": "Summary Dissolution",         "start": 2400, "end": 2406},
            {"title": "Judgments",                   "start": 2550, "end": 2556},
        ],
    },
    "division-7-property": {
        "number": "7",
        "title": "Division of Property",
        "slug": "division-7-property",
        "section_prefix": "division-7-property",
        "chapters": [
            {"title": "Division of Community Estate","start": 2500, "end": 2660},
            {"title": "Retirement Plans",            "start": 2610, "end": 2654},
            {"title": "Pension Benefits",            "start": 2650, "end": 2660},
        ],
    },
    "division-8-custody": {
        "number": "8",
        "title": "Custody of Children",
        "slug": "division-8-custody",
        "section_prefix": "division-8-custody",
        "chapters": [
            {"title": "Guiding Principles",          "start": 3000, "end": 3030},
            {"title": "Custody Orders",              "start": 3060, "end": 3100},
            {"title": "Visitation Rights",           "start": 3100, "end": 3132},
            {"title": "Mediation",                   "start": 3160, "end": 3187},
            {"title": "Child Custody Evaluations",   "start": 3110, "end": 3130},
            {"title": "Jurisdiction",                "start": 3400, "end": 3426},
        ],
    },
    "division-9-support": {
        "number": "9",
        "title": "Support",
        "slug": "division-9-support",
        "section_prefix": "division-9-support",
        "chapters": [
            {"title": "Child Support",               "start": 3500, "end": 3656},
            {"title": "Spousal Support",             "start": 3650, "end": 3694},
            {"title": "Family Support",              "start": 3700, "end": 3712},
            {"title": "Support of Parents",          "start": 4000, "end": 4008},
            {"title": "Reciprocal Enforcement",      "start": 4800, "end": 4854},
        ],
    },
    "division-10-domestic-violence": {
        "number": "10",
        "title": "Prevention of Domestic Violence",
        "slug": "division-10-domestic-violence",
        "section_prefix": "division-10-domestic-violence",
        "chapters": [
            {"title": "Domestic Violence Prevention Act", "start": 6200, "end": 6260},
            {"title": "Protective Orders",               "start": 6300, "end": 6390},
            {"title": "Temporary Emergency Orders",      "start": 6320, "end": 6326},
            {"title": "Emergency Protective Orders",     "start": 6240, "end": 6256},
            {"title": "Uniform Interstate Enforcement",  "start": 6400, "end": 6409},
        ],
    },
    "division-11-minors": {
        "number": "11",
        "title": "Minors",
        "slug": "division-11-minors",
        "section_prefix": "division-11-minors",
        "chapters": [
            {"title": "Age of Majority",             "start": 6500, "end": 6503},
            {"title": "Contracts by Minors",         "start": 6700, "end": 6752},
            {"title": "Emancipation of Minors",      "start": 7000, "end": 7143},
        ],
    },
    "division-12-parent-child": {
        "number": "12",
        "title": "Parent and Child Relationship",
        "slug": "division-12-parent-child",
        "section_prefix": "division-12-parent-child",
        "chapters": [
            {"title": "Establishing Parentage",      "start": 7540, "end": 7558},
            {"title": "Voluntary Declaration",       "start": 7570, "end": 7578},
            {"title": "Uniform Parentage Act",       "start": 7600, "end": 7740},
            {"title": "Interstate Compact",          "start": 7900, "end": 7912},
        ],
    },
    "division-13-adoption": {
        "number": "13",
        "title": "Adoption",
        "slug": "division-13-adoption",
        "section_prefix": "division-13-adoption",
        "chapters": [
            {"title": "Agency Adoptions",            "start": 8500, "end": 8625},
            {"title": "Independent Adoptions",       "start": 8800, "end": 8826},
            {"title": "Stepparent Adoptions",        "start": 9000, "end": 9008},
            {"title": "Adoption of Adults",          "start": 9100, "end": 9103},
        ],
    },
    "division-14-family-law-facilitator": {
        "number": "14",
        "title": "Family Law Facilitator Act",
        "slug": "division-14-family-law-facilitator",
        "section_prefix": "division-14-family-law-facilitator",
        "chapters": [
            {"title": "General Provisions",          "start": 10000, "end": 10016},
        ],
    },
    "division-17-support-services": {
        "number": "17",
        "title": "Support Services",
        "slug": "division-17-support-services",
        "section_prefix": "division-17-support-services",
        "chapters": [
            {"title": "Department of Child Support Services", "start": 17000, "end": 17600},
        ],
    },
    "division-20-pilot-projects": {
        "number": "20",
        "title": "Pilot Projects",
        "slug": "division-20-pilot-projects",
        "section_prefix": "division-20-pilot-projects",
        "chapters": [
            {"title": "Pilot Projects",              "start": 20000, "end": 25000},
        ],
    },
}

# Case-annotation pages (already exist — we refine them)
CASE_ANNOTATION_PAGES = [
    ("I. What Is Abuse Under the DVPA",          "abuse-definition",           "I"),
    ("II. Issuing Domestic Violence Restraining Orders", "issuing-dv-restraining-orders", "II"),
    ("III. Modifying and Terminating DVROs",     "modifying-terminating-dvro", "III"),
    ("IV. Renewing DVROs",                       "renewing-dv-restraining-orders", "IV"),
    ("V. Custody and Visitation",                "custody-visitation",         "V"),
    ("VI. Mutual Restraining Orders",            "mutual-restraining-orders",  "VI"),
    ("VII. Juvenile Dependency",                 "juvenile-dependency",        "VII"),
    ("VIII. Special Immigrant Juvenile Status",  "special-immigrant-juvenile", "VIII"),
    ("IX. Spousal Support",                      "spousal-support",            "IX"),
    ("X. Firearms and DVROs",                    "dvro-firearms",              "X"),
    ("XI. DV as a Tort",                         "dv-as-tort",                 "XI"),
    ("XII. Attorney Fees and Costs",             "attorney-fees-costs",        "XII"),
    ("XIII. Vexatious Litigant",                 "vexatious-litigant",         "XIII"),
    ("XIV. Other Cases",                         "other-cases",                "XIV"),
]


# ──────────────────────────────────────────────────────────────────────────────
# TEXT CLEANING
# ──────────────────────────────────────────────────────────────────────────────

# OCR artefacts: stray page headers, running chapter headers, etc.
_NOISE_PATTERNS = [
    r'^\s*\[Revised Comment\].*$',   # Blumberg annotation markers
    r'^\s*\[New\]\s*$',
    r'^\s*\[Amended.*?\]\s*$',
    r'^DEFINITIONS\s*$',             # OCR running headers
    r'^PREVENTION\s*$',
    r'^MARRIAGE\s*$',
    r'^SUPPORT\s*$',
    r'^ADOPTION\s*$',
    r'^DISSOLUTION\s*$',
    r'\bRIGHT\s+TO\s+CUSTODY\b',
    r'\bCUSTODY\s+OF\s+(MINOR|CHILDREN)\b',
    r'\bOF\s+DOMESTIC\s+VIOLENCE\b',
    r'\bPRELIMINARY\s+PROVISIONS\b\s*§\s*\d+',
    r'\bCHILD\s+SUPPORT\b\s+§\s*\d+',
    r'\bDIVISION\s+\d+\b',
    r'\bPART\s+\d+\b(?!\s+of)',
    r'^\s*§\s+\d[\d.]*\s*$',
    r'\bFamily Violence Appellate Project\b',
    r'\b\d+\s+RIGHT\b',
    # Witkin treatise references (not statutory language)
    r'\d+\s+Witkin,\s+California\s+Summary.*?(?:\(\d{4}\)|$)',
    r'Treatises and Practice Aids.*$',
    r'^\s*ok\s*$',
    r'^\s*\*+\s*$',
    r'^\s*\d{1,3}\s*$',
    # Stats. enactment lines
    r'^\(Added by\s+Stats\.',
    r'^\(Amended by\s+Stats\.',
    r'^Stats\.\d{4},',
    r'^Enactment\s*$',
    r'^Comments\s*$',
    r'^Construction of code.*$',
    r'^the provision\s*$',
]
_NOISE_RE = re.compile(
    '|'.join(_NOISE_PATTERNS),
    re.IGNORECASE | re.MULTILINE,
)

# Subsection markers we recognise for conversion
_SUBSEC_RE = re.compile(
    r'(?<!\w)'                          # not preceded by word char
    r'(\(([a-zA-Z]{1,2}|\d{1,2})\))'  # (a) (b) (1) (2) (AA) etc.
    r'(?=\s)',
)

def _clean_text(raw: str) -> str:
    """Remove OCR noise, fix spacing, preserve statutory language."""
    if not raw:
        return ""

    # 1. Normalise line endings
    text = raw.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Remove header/footer noise
    text = _NOISE_RE.sub(" ", text)

    # 3. Collapse sequences of whitespace within a line (but keep newlines)
    lines = []
    for line in text.split("\n"):
        line = re.sub(r'[ \t]{2,}', ' ', line).strip()
        lines.append(line)
    text = "\n".join(lines)

    # 4. Collapse 3+ blank lines into 2
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 5. Fix OCR ligature errors
    ocr_fixes = {
        r'\bfi ': 'fi',     # fi ligature split
        r'\bfl ': 'fl',
        r'\bff ': 'ff',
        r'ﬁ': 'fi',
        r'ﬂ': 'fl',
        r'ﬀ': 'ff',
        r'\x00': '',
        r'\ufffd': '',
        r'  +': ' ',
    }
    for pattern, replacement in ocr_fixes.items():
        text = re.sub(pattern, replacement, text)

    # 6. Strip leading/trailing whitespace
    return text.strip()


def _subsections_to_html(text: str) -> str:
    """
    Convert subsection markers like (a) (1) (A) to
    <span class="subsec">(a)</span> HTML, indented.
    """
    def _replace(m):
        marker = m.group(1)
        return f'<span class="subsec">{marker}</span> '

    return _SUBSEC_RE.sub(_replace, text)


def _format_statute_text(text: str) -> str:
    """Full pipeline: clean → subsection HTML → paragraph splits."""
    text = _clean_text(text)
    text = _subsections_to_html(text)
    # Split on double-newlines to get paragraphs
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    return "\n\n".join(paras)


# ──────────────────────────────────────────────────────────────────────────────
# DATA LOADING
# ──────────────────────────────────────────────────────────────────────────────

def load_json(path: Path, default=None):
    if not path.exists():
        print(f"  [WARN] Missing: {path.name}", file=sys.stderr)
        return default if default is not None else {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_section_registry() -> dict:
    """
    Merge family_code_sections_full.json and family_code_sections.json
    into a unified dict keyed by normalised section number string.

    Priority: sections_full (has source_url) > sections (Blumberg text).
    We keep ALL unique sections; for duplicates, merge text intelligently.
    """
    registry = {}

    def _add(entry: dict, source_label: str):
        num = str(entry.get("sectionNumber", "")).strip()
        if not num:
            return
        text  = entry.get("text", "").strip()
        url   = entry.get("source_url", "")
        div   = entry.get("division", None)

        if num not in registry:
            registry[num] = {
                "sectionNumber": num,
                "text": text,
                "source_url": url,
                "division": div,
                "sources": [source_label],
            }
        else:
            existing = registry[num]
            # Prefer longer / richer text
            if len(text) > len(existing["text"]):
                existing["text"] = text
            if url and not existing["source_url"]:
                existing["source_url"] = url
            if div and not existing["division"]:
                existing["division"] = div
            if source_label not in existing["sources"]:
                existing["sources"].append(source_label)

    # Load full first (higher quality — has source URLs)
    full_data = load_json(SECTIONS_FULL_JSON, {})
    for s in full_data.get("sections", []):
        _add(s, "sections_full")

    # Load basic (broader section coverage)
    basic_data = load_json(SECTIONS_JSON, {})
    for s in basic_data.get("sections", []):
        _add(s, "sections_basic")

    print(f"  Registry: {len(registry)} unique sections from two sources.")
    return registry


def _clean_case_description(desc: str, name: str, citation: str) -> str:
    """
    Strip the embedded 'Name v. Name (year) citation' header that
    _case_entries.json puts at the start of every description.
    Also strips trailing page-break noise.
    """
    if not desc:
        return ""
    # Remove leading "Name (year) citation\n" pattern
    # e.g. "X.K. v. M.C. (2025) 112 Cal.App.5th 1287  In this case..."
    header_pat = re.compile(
        r'^' + re.escape(name) + r'\s*\(\d{4}\)\s+\d+\s+Cal\..*?\d+\s+',
        re.IGNORECASE,
    )
    desc = header_pat.sub('', desc, count=1).strip()
    # Collapse double spaces from PDF extraction
    desc = re.sub(r'  +', ' ', desc)
    return desc.strip()


def _extract_statutes_from_description(desc: str) -> str:
    """
    Pull the 'Statutes used or affected: ...' line out of a description
    if the statutes field itself is truncated.
    """
    m = re.search(
        r'Statut(?:es?|es used(?: or affected)?)\s*[:\-]\s*(.+?)(?:\n|$)',
        desc, re.IGNORECASE,
    )
    return m.group(1).strip() if m else ""


def build_case_map() -> dict:
    """
    Return dict: section_number_str -> list of case dicts.

    Strategy:
    - _section_case_map.json has section->cases with compendium_section but
      truncated descriptions and statutes.
    - _case_entries.json has longer descriptions (still cut off) but no
      compendium_section.
    - We merge them: use _section_case_map.json for structure/compendium_section,
      but replace description with the longer version from _case_entries.json
      where available.
    """
    case_map = defaultdict(list)

    # Build lookup from _case_entries.json by normalised name
    entries = load_json(CASE_ENTRIES_JSON, [])
    entries_by_name: dict[str, dict] = {}
    for e in entries:
        key = re.sub(r'\s+', ' ', e.get("name", "")).strip().lower()
        entries_by_name[key] = e

    # Primary: _section_case_map.json
    raw = load_json(SECTION_CASE_MAP, {})
    for sec_num, cases in raw.items():
        for case in cases:
            name = case.get("name", "")
            key = re.sub(r'\s+', ' ', name).strip().lower()

            # Try to find a longer description in _case_entries.json
            entry = entries_by_name.get(key)
            if entry:
                long_desc = _clean_case_description(
                    entry.get("description", ""), name, entry.get("citation", "")
                )
                # Prefer longer cleaned description
                if len(long_desc) > len(case.get("description", "")):
                    case = dict(case)
                    case["description"] = long_desc
                # Fix truncated statutes: re-extract from description
                if case.get("statutes", "").rstrip().endswith((",", ";")):
                    extracted = _extract_statutes_from_description(long_desc)
                    if extracted:
                        case["statutes"] = extracted
                # Fix citation (add ordinal if missing page number)
                raw_cite = entry.get("citation", case.get("citation", ""))
                if raw_cite and not re.search(r'\d+$', raw_cite):
                    pass  # leave as-is
                elif raw_cite:
                    case = dict(case)
                    case["citation"] = raw_cite

            case_map[str(sec_num)].append(case)

    return dict(case_map)


def build_cross_ref_map() -> dict:
    """Return dict: fam_section_str -> list of cross-ref dicts."""
    xref_map = defaultdict(list)
    data = load_json(CROSS_REFS_JSON, {})
    for xref in data.get("cross_references", []):
        # "FAM § 6203" → "6203"
        raw_sec = xref.get("fam_section", "")
        m = re.search(r'§\s*([\d.]+)', raw_sec)
        if m:
            xref_map[m.group(1)].append(xref)
    return dict(xref_map)


# ──────────────────────────────────────────────────────────────────────────────
# MDX PAGE GENERATION
# ──────────────────────────────────────────────────────────────────────────────

# Known section titles for common/important sections
# (avoids relying entirely on OCR-noisy first-line extraction)
_KNOWN_TITLES: dict[str, str] = {
    "6200": "Domestic Violence Prevention Act",
    "6201": "Legislative Findings",
    "6202": "Definitions govern construction",
    "6203": '"Abuse" defined',
    "6204": '"Abuse" includes coercive control',
    "6205": '"Affinity" defined',
    "6206": '"Coercive control" defined',
    "6209": '"Protective order" defined',
    "6210": '"Disturbing the peace" defined',
    "6211": '"Domestic violence" defined',
    "6215": '"Emergency protective order" defined',
    "6218": '"Protective order" defined',
    "6220": '"Petitioner" and "respondent" defined',
    "6300": "Issuance of protective orders",
    "6301": "Persons who may seek protective order",
    "6320": "Orders enjoining harassment, contact, or abuse",
    "6321": "Exclusive possession of residence",
    "6322": "Protective orders for children",
    "6323": "Protection of animals",
    "6324": "Control of property",
    "6325": "Temporary child custody",
    "6340": "Issuance after notice and hearing",
    "6341": "Fees and costs",
    "6344": "Attorney fees",
    "6345": "Duration of orders",
    "6380": "Registration of orders",
    "3044": "Presumption against custody for perpetrators of DV",
    "3011": "Best interest of child",
    "3020": "Legislative findings; health, safety, and welfare",
    "3022": "Custody orders",
    "3024": "Notice of change of residence",
}


def _extract_section_title(cleaned_text: str, sec_num: str) -> str:
    """
    Extract a short, clean title for the section heading.
    Priority: known titles dict > first non-noise line of text.
    No em-dashes. No brackets. No ALL CAPS.
    """
    # 1. Check known titles first
    if sec_num in _KNOWN_TITLES:
        return _KNOWN_TITLES[sec_num]

    if not cleaned_text:
        return ""

    # 2. Try to extract from first meaningful line
    for line in cleaned_text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Skip lines that are noise even after cleaning
        if re.match(r'^\[', line):          # [Revised Comment] etc
            continue
        if re.match(r'^\(', line):          # starts with subsection marker
            continue
        if re.match(r'^\d', line):          # starts with number
            continue
        if line.isupper():                  # ALL CAPS running header
            continue
        if len(line) > 90:                  # too long to be a title
            continue
        if re.search(r'§\s*\d', line):      # contains section reference
            continue
        # Looks like a title
        # Convert to sentence case (only uppercase first letter)
        title = line[0].upper() + line[1:] if line else line
        # Remove any trailing period
        title = title.rstrip('.')
        return title

    return ""


def _section_slug(div_prefix: str, sec_num: str) -> str:
    """e.g. "division-10-domestic-violence", "6203" → "division-10-domestic-violence-section-6203" """
    return f"{div_prefix}-section-{sec_num}"


def _leginfo_url(sec_num: str) -> str:
    return (
        f"https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml"
        f"?lawCode=FAM&sectionNum={sec_num}."
    )


def _render_case_callout(case: dict) -> str:
    name = case.get("name", "Unknown").strip()
    name = re.sub(r'^[A-Z]\.\s*Cases?\s*\n\s*\n?\s*', '', name).strip()
    year = case.get("year", "")
    citation = case.get("citation", "").strip()
    description = case.get("description", "").strip()
    statutes = case.get("statutes", "").strip()

    # Fix citation: "112 Cal.App.5" -> "112 Cal.App.5th" (add ordinal if missing)
    citation = re.sub(r'(Cal\.(?:App\.)?\d+)$', lambda m: m.group(1) + 'th', citation)
    # Strip page number from end of citation for display (keep vol + reporter)
    cite_display = re.sub(r'\s+\d+$', '', citation).strip()
    if not cite_display:
        cite_display = citation

    label = f"{name} ({year})" if year else name

    lines = [
        '<div class="case-callout">',
        f'<strong>{label}</strong>',
        '',
        f'*{cite_display}*',
        '',
    ]
    if description:
        # Clean up double-spaces from PDF extraction
        description = re.sub(r'  +', ' ', description)
        # Remove any embedded statute line at the end of description
        description = re.sub(
            r'\n?Statut(?:es?|es used(?: or affected)?)\s*[:\-].*$',
            '', description, flags=re.IGNORECASE | re.DOTALL,
        ).strip()
        lines.append(description)
        lines.append('')
    if statutes:
        # Remove trailing comma/semicolon from truncated statutes
        statutes = statutes.rstrip(', ;')
        lines.append(f'<span class="case-statutes">Statutes: {statutes}</span>')
    lines.append('</div>')
    return '\n'.join(lines)


def _render_cross_refs(xrefs: list) -> str:
    if not xrefs:
        return ""
    seen = set()
    chips = []
    for xref in xrefs:
        sec = xref.get("referenced_section", "")
        url = xref.get("referenced_url", "")
        code = xref.get("referenced_code", "FAM")
        label = f"{code} {sec}" if sec else ""
        if label and label not in seen:
            seen.add(label)
            if url:
                chips.append(f'<a class="statute-link" href="{url}">{label}</a>')
            else:
                chips.append(f'<span class="statute-link">{label}</span>')
    if not chips:
        return ""
    return (
        '\n<div class="source-note">\n\n'
        '**Cross-References:** ' + ' '.join(chips) + '\n\n</div>'
    )


def generate_section_page(
    sec_num: str,
    section: dict,
    div_info: dict,
    cases: list,
    xrefs: list,
) -> str:
    """Render a single section's .mdx content."""

    div_title  = div_info["title"]
    div_slug   = div_info["slug"]
    div_number = div_info["number"]
    sec_slug   = _section_slug(div_info["section_prefix"], sec_num)

    # ── Extract a real section title from the statutory text ─────────────────
    raw_text = section.get("text", "")
    # Clean the text first so title detection works on noise-free content
    cleaned_for_title = _clean_text(raw_text)
    sec_title = _extract_section_title(cleaned_for_title, sec_num)

    description = sec_title if sec_title else f"California Family Code section {sec_num}"

    formatted_text = _format_statute_text(raw_text)
    source_url = section.get("source_url") or _leginfo_url(sec_num)

    parts = []

    # ── Front-matter (no em-dash anywhere) ───────────────────────────────────
    fm_title = f"{sec_num}. {sec_title}" if sec_title else f"Section {sec_num}"
    parts.append(
        f'---\n'
        f'title: "{fm_title}"\n'
        f'description: "{description[:160]}"\n'
        f'slug: {sec_slug}\n'
        f'---\n'
    )

    # ── Breadcrumb ────────────────────────────────────────────────────────────
    icon_svg = '<svg style="display:inline;width:12px;height:12px;vertical-align:-1px;margin-right:4px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>'
    parts.append(
        f'<div class="source-note">\n'
        f'  {icon_svg}\n'
        f'  <a href="/{div_slug}">{div_title}</a>\n'
        f'</div>\n'
    )

    # ── Section heading (number + title, no em-dash) ──────────────────────────
    if sec_title:
        parts.append(f"# {sec_num}. {sec_title}")
    else:
        parts.append(f"# Section {sec_num}")
    parts.append(f"\n*{div_title}*\n")

    # ── Case callouts (before statutory text, per annotated code tradition) ──
    if cases:
        for case in cases[:12]:   # cap at 12 per page
            parts.append(_render_case_callout(case))
            parts.append("")

    # ── Statutory text ────────────────────────────────────────────────────────
    if formatted_text:
        parts.append(formatted_text)
        parts.append("")

    # ── Cross-references ──────────────────────────────────────────────────────
    xref_block = _render_cross_refs(xrefs)
    if xref_block:
        parts.append(xref_block)
        parts.append("")

    # ── Source note ───────────────────────────────────────────────────────────
    parts.append(textwrap.dedent(f"""\
        <div class="source-note">

        Source: California Family Code Annotated (Grace Ganz Blumberg, 2020 Desktop Edition).
        [View on California Legislative Information]({source_url})

        </div>
    """))

    return "\n".join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# DIVISION INDEX PAGE
# ──────────────────────────────────────────────────────────────────────────────

def generate_division_index(
    div_info: dict,
    section_slugs: list,       # [(sec_num, slug), ...]
) -> str:
    """Render the division's index page with a section card grid."""
    div_number = div_info["number"]
    div_title  = div_info["title"]
    div_slug   = div_info["slug"]

    # Build chaptered card groups
    chapters = div_info.get("chapters", [])

    parts = []
    parts.append(textwrap.dedent(f"""\
        ---
        title: "Division {div_number} — {div_title}"
        description: "Index of all sections in Division {div_number} of the California Family Code."
        slug: {div_slug}
        ---
    """))

    parts.append(f"# Division {div_number} — {div_title}\n")
    parts.append(
        f"**California Family Code** · Division {div_number}\n\n"
        f"This division contains §§ "
        + (f"{section_slugs[0][0]}–{section_slugs[-1][0]}" if section_slugs else "—")
        + ".\n"
    )

    if section_slugs:
        parts.append('<div class="section-grid">\n')
        for sec_num, slug in section_slugs:
            parts.append(
                f'<a class="section-card" href="/{slug}">§ {sec_num}</a>'
            )
        parts.append('\n</div>\n')

    parts.append(textwrap.dedent(f"""\

        <div class="source-note">

        **Source:** California Family Code Annotated (Grace Ganz Blumberg, 2020 Desktop Edition).\\
        [California Legislative Information](https://leginfo.legislature.ca.gov/faces/codesTOCSelected.xhtml?tocCode=FAM)

        </div>
    """))

    return "\n".join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# HOME PAGE
# ──────────────────────────────────────────────────────────────────────────────

# Division metadata for home page rows
_DIVISION_META = {
    "preliminary-provisions":          "Definitions, construction, general rules",
    "marriage":                        "Validity, licenses, solemnization, rights",
    "division-2.5-domestic-partners":  "Registration, rights, and dissolution",
    "division-3-marriage":             "Validity, enforcement, disclosure requirements",
    "division-4-rights-during-marriage": "Community property, fiduciary duties, liability",
    "division-5-conciliation":         "Conciliation court, counseling, jurisdiction",
    "division-6-dissolution":          "Nullity, dissolution, legal separation, summary dissolution",
    "division-7-property":             "Community estate, retirement plans, pensions",
    "division-8-custody":              "Custody orders, visitation, mediation, jurisdiction",
    "division-9-support":              "Child support, spousal support, family support",
    "division-10-domestic-violence":   "DVPA, protective orders, emergency orders, enforcement",
    "division-11-minors":              "Age of majority, contracts, emancipation",
    "division-12-parent-child":        "Establishing parentage, voluntary declarations, Uniform Parentage Act",
    "division-13-adoption":            "Agency, independent, stepparent, adult adoptions",
    "division-14-family-law-facilitator": "Facilitator offices, services, funding",
    "division-17-support-services":    "Department of Child Support Services, enforcement",
    "division-20-pilot-projects":      "Legislative pilot programs and special provisions",
}

_BOOK_ICON = (
    '<svg class="division-row-icon" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="1.75" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>'
    '<path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>'
    '</svg>'
)
_ARROW_ICON = (
    '<svg class="division-row-arrow" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="1.75">'
    '<polyline points="9 18 15 12 9 6"/>'
    '</svg>'
)


def generate_home_page() -> str:
    rows = []
    for key, div in DIVISION_STRUCTURE.items():
        num   = div["number"]
        title = div["title"]
        slug  = div["slug"]
        num_display = "Prelim." if num == "Preliminary" else str(num)
        meta  = _DIVISION_META.get(key, "")
        rows.append(
            f'<a class="division-row" href="/{slug}">\n'
            f'  <span class="division-row-num">{num_display}</span>\n'
            f'  {_BOOK_ICON}\n'
            f'  <div class="division-row-body">\n'
            f'    <div class="division-row-title">{title}</div>\n'
            f'    <div class="division-row-meta">{meta}</div>\n'
            f'  </div>\n'
            f'  {_ARROW_ICON}\n'
            f'</a>'
        )

    rows_block = "\n\n".join(rows)

    return (
        "---\n"
        "slug: home\n"
        "title: California Family Code\n"
        'description: "Complete annotated statutes with case law and cross-references."\n'
        "layout: custom\n"
        "no-image-zoom: true\n"
        "---\n"
        "\n"
        '<div class="home-hero">\n'
        "\n"
        "# California Family Code\n"
        "\n"
        "Complete statutory text with case annotations and cross-references.\n"
        "Source: Blumberg, _California Family Code Annotated_ (2020).\n"
        "\n"
        "</div>\n"
        "\n"
        '<div class="division-list">\n'
        "\n"
        + rows_block + "\n"
        "\n"
        "</div>\n"
        "\n"
        '<div class="source-note">\n'
        "\n"
        "Source: California Family Code Annotated (Grace Ganz Blumberg, 2020 Desktop Edition).\n"
        "[California Legislative Information](https://leginfo.legislature.ca.gov/faces/codesTOCSelected.xhtml?tocCode=FAM)\n"
        "\n"
        "</div>\n"
    )


# ──────────────────────────────────────────────────────────────────────────────
# CASE ANNOTATION PAGES (refine existing)
# ──────────────────────────────────────────────────────────────────────────────

def generate_case_annotation_page(
    long_title: str,
    slug: str,
    compendium_section: str,
    all_cases: list,
) -> str:
    """
    Build a clean case annotation page for one compendium section.
    """
    # Filter cases for this compendium section
    section_cases = [
        c for c in all_cases
        if c.get("compendium_section", "") == compendium_section
    ]
    # Sort by year desc
    section_cases.sort(key=lambda c: str(c.get("year", "0000")), reverse=True)

    parts = []
    parts.append(textwrap.dedent(f"""\
        ---
        title: "{long_title}"
        description: "California appellate case annotations: {long_title}."
        slug: case-annotations/{slug}
        ---
    """))

    parts.append(f"# {long_title}\n")
    parts.append(
        "> **Source:** [Family Violence Appellate Project — "
        "Case-Annotated Compendium of California Domestic Violence Laws (2026 ed.)]"
        "(https://www.fvaplaw.org)\n"
    )

    if not section_cases:
        parts.append("*No cases indexed for this section.*\n")
        return "\n".join(parts)

    for case in section_cases:
        name = _clean_text(case.get("name", "Unknown"))
        name = re.sub(r'^[A-Z]\.\s*Cases?\s*\n\s*\n?\s*', '', name).strip()
        year = case.get("year", "")
        citation = case.get("citation", "")
        description = _clean_text(case.get("description", ""))
        statutes = case.get("statutes", "").strip()

        label = f"{name} ({year})" if year else name
        # Full citation with ordinal suffix
        full_cite = citation
        if citation and not re.search(r'(th|d|st)\b', citation):
            full_cite += "th"

        parts.append(f"## {label}\n")
        if full_cite:
            parts.append(f"**Citation:** *{full_cite}*\n")
        if description:
            parts.append(description + "\n")
        if statutes:
            parts.append(f"**Statutes:** {statutes}\n")
        parts.append("---\n")

    return "\n".join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# docs.yml GENERATION
# ──────────────────────────────────────────────────────────────────────────────

def _yml_entry(indent: int, key: str, value: str) -> str:
    return " " * indent + f"{key}: {value}"


def _yml_page(indent: int, label: str, path: str) -> str:
    return (
        " " * indent + f"- page: {json.dumps(label)}\n"
        + " " * (indent + 2) + f"path: {path}"
    )


def generate_docs_yml(division_nav: dict) -> str:
    """
    Rebuild fern/docs.yml with slim navigation:
    - Overview section with Home page
    - Divisions section with one entry per division index page (no section entries)
    - Case Annotations section with one entry per annotation page

    division_nav: dict keyed by div_slug →
        { "label": str, "index_path": str }
      (groups/section entries are intentionally ignored)
    """

    # Sidebar labels — short, title-case, no div number prefix, no em-dash
    _DIV_SIDEBAR_LABELS = {
        "preliminary-provisions":            "Preliminary Provisions",
        "marriage":                          "Marriage",
        "division-2.5-domestic-partners":    "Domestic Partner Registration",
        "division-3-marriage":               "Premarital Agreements",
        "division-4-rights-during-marriage": "Rights During Marriage",
        "division-5-conciliation":           "Conciliation Proceedings",
        "division-6-dissolution":            "Dissolution and Separation",
        "division-7-property":               "Division of Property",
        "division-8-custody":                "Custody of Children",
        "division-9-support":                "Support",
        "division-10-domestic-violence":     "Prevention of Domestic Violence",
        "division-11-minors":                "Minors",
        "division-12-parent-child":          "Parent and Child Relationship",
        "division-13-adoption":              "Adoption",
        "division-14-family-law-facilitator":"Family Law Facilitator Act",
        "division-17-support-services":      "Support Services",
        "division-20-pilot-projects":        "Pilot Projects",
    }

    # Case annotation sidebar labels (short, no roman numeral prefix)
    _CASE_SIDEBAR_LABELS = {
        "abuse-definition":               "What is Abuse",
        "issuing-dv-restraining-orders":  "Issuing Restraining Orders",
        "modifying-terminating-dvro":     "Modifying and Terminating",
        "renewing-dv-restraining-orders": "Renewing Restraining Orders",
        "custody-visitation":             "Custody and Visitation",
        "mutual-restraining-orders":      "Mutual Restraining Orders",
        "juvenile-dependency":            "Juvenile Dependency",
        "special-immigrant-juvenile":     "Special Immigrant Juvenile",
        "spousal-support":                "Spousal Support",
        "dvro-firearms":                  "Firearms and Orders",
        "dv-as-tort":                     "DV as a Tort",
        "attorney-fees-costs":            "Attorney Fees and Costs",
        "vexatious-litigant":             "Vexatious Litigant",
        "other-cases":                    "Other Cases",
    }

    lines = []
    lines.append("# yaml-language-server: $schema=https://schema.buildwithfern.dev/docs-yml.json")
    lines.append("")
    lines.append("instances:")
    lines.append("  - url: https://family.docs.buildwithfern.com")
    lines.append("    edit-this-page:")
    lines.append("      github:")
    lines.append("        owner: saintus-create")
    lines.append("        repo: family-x1oh1xy2")
    lines.append("        branch: main")
    lines.append("")
    lines.append("title: California Family Code")
    lines.append("")
    lines.append("layout:")
    lines.append("  searchbar-placement: header")
    lines.append("  page-width: wide")
    lines.append("  tabs-placement: header")
    lines.append("")
    lines.append("tabs:")
    lines.append("  code:")
    lines.append("    display-name: Family Code")
    lines.append("    icon: docs/assets/icon-circle.svg")
    lines.append("")
    lines.append("navigation:")
    lines.append("  - tab: code")
    lines.append("    layout:")

    # ── Overview ──────────────────────────────────────────────────────────────
    lines.append("      - section: Overview")
    lines.append("        contents:")
    lines.append("          - page: Home")
    lines.append("            path: docs/pages/home.mdx")
    lines.append("")

    # ── Divisions ─────────────────────────────────────────────────────────────
    lines.append("      - section: Divisions")
    lines.append("        contents:")
    for div_slug in DIVISION_STRUCTURE:
        label = _DIV_SIDEBAR_LABELS.get(div_slug, DIVISION_STRUCTURE[div_slug]["title"])
        path  = f"docs/pages/{div_slug}.mdx"
        lines.append(f"          - page: {label}")
        lines.append(f"            path: {path}")
    lines.append("")

    # ── Case Annotations ──────────────────────────────────────────────────────
    lines.append("      - section: Case Annotations")
    lines.append("        contents:")
    for long_title, slug, _ in CASE_ANNOTATION_PAGES:
        label = _CASE_SIDEBAR_LABELS.get(slug, long_title.split(". ", 1)[-1][:55])
        lines.append(f"          - page: {label}")
        lines.append(f"            path: docs/pages/case-annotations/{slug}.mdx")
    lines.append("")

    # ── Colors, theme, assets ─────────────────────────────────────────────────
    lines.append("colors:")
    lines.append("  accent-primary:")
    lines.append('    light: "#0066cc"')
    lines.append('    dark: "#4da6ff"')
    lines.append("  background:")
    lines.append('    light: "#ffffff"')
    lines.append('    dark: "#0a0a0a"')
    lines.append("  border:")
    lines.append('    light: "#e5e5e5"')
    lines.append('    dark: "#2a2a2a"')
    lines.append("")
    lines.append("theme:")
    lines.append("  page-actions: toolbar")
    lines.append("  footer-nav: minimal")
    lines.append("")
    lines.append("landing-page:")
    lines.append("  page: Home")
    lines.append("  path: docs/pages/home.mdx")
    lines.append("")
    lines.append("css:")
    lines.append("  - styles.css")

    return "\n".join(lines) + "\n"


# ──────────────────────────────────────────────────────────────────────────────
# MAIN ORCHESTRATION
# ──────────────────────────────────────────────────────────────────────────────

def _sec_num_sort_key(s: str) -> tuple:
    """Sort section numbers numerically: "3.5" → (3, 5), "10" → (10, 0)."""
    parts = s.split(".")
    try:
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
        return (major, minor)
    except ValueError:
        return (999999, 0)


def _group_sections(sec_nums: list, target_group_size: int = 50) -> list:
    """
    Split a sorted list of section numbers into labelled groups of
    ~target_group_size for sidebar readability.
    Returns list of {"group_label": str, "sec_nums": [str, ...]}.
    """
    if not sec_nums:
        return []
    if len(sec_nums) <= target_group_size:
        first = sec_nums[0]
        last  = sec_nums[-1]
        label = f"§§ {first}–{last}" if first != last else f"§ {first}"
        return [{"group_label": label, "sec_nums": sec_nums}]

    groups = []
    for i in range(0, len(sec_nums), target_group_size):
        chunk = sec_nums[i:i + target_group_size]
        label = f"§§ {chunk[0]}–{chunk[-1]}"
        groups.append({"group_label": label, "sec_nums": chunk})
    return groups


def _assign_section_to_division(sec_num: str, registry: dict) -> str | None:
    """
    Try to find which division a section belongs to.
    Priority: registry's 'division' field, then fallback by numeric range.
    """
    entry = registry.get(sec_num, {})
    if entry.get("division"):
        d = str(entry["division"])
        # Map numeric division → slug
        for slug, info in DIVISION_STRUCTURE.items():
            if str(info["number"]) == d:
                return slug
        return None

    # Fallback: find which division's chapter ranges include this section
    try:
        n = float(sec_num)
    except ValueError:
        return None

    best = None
    best_gap = float("inf")
    for slug, info in DIVISION_STRUCTURE.items():
        for ch in info.get("chapters", []):
            if ch["start"] <= n <= ch["end"]:
                gap = min(n - ch["start"], ch["end"] - n)
                if gap < best_gap:
                    best_gap = gap
                    best = slug
    return best


def run(
    audit_only: bool = False,
    single_section: str = None,
):
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    CASES_DIR.mkdir(parents=True, exist_ok=True)

    print("━" * 60)
    print("  California Family Code — Fern Docs Unification")
    print("━" * 60)

    # ── 1. Load data ──────────────────────────────────────────────────────────
    print("\n[1] Loading data sources…")
    registry  = build_section_registry()
    case_map  = build_case_map()
    xref_map  = build_cross_ref_map()
    all_cases = load_json(CASE_ENTRIES_JSON, [])

    # ── 2. Scan existing MDX pages to discover section→division mapping ───────
    print("\n[2] Scanning existing MDX pages for section-to-division mapping…")
    # Build: {sec_num: div_slug} from file names on disk
    existing_file_map: dict[str, str] = {}
    for f in PAGES_DIR.glob("*.mdx"):
        # e.g. "division-10-domestic-violence-section-6203.mdx"
        m = re.match(r'^(.+)-section-([\d.]+)\.mdx$', f.stem)
        if m:
            existing_file_map[m.group(2)] = m.group(1)  # sec → div_prefix

    print(f"     Found {len(existing_file_map)} existing section pages.")

    # ── 3. Build division → section list ──────────────────────────────────────
    print("\n[3] Assigning sections to divisions…")
    div_sections: dict[str, list] = defaultdict(list)

    for sec_num, section in registry.items():
        # First: check existing file mapping (most reliable)
        if sec_num in existing_file_map:
            prefix = existing_file_map[sec_num]
            # Find matching div_slug by section_prefix
            for slug, info in DIVISION_STRUCTURE.items():
                if info["section_prefix"] == prefix:
                    div_sections[slug].append(sec_num)
                    break
            else:
                # prefix not in DIVISION_STRUCTURE — assign by range
                slug = _assign_section_to_division(sec_num, registry)
                if slug:
                    div_sections[slug].append(sec_num)
        else:
            slug = _assign_section_to_division(sec_num, registry)
            if slug:
                div_sections[slug].append(sec_num)

    # Sort each division's sections
    for slug in div_sections:
        div_sections[slug] = sorted(set(div_sections[slug]), key=_sec_num_sort_key)

    total = sum(len(v) for v in div_sections.values())
    print(f"     Assigned {total} sections across {len(div_sections)} divisions.")

    if audit_only:
        print("\n── AUDIT REPORT ──────────────────────────────────────")
        for slug, secs in sorted(div_sections.items()):
            print(f"  {DIVISION_STRUCTURE[slug]['title']:45s}  {len(secs):4d} sections")
        unassigned = [s for s in registry if s not in {
            n for secs in div_sections.values() for n in secs
        }]
        print(f"\n  Unassigned sections: {len(unassigned)}")
        print("\n── END AUDIT ─────────────────────────────────────────")
        return

    # ── 4. Write section pages ────────────────────────────────────────────────
    print("\n[4] Generating section pages…")
    written = 0
    skipped = 0

    for div_slug, sec_nums in div_sections.items():
        div_info = DIVISION_STRUCTURE[div_slug]
        for sec_num in sec_nums:
            if single_section and sec_num != single_section:
                continue

            section = registry.get(sec_num, {})
            cases   = case_map.get(sec_num, [])
            xrefs   = xref_map.get(sec_num, [])

            content = generate_section_page(sec_num, section, div_info, cases, xrefs)
            slug    = _section_slug(div_info["section_prefix"], sec_num)
            fpath   = PAGES_DIR / f"{slug}.mdx"

            fpath.write_text(content, encoding="utf-8")
            written += 1

    print(f"     Written: {written}  |  Skipped: {skipped}")

    if single_section:
        print(f"\n  Done — rebuilt § {single_section} only.")
        return

    # ── 5. Write division index pages ─────────────────────────────────────────
    print("\n[5] Generating division index pages…")
    for div_slug, sec_nums in div_sections.items():
        div_info = DIVISION_STRUCTURE[div_slug]
        prefix   = div_info["section_prefix"]
        slugs    = [(n, _section_slug(prefix, n)) for n in sec_nums]
        content  = generate_division_index(div_info, slugs)
        fpath    = PAGES_DIR / f"{div_slug}.mdx"
        fpath.write_text(content, encoding="utf-8")
        print(f"     {div_slug}.mdx")

    # ── 6. Write home page ────────────────────────────────────────────────────
    print("\n[6] Generating home page…")
    (PAGES_DIR / "home.mdx").write_text(generate_home_page(), encoding="utf-8")

    # ── 7. Write case annotation pages ───────────────────────────────────────
    print("\n[7] Generating case annotation pages…")
    # Merge _case_entries.json with _section_case_map entries to get
    # compendium_section tags for all cases
    merged_cases = []
    for sec_num, cases in case_map.items():
        for c in cases:
            c2 = dict(c)
            merged_cases.append(c2)
    # Also add plain entries (may lack compendium_section)
    for c in all_cases:
        merged_cases.append(c)

    for long_title, slug, compendium_section in CASE_ANNOTATION_PAGES:
        content = generate_case_annotation_page(
            long_title, slug, compendium_section, merged_cases
        )
        fpath = CASES_DIR / f"{slug}.mdx"
        fpath.write_text(content, encoding="utf-8")
        print(f"     case-annotations/{slug}.mdx")

    # ── 8. Rebuild docs.yml ───────────────────────────────────────────────────
    print("\n[8] Rebuilding fern/docs.yml…")

    # Slim nav — only division index paths, no section entries
    division_nav: dict = {
        div_slug: {
            "label": DIVISION_STRUCTURE[div_slug]["title"],
            "index_path": f"docs/pages/{div_slug}.mdx",
        }
        for div_slug in DIVISION_STRUCTURE
    }

    yml_content = generate_docs_yml(division_nav)
    DOCS_YML.write_text(yml_content, encoding="utf-8")
    print(f"     fern/docs.yml written ({DOCS_YML.stat().st_size // 1024} KB)")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "━" * 60)
    print("  ✓  Build complete.")
    print(f"     Section pages   : {written}")
    print(f"     Division indexes: {len(div_sections)}")
    print(f"     Case pages      : {len(CASE_ANNOTATION_PAGES)}")
    print("━" * 60)
    print("\nNext step:  fern docs dev  (in the fern/ directory)")
    print("Or push to GitHub — Fern Cloud will rebuild automatically.\n")


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Unify & regenerate the California Family Code Fern docs site.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples
            --------
            Full rebuild:
                python unify_family_docs.py

            Audit only (no writes):
                python unify_family_docs.py --audit

            Rebuild a single section:
                python unify_family_docs.py --section 6203
        """),
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Report data statistics only; do not write any files.",
    )
    parser.add_argument(
        "--section",
        metavar="NUM",
        help="Rebuild only the page for this section number (e.g. 6203).",
    )
    args = parser.parse_args()
    run(audit_only=args.audit, single_section=args.section)

#!/usr/bin/env python3
"""
02_parse_statutes.py
---------------------
Parse the extracted PDF text (pdf_text/*.txt) into Family Code sections.

Each section begins with a "SECTION" / "Sec." / "§" marker followed by a
number and a period, e.g. "§ 6544." or "SEC. 3000.". The verbatim statute
body follows until the next section marker or until an annotation block
(starting with "(Stats.", "Law Revision Commission Comments", "Research
References", "History", "Comment", etc.).

Output: family_code_sections.json
  {
    "metadata": {...},
    "sections": [ {"sectionNumber": "6544", "text": "...", "source": "pdf"} ]
  }

Run:  python3 02_parse_statutes.py
"""
from __future__ import annotations
import json
import re
from pathlib import Path

REPO = Path.cwd()
TEXT_DIR = REPO / "pdf_text"
OUT_FILE = REPO / "family_code_sections.json"

# Section heading: § NNNN.  or SEC. NNNN.  or Section NNNN.  (number may have decimals)
SECTION_RE = re.compile(
    r"(?:§|SEC\.?|SECTION)\s+(\d{1,5}(?:\.\d+)?)\s*\.",
    re.IGNORECASE,
)

# Annotation blocks that mark the end of the verbatim statute text.
# Anything from one of these patterns (on a line boundary) to the next
# section is commentary, not code.
ANNOTATION_RE = re.compile(
    r"(?im)^\s*(?:\(\s*(?:Stats\.|Added|Amended|Repealed|Renumbered|"
    r"Note\s*enacted|Approved)\b"
    r"|Law\s+Revision\s+Commission\s+Comments"
    r"|Legislative\s+History"
    r"|History\b"
    r"|Research\s+References"
    r"|Comment\b"
    r"|Cross\s*[- ]?References?"
    r"|Forms\b"
    r"|Treatises\s+and\s+Practice\s+Aids"
    r"|Witkin"
    r"|West(?:'s)?\s+California"
    r"|Case\s+Annotations?"
    r"|Editorial\s+Notes?"
    r"|Law\s+Revision\s+Commission\b)"
)

# Also strip footnote-style references like "20 Cal.L.Rev.Comm.Reports"
CITATION_RE = re.compile(r"\[\d{1,3}\s+Cal\.?L\.?Rev\.?Comm\.?Reports[^\]]*\]")


def clean_text(raw: str) -> str:
    raw = CITATION_RE.sub("", raw)
    # Normalize whitespace
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


TOC_MARKERS = ("TABLE OF CONTENTS", "TABLE OF SECTIONS AFFECTED", "PREFACE", "WHAT’S NEW", "WHAT'S NEW")


def looks_like_toc(text: str) -> bool:
    up = text.upper()
    if any(m in up for m in TOC_MARKERS):
        return True
    # A TOC page is mostly numbers/dots with few real words.
    letters = len(re.findall(r"[A-Za-z]{4,}", text))
    return letters < 40


def split_sections(text: str) -> list[tuple[str, str]]:
    """Return list of (section_number, body_text)."""
    if looks_like_toc(text):
        return []
    matches = list(SECTION_RE.finditer(text))
    if not matches:
        return []
    out = []
    for idx, m in enumerate(matches):
        num = m.group(1)
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end]
        out.append((num, body))
    return out


# Dot-leader lines like "Preliminary Provisions ....... 1" signal a TOC fragment.
TOC_FRAGMENT_RE = re.compile(r"\.{4,}\s*\d+\s*$|\.{3,}\s+[A-Za-z].*\d+\s*$", re.MULTILINE)


def is_toc_fragment(text: str) -> bool:
    # Heuristic: a statute body should not be full of dot-leaders / page numbers.
    return len(TOC_FRAGMENT_RE.findall(text)) >= 2


def trim_annotations(body: str) -> str:
    """Cut the body at the first annotation block."""
    m = ANNOTATION_RE.search(body)
    if m:
        body = body[: m.start()]
    body = clean_text(body)
    if is_toc_fragment(body):
        return ""  # signal caller to skip
    return body


def main() -> None:
    if not TEXT_DIR.exists():
        raise SystemExit(f"Missing {TEXT_DIR}. Run 01_extract_pdf_text.py first.")
    texts = sorted(TEXT_DIR.glob("page_*.txt"), key=lambda p: p.name)
    if not texts:
        raise SystemExit("No extracted text files found.")

    sections: dict[str, str] = {}
    order: list[str] = []
    pages_scanned = 0

    for tp in texts:
        pages_scanned += 1
        raw = tp.read_text(encoding="utf-8")
        for num, body in split_sections(raw):
            trimmed = trim_annotations(body)
            # Require real words, not TOC fragments (mostly numbers/dots).
            if len(re.findall(r"[A-Za-z]{3,}", trimmed)) < 5:
                continue
            if num not in sections:
                sections[num] = trimmed
                order.append(num)

    payload = []
    for num in order:
        payload.append(
            {
                "sectionNumber": num,
                "text": sections[num],
                "source": "pdf: California Family Code Annotated (Blumberg)",
            }
        )

    result = {
        "metadata": {
            "source": "California Family Code Annotated (Grace Ganz Blumberg, 2020 Desktop Edition)",
            "extracted_from": "92 split PDFs via PyMuPDF",
            "pages_scanned": pages_scanned,
            "sections_extracted": len(payload),
        },
        "sections": payload,
    }
    OUT_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Extracted {len(payload)} Family Code sections -> {OUT_FILE}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
01_extract_pdf_text.py
----------------------
Extract raw text from every "California Family Code Annotated" PDF in the
repo into pdf_text/page_NNN.txt (one file per source PDF, in numerical order).

Run:  python3 01_extract_pdf_text.py
"""
from __future__ import annotations
import re
import fitz  # PyMuPDF
from pathlib import Path

REPO = Path.cwd()
OUT_DIR = REPO / "pdf_text"
OUT_DIR.mkdir(exist_ok=True)

# Match the numbered split PDFs, e.g. "...-1.pdf" .. "...-92.pdf"
PDF_RE = re.compile(r"^(.*?)(\d+)\.pdf$")


def collect_pdfs() -> list[tuple[int, Path]]:
    found = []
    for p in REPO.glob("*.pdf"):
        m = PDF_RE.match(p.name)
        if m:
            found.append((int(m.group(2)), p))
    found.sort(key=lambda x: x[0])
    return found


def main() -> None:
    pdfs = collect_pdfs()
    if not pdfs:
        raise SystemExit("No numbered PDFs found in repo root.")
    print(f"Found {len(pdfs)} PDFs")

    for num, path in pdfs:
        doc = fitz.open(path)
        parts = []
        for page in doc:
            parts.append(page.get_text())
        doc.close()
        text = "\n".join(parts)
        out = OUT_DIR / f"page_{num:03d}.txt"
        out.write_text(text, encoding="utf-8")
        print(f"  [{num:03d}] {path.name} -> {out.name} ({len(text)} chars)")

    print(f"\nDone. Extracted text written to {OUT_DIR}/")


if __name__ == "__main__":
    main()

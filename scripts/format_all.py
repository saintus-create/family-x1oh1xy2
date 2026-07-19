#!/usr/bin/env python3
"""Format all Fern docs files consistently.

- Strip trailing whitespace
- Normalize blank lines in MDX (max 2 consecutive)
- Ensure consistent frontmatter spacing
- Normalize YAML indentation
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path.cwd()
PAGES_DIR = REPO / "fern" / "docs" / "pages"


def strip_trailing(text: str) -> str:
    return re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)


def normalize_blanks(text: str, max_blank: int = 2) -> str:
    text = re.sub(r"\n{4,}", "\n" * max_blank, text)
    return text


def format_mdx(text: str) -> str:
    text = strip_trailing(text)
    text = normalize_blanks(text)
    parts = text.split("\n---\n", 1)
    if len(parts) == 2:
        fm, body = parts
        fm = strip_trailing(fm)
        fm = normalize_blanks(fm, max_blank=1)
        body = strip_trailing(body)
        body = normalize_blanks(body)
        text = fm + "\n---\n" + body
    return text.strip() + "\n"


def format_yaml(text: str) -> str:
    text = strip_trailing(text)
    text = normalize_blanks(text, max_blank=1)
    return text.strip() + "\n"


def main() -> int:
    # Format all MDX pages
    for mdx in PAGES_DIR.glob("*.mdx"):
        mdx.write_text(format_mdx(mdx.read_text(encoding="utf-8")), encoding="utf-8")
        print(f"formatted: {mdx.name}")

    # Format docs.yml
    docs_yml = REPO / "fern" / "docs.yml"
    if docs_yml.exists():
        docs_yml.write_text(format_yaml(docs_yml.read_text(encoding="utf-8")), encoding="utf-8")
        print("formatted: docs.yml")

    # Format styles.css
    css = REPO / "fern" / "styles.css"
    if css.exists():
        css.write_text(format_css(css.read_text(encoding="utf-8")), encoding="utf-8")
        print("formatted: styles.css")

    print("done.")
    return 0


def format_css(text: str) -> str:
    text = strip_trailing(text)
    text = normalize_blanks(text, max_blank=1)
    return text.strip() + "\n"


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
04_build_pages.py
-----------------
Rebuild the Fern docs site from the extracted Family Code data.

Emits clean Markdown so Fern's built-in theme handles fonts, spacing,
TOC sidebar, and responsive layout automatically.

Run:  python3 04_build_pages.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path.cwd()
PAGES_DIR = REPO / "fern" / "docs" / "pages"
SECTIONS_FILE = REPO / "family_code_sections.json"
XREF_FILE = REPO / "fam_cross_references.json"

DIVISIONS = {
    1: ("Preliminary Provisions and Definitions", "preliminary-provisions"),
    2: ("General Provisions", "marriage"),
    "2.5": ("Domestic Partner Registration", "division-2.5-domestic-partners"),
    3: ("Marriage", "division-3-marriage"),
    4: ("Rights and Obligations During Marriage", "division-4-rights-during-marriage"),
    5: ("Conciliation Proceedings", "division-5-conciliation"),
    6: ("Nullity, Dissolution, and Legal Separation", "division-6-dissolution"),
    7: ("Division of Property", "division-7-property"),
    8: ("Custody of Children", "division-8-custody"),
    9: ("Support", "division-9-support"),
    10: ("Prevention of Domestic Violence", "division-10-domestic-violence"),
    11: ("Minors", "division-11-minors"),
    12: ("Parent and Child Relationship", "division-12-parent-child"),
    13: ("Adoption", "division-13-adoption"),
    14: ("Family Law Facilitator Act", "division-14-family-law-facilitator"),
    17: ("Support Services", "division-17-support-services"),
    20: ("Pilot Projects", "division-20-pilot-projects"),
}


def division_of(section_number: str) -> float:
    try:
        n = float(section_number)
    except ValueError:
        return 0.0
    if n < 200:
        return 1
    if n < 297:
        return 2
    if 297 <= n <= 299.6:
        return 2.5
    if n < 400:
        return 2
    if n < 700:
        return 3
    if n < 1104:
        return 4
    if n < 1800:
        return 4
    if n < 2000:
        return 5
    if n < 2500:
        return 6
    if n < 3000:
        return 7
    if n < 3500:
        return 8
    if n < 3600:
        return 9
    if n < 3700:
        return 9
    if n < 4000:
        return 9
    if n < 5000:
        return 9
    if n < 6500:
        return 10
    if n < 7100:
        return 11
    if n < 7500:
        return 12
    if n < 8600:
        return 12
    if n < 10000:
        return 13
    if n < 17000:
        return 14
    if n < 20000:
        return 17
    return 20


def build_pages(sections: list[dict]) -> dict[float, list[dict]]:
    by_div: dict[float, list[dict]] = {}
    for s in sections:
        by_div.setdefault(division_of(s["sectionNumber"]), []).append(s)
    for div in by_div:
        by_div[div].sort(key=lambda x: float(x["sectionNumber"]))
    return by_div


def clean_text(text: str) -> str:
    """Prepare raw statute text for Markdown rendering.

    - Fix OCR hyphenation artifacts ("communi- ty" -> "community").
    - Join soft line breaks (PDF extraction artifacts) into sentences.
    - Collapse multiple blank lines.
    """
    text = re.sub(r"\b(\w+)-\s+", r"\1", text)
    text = re.sub(r"([A-Za-z0-9,;:])\s*\n(?=[A-Za-z0-9])", r"\1 ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Drop bare section-number TOC fragments ("3002." alone on a line) and
    # the one-line description that follows — index entries leaked from the
    # annotated source, not statute text.
    text = re.sub(r"^\s*\d{3,4}\.\s*$\n(?:[A-Z][^\n]*\n)?", "", text, flags=re.M)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def render_page(div_key, div_info, secs: list[dict]) -> str:
    title = div_info[0]
    slug = div_info[1]
    lines = [
        "---",
        f'title: "Division {div_key}: {title}"',
        f"slug: {slug}",
        "---",
        "",
        f"# {title}",
        "",
        f"**Division {div_key}** — California Family Code",
        "",
    ]
    if not secs:
        lines += ["_No sections extracted for this division yet._", ""]
        return "\n".join(lines)

    for s in secs:
        sec_url = (
            "https://leginfo.legislature.ca.gov/faces/codes_displaySection"
            f".xhtml?lawCode=FAM&sectionNum={s['sectionNumber']}."
        )
        lines += [
            f"### [Section {s['sectionNumber']}]({sec_url})",
            "",
            clean_text(s["text"]),
            "",
            "",
        ]
    return "\n".join(lines)


def inject_cross_refs(content: str, xrefs: list[dict], div_sections: set[str]) -> str:
    """Wrap bare 'Section X' mentions with links."""
    present = {m.group(1) for m in re.finditer(r"^### \[Section (\S+)", content, re.M)}
    if not present:
        return content

    links: set[tuple[str, str]] = set()
    for r in xrefs:
        m = re.search(r"(\d+(?:\.\d+)?)", r.get("fam_section", ""))
        if not m or m.group(1) not in present:
            continue
        url = r.get("referenced_url")
        frag = r.get("referenced_section", "").strip()
        if not url or not frag:
            continue
        links.add((frag, url))

    for frag, url in sorted(links, key=lambda x: -len(x[0])):
        if f'href="{url}"' in content:
            continue
        pattern = re.compile(
            r"(?<![={\"<])(?<!href=\")\b" + re.escape(frag) + r"\b(?![}>])"
        )
        content = pattern.sub(
            lambda mm, u=url: f'<a href="{u}">{mm.group(0)}</a>', content
        )
    return content


def style_emphasis(content: str) -> str:
    """Replace '* * *' omitted-text markers with a simple callout."""
    return content.replace(
        "* * *",
        "<aside class=\"omit-note\">[text omitted in source]</aside>",
    )


def main() -> None:
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    data = json.loads(SECTIONS_FILE.read_text(encoding="utf-8"))
    sections = data["sections"]
    by_div = build_pages(sections)

    xrefs = []
    if XREF_FILE.exists():
        xrefs = json.loads(XREF_FILE.read_text(encoding="utf-8")).get("cross_references", [])

    generated = []
    div_sections = {s["sectionNumber"] for s in sections}

    for div_key, div_info in DIVISIONS.items():
        secs = by_div.get(float(div_key), [])
        content = render_page(div_key, div_info, secs)
        if xrefs:
            content = inject_cross_refs(content, xrefs, div_sections)
        content = style_emphasis(content)
        (PAGES_DIR / f"{div_info[1]}.mdx").write_text(content, encoding="utf-8")
        generated.append((div_key, div_info[1], len(secs)))
        print(f"page: {div_info[1]}.mdx ({len(secs)} sections)")

    # Home page
    home = [
        "---",
        "title: California Family Code",
        "slug: home",
        "layout: custom",
        "no-image-zoom: true",
        "---",
        "",
        "# California Family Code",
        "",
        "The complete California Family Code, presented verbatim.",
        "",
        "## Divisions",
        "",
    ]
    for div_key in sorted(DIVISIONS.keys(), key=lambda k: float(k)):
        title, slug = DIVISIONS[div_key]
        home.append(f"- [Division {div_key}: {title}](/{slug})")
    home += [
        "",
        "---",
        "",
        "*Source: California Family Code Annotated (Grace Ganz Blumberg, 2020 Desktop Edition), derived from the [California Legislative Information](https://leginfo.legislature.ca.gov/faces/codesTOCSelected.xhtml?tocCode=FAM) Family Code.*",
        "",
    ]
    (PAGES_DIR / "home.mdx").write_text("\n".join(home), encoding="utf-8")
    print("page: home.mdx")

    total = sum(g[2] for g in generated)
    print(f"\nDone. {len(generated)} division pages, {total} sections total.")


if __name__ == "__main__":
    main()

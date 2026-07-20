#!/usr/bin/env python3
"""
04_build_pages.py
-----------------
Generate one page per section (paginated), plus one index page per division.

Division pages: 17 index pages listing all sections with links
Section pages: 3420 individual pages, one per section

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
CASE_MAP_FILE = REPO / "_section_case_map.json"

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
    text = re.sub(r"\b(\w+)-\s+", r"\1", text)
    text = re.sub(r"([A-Za-z0-9,;:])\s*\n(?=[A-Za-z0-9])", r"\1 ", text)
    text = re.sub(r"\b[A-Z]{3,}(?:\s+[A-Z]{3,})*\b", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"^\s*\d{3,4}\.\s*$\n(?:[A-Z][^\n]*\n)?", "", text, flags=re.M)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\*\s*\*\s*", " ", text)
    text = re.sub(r"\*\s*x\s*\*\s*", "", text)
    text = re.sub(r"\*\.\s*", "", text)
    # Strip any remaining italic markers: *word*, * * *, _word_, etc.
    text = re.sub(r"\*{1,3}\s*", "", text)
    text = re.sub(r"_([^_\n]+)_", r"\1", text)
    return text.strip()


def section_url(section_number: str) -> str:
    return (
        "https://leginfo.legislature.ca.gov/faces/codes_displaySection"
        f".xhtml?lawCode=FAM&sectionNum={section_number}."
    )


def render_division_page(div_key, div_info, secs: list[dict]) -> str:
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
        "## Sections",
        "",
    ]
    for s in secs:
        sec_slug = f"{slug}-section-{s['sectionNumber']}"
        lines.append(f"- [Sec. {s['sectionNumber']}](/{sec_slug})")
    lines += [
        "",
        '<div class="source-note">',
        "",
        "**Source:** California Family Code Annotated (Grace Ganz Blumberg, 2020 Desktop Edition).",
        "",
        "</div>",
    ]
    return "\n".join(lines)


def render_section_page(div_key, div_info, s: dict) -> str:
    title = div_info[0]
    slug = div_info[1]
    sec_slug = f"{slug}-section-{s['sectionNumber']}"
    sec_url = section_url(s["sectionNumber"])
    body = clean_text(s["text"])
    lines = [
        "---",
        f'title: "Section {s["sectionNumber"]} — {title}"',
        f"slug: {sec_slug}",
        "---",
        "",
        f"# {title}",
        "",
        f"## Section {s['sectionNumber']}",
        "",
        f'<div class="source-note">Back to <a href="/{slug}">Division {div_key}: {title}</a></div>',
        "",
        body,
        "",
        '<div class="source-note">', "",
        f"**Source:** California Family Code Annotated (Grace Ganz Blumberg, 2020 Desktop Edition). "
        f"[View on California Legislative Information]({sec_url}).",
        "",
        '</div>',
    ]
    return "\n".join(lines)


def inject_cross_refs(content: str, xrefs: list[dict], div_sections: set[str]) -> str:
    present = {m.group(1) for m in re.finditer(r"^## Section (\S+)", content, re.M)}
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
            r"(?<![={\"<])(?<!href=\")(?<!##\s)\b" + re.escape(frag) + r"\b(?![}>])"
        )
        content = pattern.sub(
            lambda mm, u=url: f'<a href="{u}">{mm.group(0)}</a>', content
        )
    return content


def style_emphasis(content: str) -> str:
    return content.replace(
        "* * *",
        "<aside class=\"callout\">[text omitted in source]</aside>",
    )


def inject_case_callouts(content: str, section_number: str, case_map: dict) -> str:
    cases = case_map.get(section_number, [])
    if not cases:
        return content
    
    callouts = []
    for case in sorted(cases, key=lambda c: c['name']):
        name = case['name']
        year = case['year']
        citation = case['citation']
        description = case.get('description', '')
        # Remove case name and citation from description
        desc = re.sub(r'^' + re.escape(name) + r'\s*\(\d{4}\)\s*' + re.escape(citation) + r'\s*', '', description).strip()
        desc = re.sub(r'\s+', ' ', desc).strip()
        if len(desc) > 500:
            desc = desc[:497] + "..."
        
        statutes = case.get('statutes', '')
        
        callout = f'<div class="case-callout">\n'
        callout += f'<strong>Case Annotation: {name} ({year})</strong>\n\n'
        callout += f'**Citation:** {citation}\n\n'
        if desc:
            callout += f'{desc}\n\n'
        if statutes:
            callout += f'**Statutes:** {statutes}\n'
        callout += '</div>\n'
        callouts.append(callout)
    
    # Insert before the source-note div
    if '<div class="source-note">' in content:
        content = content.replace('<div class="source-note">', '\n'.join(callouts) + '\n<div class="source-note">')
    else:
        content += '\n'.join(callouts)
    
    return content


def main() -> None:
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    data = json.loads(SECTIONS_FILE.read_text(encoding="utf-8"))
    sections = data["sections"]
    by_div = build_pages(sections)

    xrefs = []
    if XREF_FILE.exists():
        xrefs = json.loads(XREF_FILE.read_text(encoding="utf-8")).get("cross_references", [])

    case_map = {}
    if CASE_MAP_FILE.exists():
        case_map = json.loads(CASE_MAP_FILE.read_text(encoding="utf-8"))

    generated = 0
    div_sections = {s["sectionNumber"] for s in sections}

    for div_key, div_info in DIVISIONS.items():
        secs = by_div.get(float(div_key), [])
        if not secs:
            continue

        # Division index page
        index_content = render_division_page(div_key, div_info, secs)
        (PAGES_DIR / f"{div_info[1]}.mdx").write_text(index_content, encoding="utf-8")
        print(f"index: {div_info[1]}.mdx ({len(secs)} sections)")
        generated += 1

        # One page per section
        for s in secs:
            content = render_section_page(div_key, div_info, s)
            if xrefs:
                content = inject_cross_refs(content, xrefs, div_sections)
            content = style_emphasis(content)
            content = inject_case_callouts(content, s["sectionNumber"], case_map)
            sec_slug = f"{div_info[1]}-section-{s['sectionNumber']}"
            (PAGES_DIR / f"{sec_slug}.mdx").write_text(content, encoding="utf-8")
            generated += 1

    # Home page
    home = [
        "---",
        "title: California Family Code",
        "slug: home",
        "layout: custom",
        "no-image-zoom: true",
        "---",
        "",
        '<div class="hero">',
        "",
        "# California Family Code",
        "",
        "The complete California Family Code, presented verbatim.",
        "",
        '<div class="search-bridge">',
        '<input type="search" placeholder="Search sections..." />',
        "</div>",
        "",
        "</div>",
        "",
        '<div class="division-grid">',
        "",
    ]
    for div_key in sorted(DIVISIONS.keys(), key=lambda k: float(k)):
        title, slug = DIVISIONS[div_key]
        home.append(
            f'<a class="division-card" href="/{slug}">\n'
            f'  <div class="division-card-title">{title}</div>\n'
            f'</a>'
        )
    home += [
        "</div>",
        "",
        '<div class="source-note">',
        "",
        "**Source:** California Family Code Annotated (Grace Ganz Blumberg, 2020 Desktop Edition).",
        "",
        "</div>",
        "",
    ]
    (PAGES_DIR / "home.mdx").write_text("\n".join(home), encoding="utf-8")
    print(f"page: home.mdx")
    print(f"\nDone. {generated} pages total ({len(DIVISIONS)} division indexes + {sum(len(by_div.get(float(k), [])) for k in DIVISIONS)} sections).")


if __name__ == "__main__":
    main()

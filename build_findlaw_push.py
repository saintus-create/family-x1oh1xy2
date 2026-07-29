#!/usr/bin/env python3
"""
build_findlaw_push.py
=====================
Reads leginfo_sections.json (written by fetch_leginfo_fast.mjs),
merges text into family_code_sections_full.json, then rebuilds every
MDX page with FindLaw-style navigation and pushes to GitHub per division.

FindLaw structure:
  Sidebar: Division (collapsed) → Chapter/Part (collapsed) → § Section
  Section page: breadcrumb + clean statute text + prev/next + source link
  Division page: Part/Chapter table with section counts + links
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import textwrap
from collections import defaultdict
from pathlib import Path

ROOT       = Path(__file__).resolve().parent
PAGES_DIR  = ROOT / "fern" / "docs" / "pages"
CASES_DIR  = PAGES_DIR / "case-annotations"
DOCS_YML   = ROOT / "fern" / "docs.yml"
LEGINFO_CACHE  = ROOT / "leginfo_sections.json"
SECTIONS_FULL  = ROOT / "family_code_sections_full.json"

sys.path.insert(0, str(ROOT))
import unify_family_docs as u

# ──────────────────────────────────────────────────────────────────────────────
# STEP 1 — merge leginfo cache into family_code_sections_full.json
# ──────────────────────────────────────────────────────────────────────────────

def merge_cache():
    if not LEGINFO_CACHE.exists():
        print("  No leginfo_sections.json found — skipping merge.")
        return
    cache = json.loads(LEGINFO_CACHE.read_text())
    raw   = json.loads(SECTIONS_FULL.read_text())
    is_obj = isinstance(raw, dict)
    secs   = raw.get("sections", []) if is_obj else raw

    sec_map: dict[str, dict] = {}
    for s in secs:
        num = str(s.get("sectionNumber", "")).strip()
        if num:
            sec_map[num] = s

    updated = added = 0
    for num, res in cache.items():
        txt = (res.get("text") or "").strip()
        if not txt:
            continue
        if num in sec_map:
            sec_map[num]["text"]       = txt
            sec_map[num]["source_url"] = res.get("source_url", sec_map[num].get("source_url", ""))
            updated += 1
        else:
            sec_map[num] = {"sectionNumber": num, "text": txt,
                            "source_url": res.get("source_url", u._leginfo_url(num))}
            added += 1

    def _sort(s: dict):
        n = str(s.get("sectionNumber", "0"))
        try:
            p = n.split(".")
            return (int(p[0]), int(p[1]) if len(p) > 1 else 0)
        except Exception:
            return (999999, 0)

    new_secs = sorted(sec_map.values(), key=_sort)
    if is_obj:
        raw["sections"] = new_secs
        SECTIONS_FULL.write_text(json.dumps(raw, indent=2, ensure_ascii=False))
    else:
        SECTIONS_FULL.write_text(json.dumps(new_secs, indent=2, ensure_ascii=False))

    print(f"  Merged: {updated} updated, {added} added from leginfo cache.")


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _sec_float(s: str) -> float:
    try:
        return float(s)
    except ValueError:
        try:
            parts = s.split(".")
            return float(parts[0]) + float("0." + parts[1]) * 0.001 if len(parts) > 1 else float(parts[0])
        except Exception:
            return 999999.0


def _find_chapter(sec_num: str, div_info: dict) -> dict | None:
    n = _sec_float(sec_num)
    for ch in div_info.get("chapters", []):
        if ch["start"] <= n <= ch["end"]:
            return ch
    return None


def _section_title_short(sec_num: str, registry: dict) -> str:
    """Return a short title for a section (first meaningful line of text)."""
    sec = registry.get(sec_num, {})
    text = (sec.get("text") or "").strip()
    if not text:
        return ""
    cleaned = u._clean_text(text)
    return u._extract_section_title(cleaned, sec_num) or ""


# ──────────────────────────────────────────────────────────────────────────────
# STEP 2 — FindLaw-style section page
# ──────────────────────────────────────────────────────────────────────────────

def generate_section_page_findlaw(
    sec_num: str,
    section: dict,
    div_info: dict,
    cases: list,
    xrefs: list,
    prev_sec: str | None = None,
    next_sec: str | None = None,
) -> str:
    div_title  = div_info["title"]
    div_slug   = div_info["slug"]
    div_number = div_info["number"]
    div_prefix = div_info["section_prefix"]
    sec_slug   = u._section_slug(div_prefix, sec_num)

    raw_text       = section.get("text", "")
    cleaned_text   = u._clean_text(raw_text)
    sec_title      = u._extract_section_title(cleaned_text, sec_num)
    formatted_text = u._format_statute_text(raw_text)
    source_url     = section.get("source_url") or u._leginfo_url(sec_num)

    chapter = _find_chapter(sec_num, div_info)
    ch_title = chapter["title"] if chapter else ""

    fm_title = f"{sec_num}. {sec_title}" if sec_title else f"Section {sec_num}"
    description = sec_title if sec_title else f"California Family Code section {sec_num}"

    parts = []

    # ── Front-matter ──────────────────────────────────────────────────────────
    parts.append(
        f'---\n'
        f'title: "{fm_title}"\n'
        f'description: "{description[:160]}"\n'
        f'slug: {sec_slug}\n'
        f'---\n'
    )

    # ── Breadcrumb (FindLaw-style) ─────────────────────────────────────────────
    crumbs = [
        f'<a href="/home">California Family Code</a>',
        f'<a href="/{div_slug}">Division {div_number}</a>',
    ]
    if ch_title:
        crumbs.append(f'<span>{ch_title}</span>')
    crumbs.append(f'<span>§ {sec_num}</span>')

    parts.append(
        '<nav class="fl-breadcrumb">\n'
        + ' <span class="fl-crumb-sep">/</span>\n'.join(f'  {c}' for c in crumbs)
        + '\n</nav>\n'
    )

    # ── Section heading ────────────────────────────────────────────────────────
    if sec_title:
        parts.append(f"# § {sec_num} — {sec_title}\n")
    else:
        parts.append(f"# California Family Code § {sec_num}\n")

    # ── Statute text ───────────────────────────────────────────────────────────
    if formatted_text:
        parts.append(formatted_text)
        parts.append("")

    # ── Case callouts ──────────────────────────────────────────────────────────
    if cases:
        parts.append('<div class="case-annotations">\n')
        parts.append("## Case Annotations\n")
        for case in cases[:10]:
            parts.append(u._render_case_callout(case))
            parts.append("")
        parts.append("</div>\n")

    # ── Cross-references ───────────────────────────────────────────────────────
    xref_block = u._render_cross_refs(xrefs)
    if xref_block:
        parts.append(xref_block)
        parts.append("")

    # ── Prev / Next nav (FindLaw-style) ────────────────────────────────────────
    nav_parts = []
    if prev_sec:
        prev_slug = u._section_slug(div_prefix, prev_sec)
        nav_parts.append(f'<a class="fl-nav-btn fl-nav-prev" href="/{prev_slug}">← § {prev_sec}</a>')
    if next_sec:
        next_slug = u._section_slug(div_prefix, next_sec)
        nav_parts.append(f'<a class="fl-nav-btn fl-nav-next" href="/{next_slug}">§ {next_sec} →</a>')

    if nav_parts:
        parts.append('<div class="fl-section-nav">\n' + "\n".join(nav_parts) + "\n</div>\n")

    # ── Source note ────────────────────────────────────────────────────────────
    parts.append(
        f'<div class="source-note">\n\n'
        f'**Source:** California Family Code · '
        f'[View on California Legislative Information]({source_url})\n\n'
        f'</div>\n'
    )

    return "\n".join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# STEP 3 — FindLaw-style division index page
# ──────────────────────────────────────────────────────────────────────────────

def generate_division_index_findlaw(
    div_slug: str,
    div_info: dict,
    div_sections: list[str],
    registry: dict,
) -> str:
    div_number = div_info["number"]
    div_title  = div_info["title"]
    chapters   = div_info.get("chapters", [])

    num_display = "Preliminary" if div_number == "Preliminary" else f"Division {div_number}"

    parts = []
    parts.append(
        f'---\n'
        f'title: "{num_display} — {div_title}"\n'
        f'description: "California Family Code {num_display}: {div_title}. '
        f'Sections {div_sections[0] if div_sections else "—"}–{div_sections[-1] if div_sections else "—"}."\n'
        f'slug: {div_slug}\n'
        f'---\n'
    )

    # ── Breadcrumb ─────────────────────────────────────────────────────────────
    parts.append(
        '<nav class="fl-breadcrumb">\n'
        '  <a href="/home">California Family Code</a>\n'
        f'  <span class="fl-crumb-sep">/</span>\n'
        f'  <span>{num_display}</span>\n'
        '</nav>\n'
    )

    # ── Title ──────────────────────────────────────────────────────────────────
    parts.append(f"# {num_display} — {div_title}\n")

    if div_sections:
        sec_range = f"§§ {div_sections[0]}–{div_sections[-1]}" if len(div_sections) > 1 else f"§ {div_sections[0]}"
        parts.append(f"**California Family Code** · {sec_range} · {len(div_sections)} sections\n")

    # ── Chapter/Part table ─────────────────────────────────────────────────────
    if chapters and div_sections:
        parts.append('<div class="fl-chapter-list">\n')

        unassigned = list(div_sections)  # track what's not put in a chapter

        for ch in chapters:
            ch_secs = [s for s in div_sections
                       if ch["start"] <= _sec_float(s) <= ch["end"]]
            if not ch_secs:
                continue
            for s in ch_secs:
                if s in unassigned:
                    unassigned.remove(s)

            ch_range = (f"§§ {ch_secs[0]}–{ch_secs[-1]}"
                        if len(ch_secs) > 1 else f"§ {ch_secs[0]}")

            parts.append(f'<div class="fl-chapter-block">\n')
            parts.append(f'<h3 class="fl-chapter-title">{ch["title"]}</h3>\n')
            parts.append(f'<p class="fl-chapter-range">{ch_range} · {len(ch_secs)} sections</p>\n')
            parts.append('<ul class="fl-section-list">\n')

            for sec_num in ch_secs:
                slug  = u._section_slug(div_info["section_prefix"], sec_num)
                title = _section_title_short(sec_num, registry)
                label = f"§ {sec_num}" + (f" — {title}" if title else "")
                parts.append(f'<li><a href="/{slug}">{label}</a></li>\n')

            parts.append('</ul>\n</div>\n')

        # Sections not in any chapter
        if unassigned:
            parts.append('<div class="fl-chapter-block">\n')
            parts.append('<h3 class="fl-chapter-title">Other Provisions</h3>\n')
            parts.append('<ul class="fl-section-list">\n')
            for sec_num in unassigned:
                slug  = u._section_slug(div_info["section_prefix"], sec_num)
                title = _section_title_short(sec_num, registry)
                label = f"§ {sec_num}" + (f" — {title}" if title else "")
                parts.append(f'<li><a href="/{slug}">{label}</a></li>\n')
            parts.append('</ul>\n</div>\n')

        parts.append('</div>\n')

    elif div_sections:
        # No chapter structure — flat list
        parts.append('<ul class="fl-section-list">\n')
        for sec_num in div_sections:
            slug  = u._section_slug(div_info["section_prefix"], sec_num)
            title = _section_title_short(sec_num, registry)
            label = f"§ {sec_num}" + (f" — {title}" if title else "")
            parts.append(f'<li><a href="/{slug}">{label}</a></li>\n')
        parts.append('</ul>\n')

    # ── Source note ────────────────────────────────────────────────────────────
    toc_url = "https://leginfo.legislature.ca.gov/faces/codesTOCSelected.xhtml?tocCode=FAM"
    parts.append(
        f'<div class="source-note">\n\n'
        f'**Source:** California Family Code · '
        f'[California Legislative Information]({toc_url})\n\n'
        f'</div>\n'
    )

    return "\n".join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# STEP 4 — FindLaw-style docs.yml
# ──────────────────────────────────────────────────────────────────────────────

_DIV_LABELS = {
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
    "division-10-domestic-violence":     "Domestic Violence Prevention",
    "division-11-minors":                "Minors",
    "division-12-parent-child":          "Parent and Child",
    "division-13-adoption":              "Adoption",
    "division-14-family-law-facilitator":"Family Law Facilitator",
    "division-17-support-services":      "Support Services",
    "division-20-pilot-projects":        "Pilot Projects",
}
_CASE_LABELS = {
    "abuse-definition":               'What Is "Abuse"',
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

I = "  "   # 2-space indent unit

def _yml_line(depth: int, text: str) -> str:
    return I * depth + text

def generate_docs_yml_findlaw(div_sections_map: dict) -> str:
    """
    FindLaw hierarchy:
      Divisions
        ↳ Division N (collapsed)
             ↳ Overview page
             ↳ Chapter/Part (collapsed)
                  ↳ § individual section pages
    """
    lines = [
        "# yaml-language-server: $schema=https://schema.buildwithfern.dev/docs-yml.json",
        "",
        "instances:",
        "  - url: https://family.docs.buildwithfern.com",
        "    edit-this-page:",
        "      github:",
        "        owner: saintus-create",
        "        repo: family-x1oh1xy2",
        "        branch: main",
        "",
        "title: California Family Code",
        "",
        "layout:",
        "  searchbar-placement: header",
        "  page-width: wide",
        "  tabs-placement: header",
        "",
        "tabs:",
        "  code:",
        "    display-name: Family Code",
        "    icon: docs/assets/icon-circle.svg",
        "",
        "navigation:",
        "  - tab: code",
        "    layout:",
        "",
        "      - section: Overview",
        "        contents:",
        "          - page: Home",
        "            path: docs/pages/home.mdx",
        "",
        "      - section: Divisions",
        "        contents:",
    ]

    for div_slug, div_info in u.DIVISION_STRUCTURE.items():
        label    = _DIV_LABELS.get(div_slug, div_info["title"])
        div_num  = div_info["number"]
        secs     = div_sections_map.get(div_slug, [])
        chapters = div_info.get("chapters", [])
        prefix   = div_info["section_prefix"]

        # Division section (collapsed)
        lines += [
            f"          - section: \"{label}\"",
            f"            collapsed: true",
            f"            contents:",
            f"              - page: Overview",
            f"                path: docs/pages/{div_slug}.mdx",
        ]

        if chapters and secs:
            seen = set()
            for ch in chapters:
                ch_secs = [s for s in secs
                           if ch["start"] <= _sec_float(s) <= ch["end"]]
                if not ch_secs:
                    continue
                for s in ch_secs:
                    seen.add(s)

                ch_range = (f"§§ {ch_secs[0]}-{ch_secs[-1]}"
                            if len(ch_secs) > 1 else f"§ {ch_secs[0]}")
                ch_label = f"{ch['title']} [{ch_range}]"

                lines += [
                    f"              - section: \"{ch_label}\"",
                    f"                collapsed: true",
                    f"                contents:",
                ]
                for sec_num in ch_secs:
                    slug = u._section_slug(prefix, sec_num)
                    lines += [
                        f"                  - page: \"\u00a7 {sec_num}\"",
                        f"                    path: docs/pages/{slug}.mdx",
                    ]

            # Sections outside all chapters
            unassigned = [s for s in secs if s not in seen]
            if unassigned:
                lines += [
                    f"              - section: \"Other Provisions\"",
                    f"                collapsed: true",
                    f"                contents:",
                ]
                for sec_num in unassigned:
                    slug = u._section_slug(prefix, sec_num)
                    lines += [
                        f"                  - page: \"\u00a7 {sec_num}\"",
                        f"                    path: docs/pages/{slug}.mdx",
                    ]
        elif secs:
            for sec_num in secs:
                slug = u._section_slug(prefix, sec_num)
                lines += [
                    f"              - page: \"\u00a7 {sec_num}\"",
                    f"                path: docs/pages/{slug}.mdx",
                ]

    # Case annotations
    lines += [
        "",
        "      - section: Case Annotations",
        "        contents:",
    ]
    for long_title, slug, _ in u.CASE_ANNOTATION_PAGES:
        label = _CASE_LABELS.get(slug, long_title.split(". ", 1)[-1][:55])
        lines += [
            f"          - page: \"{label}\"",
            f"            path: docs/pages/case-annotations/{slug}.mdx",
        ]

    # Colors + assets
    lines += [
        "",
        "colors:",
        "  accent-primary:",
        '    light: "#1a56db"',
        '    dark:  "#4da6ff"',
        "  background:",
        '    light: "#ffffff"',
        '    dark:  "#0a0a0a"',
        "",
        "css:",
        "  - styles.css",
        "",
    ]

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# STEP 5 — Git helpers
# ──────────────────────────────────────────────────────────────────────────────

def git_push(message: str):
    subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
    diff = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if not diff.stdout.strip():
        print("    (no changes)")
        return
    subprocess.run(["git", "commit", "-m", message], cwd=ROOT, check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
    n = len(diff.stdout.strip().splitlines())
    print(f"    ✓ pushed  '{message}'  ({n} files)")


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main():
    subprocess.run(["git", "config", "user.email", "bot@family-code-docs.com"], cwd=ROOT)
    subprocess.run(["git", "config", "user.name", "FamilyCodeBot"], cwd=ROOT)

    print("=" * 62)
    print("  California Family Code — Build (FindLaw Nav) + Push")
    print("=" * 62)

    # ── 1. Merge leginfo cache ─────────────────────────────────────────────────
    print("\n[1] Merging leginfo cache…")
    merge_cache()

    # ── 2. Load data ───────────────────────────────────────────────────────────
    print("\n[2] Loading registry + cases + xrefs…")
    registry = u.build_section_registry()
    case_map = u.build_case_map()
    xref_map = u.build_cross_ref_map()
    all_cases = u.load_json(u.CASE_ENTRIES_JSON, [])
    print(f"    Registry: {len(registry)} sections")

    # ── 3. Assign sections to divisions ────────────────────────────────────────
    print("\n[3] Assigning sections to divisions…")
    existing_file_map: dict[str, str] = {}
    for f in PAGES_DIR.glob("*.mdx"):
        m = re.match(r"^(.+)-section-([\d.]+)$", f.stem)
        if m:
            sec, prefix = m.group(2), m.group(1)
            # Prefer longer/more-specific prefix (e.g. "division-2.5-domestic-partners"
            # beats "marriage" for the shared § 297–299 range)
            if sec not in existing_file_map or len(prefix) > len(existing_file_map[sec]):
                existing_file_map[sec] = prefix

    div_sections_map: dict[str, list[str]] = defaultdict(list)
    for sec_num in registry:
        if sec_num in existing_file_map:
            prefix = existing_file_map[sec_num]
            for slug, info in u.DIVISION_STRUCTURE.items():
                if info["section_prefix"] == prefix:
                    div_sections_map[slug].append(sec_num)
                    break
            else:
                slug = u._assign_section_to_division(sec_num, registry)
                if slug:
                    div_sections_map[slug].append(sec_num)
        else:
            slug = u._assign_section_to_division(sec_num, registry)
            if slug:
                div_sections_map[slug].append(sec_num)

    for slug in div_sections_map:
        div_sections_map[slug] = sorted(
            set(div_sections_map[slug]), key=u._sec_num_sort_key
        )

    total = sum(len(v) for v in div_sections_map.values())
    print(f"    {total} sections across {len(div_sections_map)} divisions")

    # ── 4. Home page + case annotations ───────────────────────────────────────
    print("\n[4] Writing home + case annotation pages…")
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    CASES_DIR.mkdir(parents=True, exist_ok=True)

    home = u.generate_home_page()
    (PAGES_DIR / "home.mdx").write_text(home, encoding="utf-8")

    for title, slug, comp_sec in u.CASE_ANNOTATION_PAGES:
        content = u.generate_case_annotation_page(title, slug, comp_sec, all_cases)
        (CASES_DIR / f"{slug}.mdx").write_text(content, encoding="utf-8")

    # ── 5. Build each division + push ──────────────────────────────────────────
    print("\n[5] Building divisions…\n")
    for div_slug, div_info in u.DIVISION_STRUCTURE.items():
        secs = div_sections_map.get(div_slug, [])
        print(f"  {div_info['title']}  ({len(secs)} sections)", flush=True)

        # Section pages (with prev/next)
        for i, sec_num in enumerate(secs):
            section = registry.get(sec_num, {
                "sectionNumber": sec_num, "text": "",
                "source_url": u._leginfo_url(sec_num)
            })
            cases  = case_map.get(sec_num, [])
            xrefs  = xref_map.get(sec_num, [])
            prev_s = secs[i - 1] if i > 0 else None
            next_s = secs[i + 1] if i < len(secs) - 1 else None

            content = generate_section_page_findlaw(
                sec_num, section, div_info, cases, xrefs, prev_s, next_s
            )
            slug = u._section_slug(div_info["section_prefix"], sec_num)
            (PAGES_DIR / f"{slug}.mdx").write_text(content, encoding="utf-8")

        # Division index
        idx = generate_division_index_findlaw(div_slug, div_info, secs, registry)
        (PAGES_DIR / f"{div_slug}.mdx").write_text(idx, encoding="utf-8")

        # docs.yml (always regenerate full file so nav stays consistent)
        yml = generate_docs_yml_findlaw(div_sections_map)
        DOCS_YML.write_text(yml, encoding="utf-8")

        git_push(
            f"docs({div_info['number']}): {div_info['title']} — "
            f"{len(secs)} sections, FindLaw nav"
        )

    # ── 6. Final push: home + case annotations ─────────────────────────────────
    print("\n[6] Final push…")
    git_push("docs: home page + case annotations (FindLaw nav rebuild)")

    print("\n" + "=" * 62)
    print("  ✓  Done.")
    print("=" * 62)


if __name__ == "__main__":
    main()

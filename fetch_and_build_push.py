#!/usr/bin/env python3
"""
fetch_and_build_push.py
=======================
Master script:
  1. Collects all section numbers from MDX filenames + existing JSON.
  2. Fetches full statute text from leginfo.legislature.ca.gov in parallel.
  3. Merges fetched text into family_code_sections_full.json.
  4. Rebuilds every MDX page + division indexes + home page + docs.yml
     using functions from unify_family_docs.py.
  5. Commits and pushes to GitHub after each division.

Usage:
    python3 fetch_and_build_push.py
    python3 fetch_and_build_push.py --skip-fetch    # only rebuild + push
    python3 fetch_and_build_push.py --div division-10-domestic-violence
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install",
                           "requests", "beautifulsoup4", "-q"])
    import requests
    from bs4 import BeautifulSoup

ROOT        = Path(__file__).resolve().parent
PAGES_DIR   = ROOT / "fern" / "docs" / "pages"
CASES_DIR   = PAGES_DIR / "case-annotations"
SECTIONS_FULL  = ROOT / "family_code_sections_full.json"
LEGINFO_CACHE  = ROOT / "leginfo_sections.json"

LEGINFO_BASE = (
    "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml"
    "?lawCode=FAM&sectionNum={sec}."
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
MAX_WORKERS = 15


# ─── URL builder ──────────────────────────────────────────────────────────────

def leginfo_url(sec: str) -> str:
    from urllib.parse import quote
    return LEGINFO_BASE.format(sec=quote(sec, safe=""))


# ─── HTML parser ──────────────────────────────────────────────────────────────

def parse_leginfo_html(html: str, sec_num: str) -> str | None:
    """
    Extract clean statutory text from a leginfo section page.
    Strategy: find the <h6> heading for this section, then collect
    all <p> siblings that follow it in the same parent container.
    Falls back to full div text-extraction if h6 not found.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Strategy 1: find <h6><b>6203.  </b></h6> and collect following <p> tags
    bare = sec_num.strip().rstrip(".")
    for h6 in soup.find_all("h6"):
        h6_text = h6.get_text().strip().rstrip(". ")
        if h6_text == bare or h6_text == bare + ".":
            parent = h6.parent
            paras = []
            collecting = False
            for child in parent.children:
                if child == h6:
                    collecting = True
                    continue
                if not collecting:
                    continue
                if not hasattr(child, "name"):
                    # NavigableString
                    t = str(child).strip()
                    if t:
                        paras.append(t)
                    continue
                if child.name in ("p", "div"):
                    t = child.get_text(separator="\n").strip()
                    if t:
                        paras.append(t)
                elif child.name == "h6":
                    break  # next section starts
            if paras:
                return "\n\n".join(paras)

    # Strategy 2: grab the full codeLawSectionNoHead div text and clean it
    content = (
        soup.find("div", id="codeLawSectionNoHead")
        or soup.find("div", id="codeLawSection")
        or soup.find("div", class_="codeLawSection")
        or soup.find("div", id="codeLawDiv")
        or soup.find("main")
    )
    if not content:
        return None

    raw = content.get_text(separator="\n")
    lines = [l.rstrip() for l in raw.splitlines()]

    # Skip division/part/chapter header lines
    _noise = re.compile(
        r"^(FAMILY CODE|CAL\.\s*FAM\.\s*CODE|Family Code\s*$"
        r"|DIVISION \d|PART \d|CHAPTER \d"
        r"|Added by Stats\.|Amended by Stats\."
        r"|\(Added by|\(Amended by|\(Division\s"
        r"|\s*\d{1,4}\s*$"        # bare page numbers
        r"|^\s*[-–]\s*$)",         # stray dashes
        re.IGNORECASE,
    )
    _header_caps = re.compile(
        r"^[A-Z][A-Z\s,\.'\d\[\]\(\)\-]+\[\d+ - \d+\]\s*$"
    )
    cleaned = []
    for l in lines:
        s = l.strip()
        if not s:
            cleaned.append("")
            continue
        if _noise.match(s):
            continue
        if _header_caps.match(s):
            continue
        cleaned.append(l)

    text = re.sub(r"\n{3,}", "\n\n", "\n".join(cleaned)).strip()
    return text if len(text) > 30 else None


# ─── Single-section fetcher ────────────────────────────────────────────────────

def fetch_one(sec_num: str, url: str,
              session: requests.Session) -> tuple[str, dict | None]:
    try:
        r = session.get(url, headers=HEADERS, timeout=25)
        if r.status_code == 404:
            return sec_num, {"title": "", "text": "", "source_url": url}
        r.raise_for_status()
    except Exception as exc:
        return sec_num, None   # will retry or mark empty

    text = parse_leginfo_html(r.text, sec_num)
    if not text:
        return sec_num, {"title": "", "text": "", "source_url": url}

    # Short title: first line if concise
    first = next((l.strip() for l in text.splitlines() if l.strip()), "")
    title = first if first and len(first) < 120 and not re.match(r"^\(", first) else ""

    return sec_num, {"title": title, "text": text, "source_url": url}


# ─── Parallel fetch engine ─────────────────────────────────────────────────────

def fetch_all(sections: dict[str, str],
              cache: dict,
              retries: int = 2) -> dict:
    """
    Fetch all sections not already in `cache`.
    Returns updated cache dict.
    """
    todo = {k: v for k, v in sections.items() if k not in cache}
    print(f"  Need to fetch: {len(todo)}  (cached: {len(cache)})")
    if not todo:
        return cache

    results = dict(cache)
    errors: dict[str, str] = {}   # sec_num → url for retry

    session = requests.Session()
    done = 0
    fail = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        future_map = {
            pool.submit(fetch_one, num, url, session): num
            for num, url in todo.items()
        }
        for future in as_completed(future_map):
            sec_num, result = future.result()
            if result is not None:
                results[sec_num] = result
                done += 1
            else:
                errors[sec_num] = todo[sec_num]
                fail += 1

            total = done + fail
            if total % 200 == 0 or total == len(todo):
                pct = total * 100 // len(todo)
                print(f"  {total}/{len(todo)} ({pct}%)  OK={done}  err={fail}",
                      flush=True)
                LEGINFO_CACHE.write_text(
                    json.dumps(results, indent=2, ensure_ascii=False)
                )

    # One retry pass for network errors
    if errors and retries > 0:
        print(f"\n  Retrying {len(errors)} failed sections…")
        time.sleep(3)
        results = fetch_all(errors, results, retries=retries - 1)

    LEGINFO_CACHE.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    return results


# ─── JSON merge ───────────────────────────────────────────────────────────────

def merge_into_full_json(fetched: dict):
    raw = json.loads(SECTIONS_FULL.read_text())
    is_obj = isinstance(raw, dict)
    secs = raw.get("sections", []) if is_obj else raw

    sec_map: dict[str, dict] = {}
    for s in secs:
        num = str(s.get("sectionNumber", "")).strip()
        if num:
            sec_map[num] = s

    updated = added = skipped = 0
    for num, res in fetched.items():
        txt = (res.get("text") or "").strip()
        if not txt:
            skipped += 1
            continue
        if num in sec_map:
            sec_map[num]["text"] = txt
            if res.get("source_url"):
                sec_map[num]["source_url"] = res["source_url"]
            updated += 1
        else:
            sec_map[num] = {
                "sectionNumber": num,
                "text": txt,
                "source_url": res.get("source_url", ""),
            }
            added += 1

    def _sort_key(s: dict):
        n = str(s.get("sectionNumber", "0"))
        try:
            return (float(n.split(".")[0]), float("0." + n.split(".")[1]) if "." in n else 0)
        except Exception:
            return (999999, 0)

    new_secs = sorted(sec_map.values(), key=_sort_key)
    if is_obj:
        raw["sections"] = new_secs
        SECTIONS_FULL.write_text(json.dumps(raw, indent=2, ensure_ascii=False))
    else:
        SECTIONS_FULL.write_text(json.dumps(new_secs, indent=2, ensure_ascii=False))

    print(f"  JSON updated: {updated} | added: {added} | skipped (empty): {skipped}")


# ─── Git helpers ──────────────────────────────────────────────────────────────

def git(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, check=True, text=True,
                          capture_output=True)


def git_push(message: str):
    git("add", "-A")
    diff = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if not diff.stdout.strip():
        print("  (no changes to commit)")
        return
    git("commit", "-m", message)
    git("push", "origin", "main")
    n = len(diff.stdout.strip().splitlines())
    print(f"  ✓ Pushed  '{message}'  ({n} files)", flush=True)


# ─── Division rebuild + push ──────────────────────────────────────────────────

def rebuild_and_push(
    div_slug: str,
    div_info: dict,
    div_sections: list[str],
    division_nav: dict,      # full nav dict (all divs seen so far)
    u,                        # the unify_family_docs module
):
    """Generate all pages for one division, rebuild docs.yml, commit+push."""
    registry  = u._registry_cache
    case_map  = u._case_map_cache
    xref_map  = u._xref_map_cache

    written = 0
    for sec_num in div_sections:
        section = registry.get(
            sec_num,
            {"sectionNumber": sec_num, "text": "", "source_url": u._leginfo_url(sec_num)},
        )
        cases  = case_map.get(sec_num, [])
        xrefs  = xref_map.get(sec_num, [])
        content = u.generate_section_page(sec_num, section, div_info, cases, xrefs)
        slug    = u._section_slug(div_info["section_prefix"], sec_num)
        (PAGES_DIR / f"{slug}.mdx").write_text(content, encoding="utf-8")
        written += 1

    # Division index page
    idx = u.generate_division_index(div_slug, div_info, div_sections)
    (PAGES_DIR / f"{div_slug}.mdx").write_text(idx, encoding="utf-8")

    # Rebuild docs.yml with everything accumulated so far
    yml = u.generate_docs_yml(division_nav)
    (ROOT / "fern" / "docs.yml").write_text(yml, encoding="utf-8")

    print(f"  {div_info['title']}: {written} section pages + index written")

    git_push(
        f"docs: {div_info['title']} — {written} sections with full leginfo text"
    )
    return written


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-fetch", action="store_true",
                        help="Skip leginfo fetching; use existing cache only.")
    parser.add_argument("--div", default=None,
                        help="Only rebuild this one division slug.")
    args = parser.parse_args()

    # ── Git identity ──────────────────────────────────────────────────────────
    subprocess.run(["git", "config", "user.email", "bot@family-code-docs.com"],
                   cwd=ROOT)
    subprocess.run(["git", "config", "user.name", "FamilyCodeBot"], cwd=ROOT)

    print("=" * 62)
    print("  California Family Code — Fetch ▸ Build ▸ Push")
    print("=" * 62)

    # ── Step 1: collect all section numbers ──────────────────────────────────
    print("\n[1] Collecting section numbers…")

    # From existing full JSON
    raw = json.loads(SECTIONS_FULL.read_text())
    secs_list = raw.get("sections", []) if isinstance(raw, dict) else raw
    all_sections: dict[str, str] = {}
    for s in secs_list:
        num = str(s.get("sectionNumber", "")).strip()
        url = s.get("source_url", "").strip() or leginfo_url(num)
        if num:
            all_sections[num] = url

    # From MDX filenames (catches any extras)
    for f in PAGES_DIR.glob("*.mdx"):
        m = re.match(r"^.+-section-([\d.]+)\.mdx$", f.stem)
        if m:
            num = m.group(1)
            if num not in all_sections:
                all_sections[num] = leginfo_url(num)

    print(f"  Total unique sections: {len(all_sections)}")

    # ── Step 2: fetch from leginfo ────────────────────────────────────────────
    if not args.skip_fetch:
        print("\n[2] Fetching statute text from leginfo.legislature.ca.gov…")
        existing_cache: dict = {}
        if LEGINFO_CACHE.exists():
            existing_cache = json.loads(LEGINFO_CACHE.read_text())
            # Only keep entries that have actual text
            existing_cache = {
                k: v for k, v in existing_cache.items()
                if v.get("text", "").strip()
            }
            print(f"  Resuming from cache: {len(existing_cache)} already fetched.")

        fetched = fetch_all(all_sections, existing_cache)
        print(f"  Total cached: {len(fetched)}")

        # ── Step 3: merge into full JSON ──────────────────────────────────────
        print("\n[3] Merging into family_code_sections_full.json…")
        merge_into_full_json(fetched)
    else:
        print("\n[2] Skipping fetch (--skip-fetch).")
        print("[3] Skipping JSON merge.")

    # ── Step 4: import unify_family_docs ──────────────────────────────────────
    print("\n[4] Loading unify_family_docs…")
    sys.path.insert(0, str(ROOT))
    import importlib
    import unify_family_docs as u  # noqa: E402

    # Pre-load data caches so we don't reload inside every division loop
    print("  Building registry + case map + xref map…")
    registry = u.build_section_registry()
    case_map = u.build_case_map()
    xref_map = u.build_cross_ref_map()
    # Attach caches to module for use in rebuild_and_push
    u._registry_cache = registry
    u._case_map_cache = case_map
    u._xref_map_cache = xref_map
    print(f"  Registry: {len(registry)} sections")

    # ── Step 5: discover which sections belong to which division ───────────────
    print("\n[5] Assigning sections to divisions…")

    existing_file_map: dict[str, str] = {}
    for f in PAGES_DIR.glob("*.mdx"):
        m = re.match(r"^(.+)-section-([\d.]+)\.mdx$", f.stem)
        if m:
            existing_file_map[m.group(2)] = m.group(1)

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

    total_secs = sum(len(v) for v in div_sections_map.values())
    print(f"  Assigned {total_secs} sections across {len(div_sections_map)} divisions")

    # ── Step 6: home page + case annotations ─────────────────────────────────
    print("\n[6] Generating home page + case annotations…")
    home = u.generate_home_page()
    (PAGES_DIR / "home.mdx").write_text(home, encoding="utf-8")

    all_cases = u.load_json(u.CASE_ENTRIES_JSON, [])
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    for title, slug, comp_sec in u.CASE_ANNOTATION_PAGES:
        content = u.generate_case_annotation_page(title, slug, comp_sec, all_cases)
        (CASES_DIR / f"{slug}.mdx").write_text(content, encoding="utf-8")

    # ── Step 7: division-by-division build + push ──────────────────────────────
    print("\n[7] Building divisions and pushing…\n")
    division_nav: dict[str, list[str]] = {}

    divs_to_process = (
        [args.div] if args.div else list(u.DIVISION_STRUCTURE.keys())
    )

    for div_slug in divs_to_process:
        div_info = u.DIVISION_STRUCTURE.get(div_slug)
        if not div_info:
            print(f"  SKIP unknown division: {div_slug}")
            continue

        secs = div_sections_map.get(div_slug, [])
        # Always include this division in nav (even if no sections)
        division_nav[div_slug] = secs

        print(f"\n  ── {div_info['title']} ({len(secs)} sections) ──")
        rebuild_and_push(div_slug, div_info, secs, dict(division_nav), u)

    # Final push: home page + case annotations (may have changed)
    print("\n[8] Final push (home + case annotations)…")
    git_push("docs: rebuild home page and case annotation pages")

    print("\n" + "=" * 62)
    print("  ✓  Complete!")
    print(f"     Divisions processed : {len(divs_to_process)}")
    print(f"     Total sections      : {total_secs}")
    print("=" * 62)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
fetch_leginfo.py
================
Fetches clean statutory text for every Family Code section directly from
leginfo.legislature.ca.gov and writes the result to leginfo_sections.json.

Run once:
    python3 fetch_leginfo.py

Output: leginfo_sections.json  —  { "6203": { "title": "...", "text": "...", "url": "..." }, ... }

Rate-limited to 1 request per second to be polite to the server.
"""

import json
import re
import time
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "beautifulsoup4", "-q"])
    import requests
    from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
SECTIONS_FULL = ROOT / "family_code_sections_full.json"
OUTPUT = ROOT / "leginfo_sections.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def load_section_urls() -> dict[str, str]:
    """Return {sec_num: url} for all sections that have a leginfo URL."""
    data = json.loads(SECTIONS_FULL.read_text())
    secs = data.get("sections", [])
    result = {}
    for s in secs:
        num = str(s.get("sectionNumber", "")).strip()
        url = s.get("source_url", "").strip()
        if num and url:
            result[num] = url
    return result


def fetch_section(url: str, session: requests.Session) -> dict | None:
    """Fetch a single leginfo section page and extract title + text."""
    try:
        r = session.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"    ERROR fetching {url}: {e}")
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    # leginfo wraps section content in <div id="codeLawSectionNoHead">
    # or <div id="codeLawSection"> depending on the page type
    content_div = (
        soup.find("div", id="codeLawSectionNoHead")
        or soup.find("div", id="codeLawSection")
        or soup.find("div", class_="codeLawSection")
    )

    if not content_div:
        # fallback: grab all paragraph text from main content area
        main = soup.find("div", id="codeLawDiv") or soup.find("main")
        if not main:
            return None
        content_div = main

    # Extract text, preserving paragraph breaks
    raw = content_div.get_text(separator="\n")

    # Clean up
    lines = [l.rstrip() for l in raw.splitlines()]

    # Remove running page-header noise leginfo sometimes injects
    noise = re.compile(
        r"^(FAMILY CODE|CAL\. FAM\. CODE|Family Code|"
        r"Sec\.\s+\d|SECTION \d|\d+\s*$|"
        r"Added by Stats\.|Amended by Stats\.|"
        r"\(Added by|\(Amended by)",
        re.IGNORECASE,
    )
    lines = [l for l in lines if not noise.match(l.strip())]

    # Collapse 3+ blank lines to 2
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()

    if not cleaned:
        return None

    # Try to extract a short title from the first non-empty line
    first = next((l.strip() for l in cleaned.splitlines() if l.strip()), "")
    # Title: first line if it's short and doesn't start with a subsection marker
    if first and len(first) < 100 and not re.match(r"^\(", first) and not re.match(r"^\d", first):
        title = first
    else:
        title = ""

    return {"title": title, "text": cleaned, "url": url}


def main():
    # Load existing output if any (resume on interruption)
    if OUTPUT.exists():
        existing = json.loads(OUTPUT.read_text())
        print(f"Resuming — {len(existing)} sections already fetched.")
    else:
        existing = {}

    urls = load_section_urls()
    print(f"Total sections with URLs: {len(urls)}")

    session = requests.Session()
    done = 0
    errors = 0

    for sec_num, url in sorted(urls.items(), key=lambda kv: float(kv[0].split(".")[0]) if kv[0].replace(".", "").isdigit() else 999999):
        if sec_num in existing:
            continue  # already fetched

        result = fetch_section(url, session)
        if result:
            existing[sec_num] = result
            done += 1
        else:
            existing[sec_num] = {"title": "", "text": "", "url": url}
            errors += 1

        # Progress report every 50
        if (done + errors) % 50 == 0:
            print(f"  {done + errors}/{len(urls) - len([k for k in existing if existing[k]['text']])} done, {errors} errors")
            OUTPUT.write_text(json.dumps(existing, indent=2, ensure_ascii=False))

        time.sleep(1.0)  # polite rate limit

    OUTPUT.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
    print(f"\nDone. {done} fetched, {errors} errors. Output: {OUTPUT}")


if __name__ == "__main__":
    main()

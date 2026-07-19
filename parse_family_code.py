#!/usr/bin/env python3
"""Parse extracted Family Code PDF text into structured sections."""

import os
import re
import json
import glob

SRC = "extracted_text"
OUT_JSON = "family_code_sections_full.json"

section_re = re.compile(r"^§\s*(\d{1,5}(?:\.\d+)?)\.\s*(.*)$")
commentary_re = re.compile(r"^(Commentary|Historical Note|Law Revision|Comment|Notes?)\b", re.I)

def quality(text):
    t = text.strip()
    if not t:
        return -1
    first = t.split("\n")[0].strip()
    score = 0.0
    if re.match(r"^[A-Za-z]", first):
        score += 2
    if re.match(r"^(Amended|Added|Stats|\(Stats|Note|Historical)", first):
        score -= 3
    if first.isupper() and len(first) > 8:
        score -= 2
    score += min(len(t), 2000) / 500.0
    return score

JUNK_RE = re.compile(r"^(West[’']s|Hein[’']s|California Transaction|Research References|Witkin|Forms--|Short title|Forms$|Comment$|Ex Parte Protective|^\s*§\s*\d+(\.\d+)?\.\s*Comment)")


def strip_junk(text):
    out = []
    for ln in text.split("\n"):
        if JUNK_RE.match(ln.strip()):
            continue
        out.append(ln)
    return "\n".join(out).strip()

raw = {}
first_seen = {}  # num -> file index (earliest occurrence wins)
order = []

for fi, path in enumerate(sorted(glob.glob(os.path.join(SRC, "*.txt")))):
    with open(path, encoding="utf-8", errors="ignore") as fh:
        lines = fh.read().splitlines()
    pending = None
    buf = []
    for line in lines:
        m = section_re.match(line.strip())
        if m:
            if pending is not None:
                text = "\n".join(buf).strip()
                cut = None
                bl = text.split("\n")
                for i, ln in enumerate(bl):
                    if commentary_re.match(ln.strip()):
                        cut = i
                        break
                if cut is not None:
                    text = "\n".join(bl[:cut]).strip()
                text = re.sub(r"\n{2,}", "\n", text).strip()
                text = strip_junk(text)
                if text:
                    ls = [l for l in text.split("\n") if l.strip()]
                    toc = sum(1 for l in ls if re.match(r"^\d{1,5}(\.\d+)?\.\s+\S", l))
                    if not (len(ls) >= 3 and toc >= max(2, len(ls) * 0.6)):
                        if pending not in raw:
                            raw[pending] = text
                            first_seen[pending] = fi
                            order.append(pending)
                        elif fi < first_seen.get(pending, 999) and quality(text) >= quality(raw[pending]) - 1:
                            # prefer earliest occurrence (canonical definition)
                            raw[pending] = text
                            first_seen[pending] = fi
            pending = m.group(1)
            buf = []
        else:
            if pending is not None:
                buf.append(line)
    if pending is not None:
        # flush last
        text = "\n".join(buf).strip()
        bl = text.split("\n")
        cut = None
        for i, ln in enumerate(bl):
            if commentary_re.match(ln.strip()):
                cut = i
                break
        if cut is not None:
            text = "\n".join(bl[:cut]).strip()
        text = re.sub(r"\n{2,}", "\n", text).strip()
        text = strip_junk(text)
        if text and pending not in raw:
            raw[pending] = text
            order.append(pending)

print("Parsed", len(raw), "sections")

def division_for(num):
    try:
        f = float(num)
    except ValueError:
        return None
    if f < 200: return 1
    if f < 300: return 2
    if f < 400: return 3
    if f < 500: return 3
    if f < 600: return 3
    if f < 700: return 3
    if f < 800: return 3
    if f < 860: return 3
    if f < 900: return 13
    if f < 1000: return 13
    if f < 1100: return 14
    if f < 2000: return 4
    if f < 2300: return 6
    if f < 2500: return 6
    if f < 3000: return 7
    if f < 3500: return 8
    if f < 3700: return 9
    if f < 4000: return 9
    if f < 5000: return 9
    if f < 6000: return 9
    if f < 6500: return 10
    if f < 7000: return 11
    if f < 7500: return 11
    if f < 8000: return 12
    if f < 8600: return 12
    if f < 17600: return 17
    if f < 20200: return 20
    return None

sections = []
for num in order:
    div = division_for(num)
    if div is None:
        continue
    sections.append({
        "sectionNumber": num,
        "division": div,
        "text": raw[num],
        "source_url": f"https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=FAM&sectionNum={num}.",
    })

with open(OUT_JSON, "w", encoding="utf-8") as f:
    json.dump({"source": "California Family Code Annotated (Blumberg, 2020)",
               "sections_fetched": len(sections),
               "sections": sections}, f, indent=2, ensure_ascii=False)

from collections import Counter
print("By division:", dict(sorted(Counter(s["division"] for s in sections).items())))
print("Wrote", OUT_JSON)

#!/usr/bin/env python3
"""
cleanup_docs.py
Restores the Fern site to clean, native-UI-only format:
  1. docs.yml — replace bad colors block, remove css: ref, add icons to sections
  2. Division overview MDX (17 files) — fix ALL CAPS, remove bracket ranges
  3. All section MDX — strip custom HTML (breadcrumbs, subsec spans, small tags)
  4. styles.css — clear it (no custom CSS needed)
"""

import re
from pathlib import Path

ROOT = Path("/home/runner/workspace")
DOCS_YML  = ROOT / "fern/docs.yml"
PAGES_DIR = ROOT / "fern/docs/pages"
STYLES    = ROOT / "fern/styles.css"

# ─────────────────────────────────────────────────────────────────────────────
# 1. docs.yml
# ─────────────────────────────────────────────────────────────────────────────
print("[1] Updating docs.yml …")

text = DOCS_YML.read_text()

# Remove the bad injected block at the bottom (colors + theme + landing-page + css)
# These were appended after the navigation block by Replit
text = re.sub(
    r'\ncolors:\n  accent-primary:.*?(?=\Z)',
    '',
    text,
    flags=re.DOTALL
)

# Also remove any stray css: block
text = re.sub(r'\ncss:\n(?:  - [^\n]+\n?)+', '\n', text)

# Remove any stray theme: block (Replit added)
text = re.sub(r'\ntheme:\n(?:  [^\n]+\n?)+', '\n', text)

# Remove stray landing-page: block
text = re.sub(r'\nlanding-page:\n(?:  [^\n]+\n?)+', '\n', text)

# Add clean colors block right after "title: California Family Code"
COLORS_BLOCK = """\
colors:
  accentPrimary:
    light: "#1E4A8A"
    dark:  "#6B9FD4"
  background:
    light: "#F5F4F0"
    dark:  "#1C2332"
"""

if "colors:" not in text:
    text = text.replace(
        "title: California Family Code\n",
        "title: California Family Code\n\n" + COLORS_BLOCK
    )
else:
    # Replace existing (possibly correct but wrong values) colors block near top
    text = re.sub(
        r'colors:\n  accentPrimary:.*?(?=\n\S)',
        COLORS_BLOCK.rstrip(),
        text,
        flags=re.DOTALL
    )

# Add icon: book-open to top-level division sections that don't already have one.
# These lines look like:  "          - section: "Division Name""
# followed by:            "            collapsed: true"
# We insert:              "            icon: book-open"  between them.
def add_section_icon(m):
    section_line = m.group(1)
    collapsed_line = m.group(2)
    # Already has icon?
    return section_line + "\n            icon: book-open\n" + collapsed_line

text = re.sub(
    r'(          - section: "[^"]+"\n)(            collapsed: true)',
    add_section_icon,
    text
)

# Add icon: scale to the Case Annotations section
text = re.sub(
    r'(      - section: Case Annotations\n)(        contents:)',
    r'\1        icon: scale\n\2',
    text
)

DOCS_YML.write_text(text)
print("   done")

# ─────────────────────────────────────────────────────────────────────────────
# 2. Division overview MDX — fix ALL CAPS headings, remove bracket ranges
# ─────────────────────────────────────────────────────────────────────────────
print("[2] Fixing division overview pages …")

MINOR = {'a','an','the','and','but','or','for','nor','on','at','to','by','in','of','up','as','with'}

def smart_titlecase(text):
    """Title-case an ALL-CAPS string, keep known acronyms intact."""
    words = text.split()
    out = []
    for i, w in enumerate(words):
        # Preserve all-caps acronyms/codes: IV-D, SLAPP, DV, etc. (≤5 chars or hyphenated)
        if re.match(r'^[A-Z][A-Z0-9\-\.]*$', w) and (len(w) <= 5 or '-' in w or '.' in w):
            out.append(w)
        elif w.isupper() and len(w) > 1:
            low = w.lower()
            if i > 0 and i < len(words) - 1 and low in MINOR:
                out.append(low)
            else:
                out.append(w.capitalize())
        else:
            out.append(w)
    return ' '.join(out)

def clean_heading(raw):
    # Remove section-range brackets like [1. - 185] or [6200 - 6460]
    raw = re.sub(r'\s*\[[\d\.\s\-]+\]', '', raw)
    # Collapse multiple spaces (between number and title)
    raw = re.sub(r'  +', ' ', raw).strip()
    # Fix ALL CAPS words
    raw = smart_titlecase(raw)
    return raw

OVERVIEW_PAGES = [
    "preliminary-provisions.mdx",
    "marriage.mdx",
    "division-2.5-domestic-partners.mdx",
    "division-3-marriage.mdx",
    "division-4-rights-during-marriage.mdx",
    "division-5-conciliation.mdx",
    "division-6-dissolution.mdx",
    "division-7-property.mdx",
    "division-8-custody.mdx",
    "division-9-support.mdx",
    "division-10-domestic-violence.mdx",
    "division-11-minors.mdx",
    "division-12-parent-child.mdx",
    "division-13-adoption.mdx",
    "division-14-family-law-facilitator.mdx",
    "division-17-support-services.mdx",
    "division-20-pilot-projects.mdx",
]

fixed = 0
for name in OVERVIEW_PAGES:
    p = PAGES_DIR / name
    if not p.exists():
        continue
    c = p.read_text()

    # Fix frontmatter title / description
    c = re.sub(r'(title:\s*")([^"]+)(")', lambda m: m.group(1) + clean_heading(m.group(2)) + m.group(3), c)
    c = re.sub(r'(description:\s*")([^"]+)(")', lambda m: m.group(1) + clean_heading(m.group(2)) + m.group(3), c)

    # Fix markdown headings (# ## ### ####)
    def fix_md_heading(m):
        hashes = m.group(1)
        body   = m.group(2)
        return hashes + ' ' + clean_heading(body)
    c = re.sub(r'^(#{1,4})\s+(.+)$', fix_md_heading, c, flags=re.MULTILINE)

    p.write_text(c)
    fixed += 1

print(f"   fixed {fixed} overview pages")

# ─────────────────────────────────────────────────────────────────────────────
# 3. Section MDX pages — strip custom HTML
# ─────────────────────────────────────────────────────────────────────────────
print("[3] Cleaning section pages …")

all_mdx   = list(PAGES_DIR.glob("*.mdx")) + list(PAGES_DIR.glob("case-annotations/*.mdx"))
skip_names = set(OVERVIEW_PAGES) | {"home.mdx"}

cleaned = 0
for p in all_mdx:
    if p.name in skip_names:
        continue
    c = p.read_text()
    orig = c

    # Remove <nav class="fl-breadcrumb">...</nav> (multiline)
    c = re.sub(r'<nav[^>]*class=["\']fl-breadcrumb["\'][^>]*>.*?</nav>\s*\n?', '', c, flags=re.DOTALL)

    # <span class="subsec">(x)</span>  →  (x)
    c = re.sub(r'<span[^>]*class=["\']subsec["\'][^>]*>([^<]*)</span>', r'\1', c)

    # <small>[Source](url)</small>  →  [Source](url)
    c = re.sub(r'<small>(\[Source\][^<]*)</small>', r'\1', c)

    # <span class="statute-link" ...>text</span>  →  text
    c = re.sub(r'<span[^>]*class=["\']statute-link["\'][^>]*>([^<]*)</span>', r'\1', c)

    # <span class="case-statutes">text</span>  →  text
    c = re.sub(r'<span[^>]*class=["\']case-statutes["\'][^>]*>([^<]*)</span>', r'\1', c)

    # <div class="case-callout">...</div>  →  unwrap (keep inner text)
    c = re.sub(r'<div[^>]*class=["\']case-callout["\'][^>]*>(.*?)</div>', r'\1', c, flags=re.DOTALL)

    # Remove any leftover empty <div> or <span> wrappers
    c = re.sub(r'</?(?:div|span)[^>]*>\s*', '', c)

    if c != orig:
        p.write_text(c)
        cleaned += 1

print(f"   cleaned {cleaned} section/annotation pages")

# ─────────────────────────────────────────────────────────────────────────────
# 4. Clear styles.css
# ─────────────────────────────────────────────────────────────────────────────
print("[4] Clearing styles.css …")
STYLES.write_text("/* California Family Code — no custom styles */\n")
print("   done")

print("\nAll done. Review fern/docs.yml, then push to trigger Fern rebuild.")

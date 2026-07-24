# California Family Code — Fern Docs
## How to Build, Preview, and Update

---

## Prerequisites

Make sure you have these installed once:

```bash
# Python 3.9+ (check your version)
python3 --version

# Node.js 18+ (needed for Fern CLI)
node --version

# Fern CLI (install once, globally)
npm install -g fern-api
```

---

## Step 1 — Run the automation script

From the repo root:

```bash
cd /Users/2024-jan/.bob/playground/family-x1oh1xy2

python3 unify_family_docs.py
```

This takes about 15–30 seconds. You will see output like:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  California Family Code — Fern Docs Unification
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[1] Loading data sources…
     Registry: ~4200 unique sections from two sources.

[2] Scanning existing MDX pages…
     Found 3473 existing section pages.

[3] Assigning sections to divisions…
     Assigned 4100+ sections across 17 divisions.

[4] Generating section pages…
     Written: 4100+

[5] Generating division index pages…
[6] Generating home page…
[7] Generating case annotation pages…
[8] Rebuilding fern/docs.yml…

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✓  Build complete.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Step 2 — Preview locally

```bash
cd /Users/2024-jan/.bob/playground/family-x1oh1xy2/fern

fern docs dev
```

Open your browser at **http://localhost:3000**

---

## Step 3 — Push to publish

The site is already connected to Fern Cloud at `family.docs.buildwithfern.com`.
Pushing to `main` triggers an automatic rebuild:

```bash
cd /Users/2024-jan/.bob/playground/family-x1oh1xy2

git add -A
git commit -m "chore: rebuild via unify_family_docs.py"
git push origin main
```

Fern Cloud will pick up the changes and deploy within ~2 minutes.

---

## Useful script options

| Command | What it does |
|---|---|
| `python3 unify_family_docs.py` | Full rebuild of all pages + docs.yml |
| `python3 unify_family_docs.py --audit` | Report only — no files written |
| `python3 unify_family_docs.py --section 6203` | Rebuild only § 6203 (fast, for spot fixes) |

---

## Adding new content in the future

### Adding a new case
1. Open `_case_entries.json`
2. Add a new entry following the existing format:
   ```json
   {
     "name": "Smith v. Jones",
     "year": "2026",
     "citation": "120 Cal.App.5th 100",
     "description": "...",
     "statutes": "Family Code sections 6203, 6320",
     "compendium_section": "I"
   }
   ```
3. Run `python3 unify_family_docs.py` — the case will appear on all relevant section pages automatically.

### Updating a section's statutory text
1. Open `family_code_sections_full.json`
2. Find the entry by `sectionNumber` and update the `text` field
3. Run `python3 unify_family_docs.py --section NNNN`

### Adding a new division or chapter
1. Open `unify_family_docs.py`
2. Add your division to the `DIVISION_STRUCTURE` dict at the top
3. Run `python3 unify_family_docs.py`

---

## File map

```
family-x1oh1xy2/
├── unify_family_docs.py          ← master automation script (run this)
├── fern/
│   ├── docs.yml                  ← navigation (auto-rebuilt by script)
│   ├── styles.css                ← site styles (contemporary legal)
│   └── docs/pages/
│       ├── home.mdx
│       ├── preliminary-provisions.mdx
│       ├── preliminary-provisions-section-*.mdx
│       ├── division-10-domestic-violence.mdx
│       ├── division-10-domestic-violence-section-*.mdx
│       ├── ...
│       └── case-annotations/
│           ├── abuse-definition.mdx
│           ├── issuing-dv-restraining-orders.mdx
│           └── ...
├── family_code_sections_full.json   ← primary section text + leginfo URLs
├── family_code_sections.json        ← secondary section text (broader)
├── _case_entries.json               ← all case annotations
├── _section_case_map.json           ← section → cases mapping
└── fam_cross_references.json        ← cross-reference links
```

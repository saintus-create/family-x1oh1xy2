import json, re, os

SECTIONS = [
    ("I", "What Is Abuse Under the DVPA", "abuse-definition"),
    ("II", "Issuing DV Restraining Orders", "issuing-dv-restraining-orders"),
    ("III", "Mutual Restraining Orders", "mutual-restraining-orders"),
    ("IV", "Renewing DV Restraining Orders", "renewing-dv-restraining-orders"),
    ("V", "Modifying and Terminating DVRO", "modifying-terminating-dvro"),
    ("VI", "DVRO and Firearms", "dvro-firearms"),
    ("VII", "Attorney Fees and Costs", "attorney-fees-costs"),
    ("VIII", "Vexatious Litigant", "vexatious-litigant"),
    ("IX", "Custody and Visitation", "custody-visitation"),
    ("X", "Spousal Support", "spousal-support"),
    ("XI", "DV as a Tort", "dv-as-tort"),
    ("XII", "Juvenile Dependency", "juvenile-dependency"),
    ("XIII", "Special Immigrant Juvenile Status", "special-immigrant-juvenile"),
    ("XIV", "Other Cases", "other-cases"),
]

with open('_case_sections.json') as f:
    cases_by_section = json.load(f)

os.makedirs('fern/docs/pages/case-annotations', exist_ok=True)

for roman, title, slug in SECTIONS:
    sec_cases = cases_by_section.get(roman, [])
    
    mdx = f"""---
title: "Case Annotations: {title}"
slug: case-annotations/{slug}
---

# {roman}. {title}

> **Source:** [Case-Annotated Compendium of California Domestic Violence Laws (FVAP, 2026)](https://www.fvaplaw.org)

"""
    
    if not sec_cases:
        mdx += "No cases in this section.\n"
    else:
        for case in sorted(sec_cases, key=lambda c: c['name']):
            name = case['name']
            year = case['year']
            citation = case['citation']
            description = case.get('description', '')
            # Remove case name and citation from description if present
            desc = re.sub(r'^' + re.escape(name) + r'\s*\(\d{4}\)\s*' + re.escape(citation) + r'\s*', '', description).strip()
            desc = re.sub(r'\s+', ' ', desc).strip()
            if len(desc) > 800:
                desc = desc[:797] + "..."
            
            mdx += f"## {name} ({year})\n\n"
            mdx += f"**Citation:** {citation}\n\n"
            if desc:
                mdx += f"{desc}\n\n"
            if case.get('statutes'):
                mdx += f"**Statutes:** {case['statutes']}\n\n"
            mdx += "---\n\n"
    
    with open(f'fern/docs/pages/case-annotations/{slug}.mdx', 'w') as f:
        f.write(mdx)
    
    print(f"Generated {slug}.mdx ({len(sec_cases)} cases)")

print("\nDone generating case annotation pages")

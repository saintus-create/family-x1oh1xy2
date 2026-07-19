#!/usr/bin/env python3
"""Generate clean MDX pages from Family Code JSON data."""

import json
import os
import re

# Load sections data
with open('family_code_sections.json') as f:
    data = json.load(f)

sections = data['sections']

# Division/Part structure mapping section numbers to divisions
# Based on California Family Code structure
DIVISIONS = {
    1: {
        'title': 'Preliminary Provisions',
        'slug': 'preliminary-provisions',
        'parts': {
            1: {'title': 'General Provisions', 'sections': list(range(1, 14))},
        }
    },
    '1-definitions': {
        'title': 'Division 1 — Definitions',
        'slug': 'division-1-definitions',
        'parts': {
            2: {'title': 'Definitions', 'sections': list(range(50, 156))},
            3: {'title': 'Indian Child Welfare Act Definitions', 'sections': list(range(170, 186))},
        }
    },
    2: {
        'title': 'Marriage',
        'slug': 'marriage',
        'parts': {
            1: {'title': 'Validity of Marriage', 'sections': list(range(300, 311))},
            2: {'title': 'Marriage Licenses', 'sections': list(range(350, 361))},
            3: {'title': 'Solemnization', 'sections': list(range(400, 426))},
            4: {'title': 'Confidential Marriage', 'sections': list(range(500, 504))},
            5: {'title': 'Rights During Marriage', 'sections': list(range(550, 561))},
        }
    },
    3: {
        'title': 'Marriage — Rights and Obligations',
        'slug': 'division-3-marriage',
        'parts': {
            1: {'title': 'Property Rights', 'sections': list(range(700, 710))},
        }
    },
    4: {
        'title': 'Property Rights',
        'slug': 'division-4-rights-during-marriage',
        'parts': {
            1: {'title': 'Community Property', 'sections': list(range(760, 803))},
            2: {'title': 'Separate Property', 'sections': list(range(850, 853))},
            3: {'title': 'Quasi-Community Property', 'sections': list(range(910, 912))},
            4: {'title': 'Fiduciary Duties', 'sections': list(range(1100, 1104))},
        }
    },
    5: {
        'title': 'Conciliation Proceedings',
        'slug': 'division-5-conciliation',
        'parts': {
            1: {'title': 'Conciliation Court', 'sections': list(range(1850, 1853))},
        }
    },
    6: {
        'title': 'Dissolution, Nullity, Legal Separation',
        'slug': 'division-6-dissolution',
        'parts': {
            1: {'title': 'General Provisions', 'sections': list(range(2000, 2011))},
            2: {'title': 'Dissolution of Marriage', 'sections': list(range(2310, 2345))},
            3: {'title': 'Nullity of Marriage', 'sections': list(range(2200, 2211))},
            4: {'title': 'Legal Separation', 'sections': list(range(2345, 2350))},
        }
    },
    7: {
        'title': 'Division of Property',
        'slug': 'division-7-property',
        'parts': {
            1: {'title': 'Property Division', 'sections': list(range(2500, 2552))},
            2: {'title': 'Family Home', 'sections': list(range(2600, 2651))},
        }
    },
    8: {
        'title': 'Custody of Children',
        'slug': 'division-8-custody',
        'parts': {
            1: {'title': 'General', 'sections': list(range(3000, 3049))},
            2: {'title': 'Custody Orders', 'sections': list(range(3080, 3090))},
            3: {'title': 'Visitation', 'sections': list(range(3100, 3105))},
        }
    },
    9: {
        'title': 'Support',
        'slug': 'division-9-support',
        'parts': {
            1: {'title': 'Child Support', 'sections': list(range(3500, 3652))},
            2: {'title': 'Spousal Support', 'sections': list(range(3650, 3692))},
            3: {'title': 'Family Support', 'sections': list(range(3700, 3712))},
        }
    },
    10: {
        'title': 'Prevention of Domestic Violence',
        'slug': 'division-10-domestic-violence',
        'parts': {
            1: {'title': 'Domestic Violence Prevention Act', 'sections': list(range(6200, 6220))},
            2: {'title': 'Protective Orders', 'sections': list(range(6300, 6389))},
        }
    },
    11: {
        'title': 'Minors',
        'slug': 'division-11-minors',
        'parts': {
            1: {'title': 'Age of Majority', 'sections': list(range(6500, 6503))},
            2: {'title': 'Contracts', 'sections': list(range(6700, 6710))},
            3: {'title': 'Emancipation', 'sections': list(range(7120, 7130))},
        }
    },
    12: {
        'title': 'Parent and Child Relationship',
        'slug': 'division-12-parent-child',
        'parts': {
            1: {'title': 'Parentage', 'sections': list(range(7540, 7551))},
            2: {'title': 'Voluntary Declaration', 'sections': list(range(7570, 7578))},
            3: {'title': 'Adoption', 'sections': list(range(7600, 7670))},
        }
    },
    13: {
        'title': 'Adoption',
        'slug': 'division-13-adoption',
        'parts': {
            1: {'title': 'General', 'sections': list(range(8600, 8620))},
            2: {'title': 'Stepparent Adoption', 'sections': list(range(9000, 9008))},
            3: {'title': 'Adoption of Adults', 'sections': list(range(9100, 9103))},
        }
    },
    14: {
        'title': 'Family Law Facilitator Act',
        'slug': 'division-14-family-law-facilitator',
        'parts': {
            1: {'title': 'General', 'sections': list(range(10000, 10016))},
        }
    },
    17: {
        'title': 'Support Services',
        'slug': 'division-17-support-services',
        'parts': {
            1: {'title': 'Child Support Enforcement', 'sections': list(range(17000, 17600))},
        }
    },
    20: {
        'title': 'Pilot Projects',
        'slug': 'division-20-pilot-projects',
        'parts': {
            1: {'title': 'Pilot Projects', 'sections': list(range(20000, 20020))},
        }
    },
}

# Build section lookup
section_map = {}
for s in sections:
    try:
        section_map[int(s['sectionNumber'])] = s
    except ValueError:
        try:
            section_map[float(s['sectionNumber'])] = s
        except ValueError:
            section_map[s['sectionNumber']] = s

def get_section_text(section_num):
    """Get section text from map, handling various formats."""
    for key in [section_num, float(section_num), int(section_num)]:
        if key in section_map:
            return section_map[key]['text']
    return None

def generate_page(division_num, div_info):
    """Generate MDX page for a division."""
    slug = div_info['slug']
    title = f"Division {division_num}: {div_info['title']}"
    
    lines = [
        f'---',
        f'title: "{title}"',
        f'slug: {slug}',
        f'---',
        f'',
        f'# {div_info["title"]}',
        f'',
        f'**Division {division_num}** — California Family Code',
        f'',
    ]
    
    for part_num, part_info in div_info['parts'].items():
        part_sections = []
        for sec_num in part_info['sections']:
            text = get_section_text(sec_num)
            if text:
                part_sections.append((sec_num, text))
        
        if part_sections:
            lines.append(f'## Part {part_num}: {part_info["title"]}')
            lines.append('')
            for sec_num, text in part_sections:
                lines.append(f'### Section {sec_num}')
                lines.append('')
                # Clean up the text - keep verbatim
                lines.append(text)
                lines.append('')
                lines.append('')
    
    return '\n'.join(lines)

# Generate all division pages
output_dir = 'fern/docs/pages'
os.makedirs(output_dir, exist_ok=True)

# Remove old generated pages
old_pages = [
    'division-1-definitions.mdx', 'division-2-general.mdx', 'division-2.5-domestic-partners.mdx',
    'division-3-marriage.mdx', 'division-4-rights-during-marriage.mdx', 'division-5-conciliation.mdx',
    'division-6-dissolution.mdx', 'division-7-property.mdx', 'division-8-custody.mdx',
    'division-9-support.mdx', 'division-10-domestic-violence.mdx', 'division-11-minors.mdx',
    'division-12-parent-child.mdx', 'division-13-adoption.mdx', 'division-14-family-law-facilitator.mdx',
    'division-17-support-services.mdx', 'division-20-pilot-projects.mdx',
    'preliminary-provisions.mdx', 'components.mdx', 'developer-guide.mdx', 'support.mdx',
    'case-law.mdx', 'forms.mdx', 'api-reference-overview.mdx', 'intro.mdx'
]

for page in old_pages:
    path = os.path.join(output_dir, page)
    if os.path.exists(path):
        os.remove(path)

# Generate new clean pages
for div_num, div_info in DIVISIONS.items():
    content = generate_page(div_num, div_info)
    filename = f'{div_info["slug"]}.mdx'
    path = os.path.join(output_dir, filename)
    with open(path, 'w') as f:
        f.write(content)
    print(f'Generated: {filename}')

# Generate home page
home_content = '''---
title: California Family Code
slug: home
layout: custom
no-image-zoom: true
---

# California Family Code

The complete California Family Code, presented verbatim.

## Divisions

'''
# Sort divisions by numeric key
def sort_key(item):
    key = item[0]
    if isinstance(key, int):
        return key
    if isinstance(key, str) and key.startswith('1-'):
        return 1.5
    return 999

for div_num, div_info in sorted(DIVISIONS.items(), key=sort_key):
    home_content += f'- [Division {div_num}: {div_info["title"]}](/{div_info["slug"]})\n'

home_content += '''
---

*Source: [California Legislative Information](https://leginfo.legislature.ca.gov/faces/codesTOCSelected.xhtml?tocCode=FAM) — Official codification maintained by the California State Senate and Assembly.*
'''

with open(os.path.join(output_dir, 'home.mdx'), 'w') as f:
    f.write(home_content)

print('Generated: home.mdx')
print('Done!')
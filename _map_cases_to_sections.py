import json, re

with open('_case_sections.json') as f:
    cases_by_section = json.load(f)

# Flatten all cases
all_cases = []
for roman, cases in cases_by_section.items():
    for case in cases:
        case['compendium_section'] = roman
        all_cases.append(case)

print(f"Total cases: {len(all_cases)}")

# Map cases to Family Code section numbers based on statute references
section_to_cases = {}

for case in all_cases:
    statutes_text = case.get('statutes', '')
    if not statutes_text:
        continue
    
    # Extract Family Code section numbers
    # Patterns: "Family Code sections 6203, 6211" or "Family Code section 6320"
    # Also "Fam. Code, §§ 3000 et seq."
    fc_pattern = re.compile(r'Family Code sections?\s+([\d\.]+(?:\s*et\s*seq\.)?)', re.IGNORECASE)
    fam_pattern = re.compile(r'Fam\.\s*Code,?\s*§§?\s*([\d\.]+)', re.IGNORECASE)
    
    sections_found = set()
    for m in fc_pattern.finditer(statutes_text):
        sec = m.group(1).strip()
        # Handle "et seq." - map to range
        if 'et seq.' in sec.lower():
            base = re.sub(r'\s*et\s*seq\.', '', sec).strip()
            sections_found.add(f"{base}-{int(float(base))+100}")
        else:
            sections_found.add(sec)
    
    for m in fam_pattern.finditer(statutes_text):
        sec = m.group(1).strip()
        sections_found.add(sec)
    
    for sec in sections_found:
        section_to_cases.setdefault(sec, []).append(case)

# Save mapping
with open('/Users/2024-jan/f/family-x1oh1xy2/_section_case_map.json', 'w') as f:
    json.dump(section_to_cases, f, indent=2)

print(f"Mapped {len(section_to_cases)} sections to cases")
# Show top sections with most cases
sorted_sections = sorted(section_to_cases.items(), key=lambda x: len(x[1]), reverse=True)
for sec, cases in sorted_sections[:10]:
    print(f"  Section {sec}: {len(cases)} cases")

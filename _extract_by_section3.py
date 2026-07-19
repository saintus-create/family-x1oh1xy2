import fitz, re, json
pdf_path = "/Users/2024-jan/Downloads/2026.06.08-Case-Annotated.pdf"
doc = fitz.open(pdf_path)

full_text = ""
for i in range(len(doc)):
    full_text += doc[i].get_text() + "\n"
doc.close()

# Find section boundaries
section_pattern = re.compile(r'\n([IVX]+)\.\s+([^\n]+?)\s*\n+', re.MULTILINE)
section_positions = []
seen_romans = set()
for m in section_pattern.finditer(full_text):
    roman = m.group(1)
    title = m.group(2).strip()
    if '....' in title or '......' in title:
        continue
    if roman not in seen_romans:
        section_positions.append((m.start(), roman, title))
        seen_romans.add(roman)

# Find all case entries
case_pattern = re.compile(
    r'([A-Z][A-Za-z\.\s]+?)\s+v\.\s+([A-Z][A-Za-z\.\s]+?)\s+\((\d{4})\)\s+(\d+\s+Cal\.\s*(?:App\.\d?)\s*\d+)',
    re.MULTILINE
)

case_positions = []
for m in case_pattern.finditer(full_text):
    case_name = m.group(0).strip()
    name = re.sub(r'\s*\(\d{4}\)\s*\d+\s+Cal\.\s*.*', '', case_name).strip()
    year = m.group(3)
    citation = m.group(4)
    start = m.start()
    case_positions.append((start, name, year, citation))

# Map cases to sections and extract clean descriptions
cases_by_section = {roman: [] for _, roman, _ in section_positions}

for start, name, year, citation in case_positions:
    # Find section
    current_section = section_positions[0][1] if section_positions else "I"
    for pos, roman, title in section_positions:
        if start >= pos:
            current_section = roman
        else:
            break
    
    # Get description - stop at next case or statutes
    rest = full_text[start:start+4000]
    next_case = re.search(r'\n([A-Z][A-Za-z\.]+\s+v\.\s+[A-Z][A-Za-z\.\s]+?)\s+\(\d{4}\)\s+\d+\s+Cal\.', rest[200:])
    statutes_match = re.search(r'\nStatutes used or affected:\s*', rest, re.IGNORECASE)
    
    if next_case:
        end = next_case.start() + 200
    elif statutes_match:
        end = statutes_match.start()
    else:
        end = min(4000, len(rest))
    
    raw_description = rest[:end].strip()
    
    # Remove page numbers, headers, footers
    raw_description = re.sub(r'\n+Case-Annotated.*?\n', '', raw_description)
    raw_description = re.sub(r'\n+\d+\n+', '\n', raw_description)
    
    # Remove the case name and citation from the beginning
    raw_description = re.sub(r'^' + re.escape(name) + r'\s*\(\d{4}\)\s*' + re.escape(citation) + r'\s*', '', raw_description).strip()
    
    # Clean up citation artifacts like "th 864" from "5th 864"
    raw_description = re.sub(r'\b(th|st|nd|rd)\s+\d+\b', '', raw_description)
    raw_description = re.sub(r'\s+', ' ', raw_description).strip()
    
    # Truncate to ~400 chars for callout
    if len(raw_description) > 400:
        raw_description = raw_description[:397] + "..."
    
    # Clean citation
    citation = re.sub(r'\b(th|st|nd|rd)\s+', ' ', citation)
    citation = re.sub(r'\s+', ' ', citation).strip()
    
    # Get statutes
    statutes = ""
    if statutes_match:
        statutes_text = rest[statutes_match.start():statutes_match.start()+500]
        statutes = re.sub(r'\nStatutes used or affected:\s*', '', statutes_text).strip()
        statutes = re.sub(r'\n.*', '', statutes).strip()
    
    cases_by_section[current_section].append({
        'name': name,
        'year': year,
        'citation': citation,
        'description': raw_description,
        'statutes': statutes
    })

with open('/Users/2024-jan/f/family-x1oh1xy2/_case_sections.json', 'w') as f:
    json.dump(cases_by_section, f, indent=2)

print("Section counts:")
for roman, cases in cases_by_section.items():
    print(f"  {roman}: {len(cases)} cases")

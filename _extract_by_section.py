import fitz, re, json
pdf_path = "/Users/2024-jan/Downloads/2026.06.08-Case-Annotated.pdf"
doc = fitz.open(pdf_path)

full_text = ""
for i in range(len(doc)):
    full_text += doc[i].get_text() + "\n"
doc.close()

# First, find section boundaries using Roman numerals
# The sections are: I, II, III, IV, V, VI, VII, VIII, IX, X, XI, XII, XIII, XIV
section_pattern = re.compile(
    r'\n([IVX]+)\.\s+([^\n]+?)\s*\n+',
    re.MULTILINE
)

section_positions = []
for m in section_pattern.finditer(full_text):
    roman = m.group(1)
    title = m.group(2).strip()
    # Only keep valid Roman numerals I-XIV
    if roman in ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII', 'XIII', 'XIV']:
        section_positions.append((m.start(), roman, title))

print(f"Found {len(section_positions)} sections")
for pos, roman, title in section_positions:
    print(f"  {roman}: {title[:60]}")

# Now find all case entries with their positions
case_pattern = re.compile(
    r'([A-Z][A-Za-z\.\s]+?)\s+v\.\s+([A-Z][A-Za-z\.\s]+?)\s+\((\d{4})\)\s+(\d+\s+Cal\.\s*(?:App\.\d?)\s*\d+)',
    re.MULTILINE
)

case_positions = []
for m in case_pattern.finditer(full_text):
    case_name = m.group(0).strip()
    # Clean up: remove citation from name
    name = re.sub(r'\s*\(\d{4}\)\s*\d+\s+Cal\.\s*.*', '', case_name).strip()
    year = m.group(3)
    citation = m.group(4)
    start = m.start()
    case_positions.append((start, name, year, citation))

print(f"\nFound {len(case_positions)} cases")

# Map each case to its section based on position
cases_by_section = {roman: [] for _, roman, _ in section_positions}

for start, name, year, citation in case_positions:
    # Find which section this case belongs to
    current_section = "I"  # default
    for pos, roman, title in section_positions:
        if start >= pos:
            current_section = roman
        else:
            break
    
    # Get description
    rest = full_text[start:start+3000]
    statutes_match = re.search(r'\nStatutes used or affected:\s*([^\n]+)', rest, re.IGNORECASE)
    next_case = re.search(r'\n([A-Z][A-Za-z\.]+\s+v\.\s+[A-Z][A-Za-z\.\s]+?)\s+\(\d{4}\)\s+\d+\s+Cal\.', rest[100:])
    
    if next_case:
        end = next_case.start() + 100
    elif statutes_match:
        end = statutes_match.start()
    else:
        end = min(3000, len(rest))
    
    description = rest[:end].strip()
    description = re.sub(r'\n+Case-Annotated.*?\n', '', description)
    description = re.sub(r'\n+\d+\n+', '\n', description)
    description = re.sub(r'\n+', ' ', description).strip()
    
    statutes = ""
    if statutes_match:
        statutes = statutes_match.group(1).strip()
    
    cases_by_section[current_section].append({
        'name': name,
        'year': year,
        'citation': citation,
        'description': description,
        'statutes': statutes
    })

# Save section mapping
with open('/Users/2024-jan/f/family-x1oh1xy2/_case_sections.json', 'w') as f:
    json.dump(cases_by_section, f, indent=2)

print("\nSection counts:")
for roman, cases in cases_by_section.items():
    print(f"  {roman}: {len(cases)} cases")

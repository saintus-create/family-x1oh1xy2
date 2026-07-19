import fitz, re, json
pdf_path = "/Users/2024-jan/Downloads/2026.06.08-Case-Annotated.pdf"
doc = fitz.open(pdf_path)

full_text = ""
for i in range(len(doc)):
    full_text += doc[i].get_text() + "\n"
doc.close()

# Better extraction: find all case entries
# Pattern: CaseName v. CaseName (year) Cal citation
# Ends at: "Statutes used or affected:" or next case

case_pattern = re.compile(
    r'([A-Z][A-Za-z\s\.]+v\.\s+[A-Z][A-Za-z\s\.]+)\s*\n'
    r'\((\d{4})\)\s+([^\n]*?Cal\.\s*(?:App\.\d?)\s*\d+[^\n]*)\s*\n+',
    re.MULTILINE
)

cases = []
for m in case_pattern.finditer(full_text):
    case_name = m.group(1).strip()
    year = m.group(2).strip()
    citation = m.group(3).strip()
    
    # Get text from start of this case to next case or statutes
    start = m.end()
    # Look ahead for next case or statutes section
    rest = full_text[start:start+4000]
    
    # Find next case
    next_case = re.search(r'\n([A-Z][A-Za-z\s\.]+v\.\s+[A-Z][A-Za-z\s\.]+)\s*\n\(\d{4}\)', rest)
    # Find statutes section
    statutes_match = re.search(r'\nStatutes used or affected:\s*([^\n]+)', rest, re.IGNORECASE)
    
    if next_case:
        description_end = next_case.start()
    elif statutes_match:
        description_end = statutes_match.start()
    else:
        description_end = min(4000, len(rest))
    
    description = rest[:description_end].strip()
    # Clean up: remove page numbers and footers
    description = re.sub(r'\n+\d+\n+', '\n', description)
    description = re.sub(r'\n+', ' ', description).strip()
    
    statutes = ""
    if statutes_match:
        statutes = statutes_match.group(1).strip()
        # Remove continuation from next case if present
        if next_case:
            statutes = statutes[:statutes.find('\n')].strip()
    
    cases.append({
        'name': case_name,
        'year': year,
        'citation': citation,
        'description': description[:500],  # Truncate for now
        'statutes': statutes
    })

print(f"Found {len(cases)} cases")
for c in cases[:8]:
    print(f"\n{c['name']} ({c['year']})")
    print(f"  Statutes: {c['statutes'][:120]}")

with open('/Users/2024-jan/f/family-x1oh1xy2/_case_entries.json', 'w') as f:
    json.dump(cases, f, indent=2)
print("\nSaved to _case_entries.json")

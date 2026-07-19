import fitz, re, json
pdf_path = "/Users/2024-jan/Downloads/2026.06.08-Case-Annotated.pdf"
doc = fitz.open(pdf_path)

full_text = ""
for i in range(len(doc)):
    full_text += doc[i].get_text() + "\n"
doc.close()

# Stricter pattern: case name v. case name (year) Cal citation
# Use non-greedy and restrict to single line
case_pattern = re.compile(
    r'([A-Z][A-Za-z\.]+\s+v\.\s+[A-Z][A-Za-z\.\s]+?)\s+\((\d{4})\)\s+(\d+\s+Cal\.\s*(?:App\.\d?)\s*\d+)',
    re.MULTILINE
)

cases = []
for m in case_pattern.finditer(full_text):
    case_name = m.group(1).strip()
    year = m.group(2)
    citation_num = m.group(3)
    start = m.start()
    
    # Get description from start to next case or statutes
    rest = full_text[start:start+3000]
    
    # Find next case or statutes
    next_case = re.search(r'\n([A-Z][A-Za-z\.]+\s+v\.\s+[A-Z][A-Za-z\.\s]+?)\s+\(\d{4}\)\s+\d+\s+Cal\.', rest[100:])
    statutes_match = re.search(r'\nStatutes used or affected:\s*([^\n]+)', rest, re.IGNORECASE)
    
    if next_case:
        end = next_case.start() + 100
    elif statutes_match:
        end = statutes_match.start()
    else:
        end = min(3000, len(rest))
    
    description = rest[:end].strip()
    # Remove footer text and page numbers
    description = re.sub(r'\n+Case-Annotated.*?\n', '', description)
    description = re.sub(r'\n+\d+\n+', '\n', description)
    description = re.sub(r'\n+', ' ', description).strip()
    
    statutes = ""
    if statutes_match:
        statutes = statutes_match.group(1).strip()
    
    cases.append({
        'name': case_name,
        'year': year,
        'citation': citation_num,
        'description': description[:800],
        'statutes': statutes
    })

print(f"Found {len(cases)} cases")
for c in cases[:8]:
    print(f"\n{c['name']} ({c['year']}) [{c['citation']}]")
    print(f"  Statutes: {c['statutes'][:120]}")
    print(f"  Desc: {c['description'][:200]}")

with open('/Users/2024-jan/f/family-x1oh1xy2/_case_entries.json', 'w') as f:
    json.dump(cases, f, indent=2)
print("\nSaved to _case_entries.json")

import fitz, re, json
pdf_path = "/Users/2024-jan/Downloads/2026.06.08-Case-Annotated.pdf"
doc = fitz.open(pdf_path)

full_text = ""
for i in range(len(doc)):
    full_text += doc[i].get_text() + "\n"
doc.close()

# Split into pages to understand section boundaries
pages = full_text.split('\nCase-Annotated Compendium of California Domestic Violence Laws \nFamily Violence Appellate Project')

# The first page contains TOC
# Pages 8+ contain actual content

# Let's extract case entries - they have pattern:
# CaseName v. CaseName (year) Cal citation
# Followed by facts/analysis
# Then "Statutes used or affected:" line

case_entries = []
case_pattern = re.compile(
    r'([A-Z][A-Za-z\s\.]+\s+v\.\s+[A-Z][A-Za-z\s\.]+)\s*\n*'
    r'\((\d{4})\)\s+([^\n]*?Cal\.\s*(?:App\.\d?)\s*\d+[^\n]*)',
    re.MULTILINE
)

for m in case_pattern.finditer(full_text):
    case_name = m.group(1).strip()
    year = m.group(2).strip()
    citation = m.group(3).strip()
    
    # Find the statutes section after this case
    start = m.start()
    rest = full_text[start:start+3000]
    
    # Find statutes line
    statutes_match = re.search(r'Statutes used or affected:\s*([^\n]+)', rest, re.IGNORECASE)
    if statutes_match:
        statutes_text = statutes_match.group(1).strip()
    else:
        statutes_text = ""
    
    case_entries.append({
        'name': case_name,
        'year': year,
        'citation': citation,
        'statutes': statutes_text
    })

print(f"Found {len(case_entries)} cases")
for c in case_entries[:10]:
    print(f"\n{c['name']} ({c['year']})")
    print(f"  Statutes: {c['statutes'][:150]}")

with open('/Users/2024-jan/f/family-x1oh1xy2/_case_entries.json', 'w') as f:
    json.dump(case_entries, f, indent=2)
print("\nSaved to _case_entries.json")

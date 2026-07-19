import fitz, re, json
pdf_path = "/Users/2024-jan/Downloads/2026.06.08-Case-Annotated.pdf"
doc = fitz.open(pdf_path)

# Extract all text
full_text = ""
for i in range(len(doc)):
    full_text += doc[i].get_text() + "\n"
doc.close()

# Find case entries - they typically have case names in italics or caps
# followed by citation info
cases = []

# Split by major sections
sections = re.split(r'\n([IVX]+\.\s)', full_text)

# Look for case patterns: case name, citation, holding
case_pattern = re.compile(
    r'([A-Z][a-zA-Z\s\.]+v\.\s[A-Za-zA-Z\s\.]+)\s*\n'
    r'([^\(]{0,50}?\d{4})\s*'
    r'([^\n]+?Cal\.\s*(?:App\.\d?|Superior|Supreme)\s*[^\n]*)',
    re.MULTILINE | re.DOTALL
)

for match in case_pattern.finditer(full_text[:50000]):  # first 50k chars
    cases.append({
        'name': match.group(1).strip(),
        'year': match.group(2).strip(),
        'citation': match.group(3).strip()[:200]
    })

print(f"Found {len(cases)} cases in first 50k chars")
for c in cases[:5]:
    print(f"\n{c['name']} ({c['year']})")
    print(f"  {c['citation']}")

# Save raw text for manual review
with open('/Users/2024-jan/f/family-x1oh1xy2/_case_raw.txt', 'w') as f:
    f.write(full_text[:30000])
print("\nRaw text saved to _case_raw.txt")

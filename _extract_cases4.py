import fitz, re, json
pdf_path = "/Users/2024-jan/Downloads/2026.06.08-Case-Annotated.pdf"
doc = fitz.open(pdf_path)

full_text = ""
for i in range(len(doc)):
    full_text += doc[i].get_text() + "\n"
doc.close()

# Look at actual format around case names
# Let's find all " v. " patterns and see context
matches = list(re.finditer(r'([A-Z][A-Za-z\.]+)\s+v\.\s+([A-Z][A-Za-z\.]+)\s*\((\d{4})\)', full_text[:50000]))
print(f"Found {len(matches)} case patterns")
for m in matches[:10]:
    print(f"  {m.group(0)}")

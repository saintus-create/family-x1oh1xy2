import fitz, re
pdf_path = "/Users/2024-jan/Downloads/2026.06.08-Case-Annotated.pdf"
doc = fitz.open(pdf_path)
print(f"Pages: {len(doc)}")

# Extract TOC from first few pages
toc_text = ""
for i in range(min(6, len(doc))):
    toc_text += doc[i].get_text()

# Find the table of contents entries
lines = toc_text.split('\n')
for line in lines:
    line = line.strip()
    if re.match(r'^[A-Z]\.\s', line) or re.match(r'^[IVX]+\.\s', line):
        print(line)

doc.close()

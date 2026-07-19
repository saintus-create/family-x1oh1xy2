import fitz
pdf_path = "/Users/2024-jan/Downloads/2026.06.08-Case-Annotated.pdf"
doc = fitz.open(pdf_path)
print(f"Pages: {len(doc)}")
for i in range(min(10, len(doc))):
    text = doc[i].get_text()
    if text.strip():
        print(f"\n--- Page {i+1} ---")
        print(text[:2000])
doc.close()

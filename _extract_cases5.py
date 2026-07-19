import fitz, re, json
pdf_path = "/Users/2024-jan/Downloads/2026.06.08-Case-Annotated.pdf"
doc = fitz.open(pdf_path)

full_text = ""
for i in range(len(doc)):
    full_text += doc[i].get_text() + "\n"
doc.close()

# Find all case positions
case_pattern = re.compile(
    r'([A-Z][A-Za-z\.\s]+?)\s+v\.\s+([A-Z][A-Za-z\.\s]+?)\s+\((\d{4})\)',
    re.MULTILINE
)

case_positions = []
for m in case_pattern.finditer(full_text):
    name = m.group(0).strip()
    # Clean up - remove extra spaces and trailing (year) from name
    case_name = re.sub(r'\s*\(\d{4}\)\s*', '', name).strip()
    year = m.group(3)
    start = m.start()
    case_positions.append((start, case_name, year))

print(f"Found {len(case_positions)} case positions")
for pos, name, year in case_positions[:10]:
    print(f"  {pos}: {name} ({year})")

"""검증 스크립트"""
from docx import Document

doc = Document(r"T:\Gits\Web-GIS 기반 현황분석 자동화\2-1_소유자별_현황.docx")
ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

for idx, el in enumerate(doc.element.body):
    tag = el.tag.split("}")[-1]
    if tag == "p":
        txt = el.text or ""
        print(f"[{idx}] P: {txt[:80]}")
    elif tag == "tbl":
        rows = el.findall(f".//{ns}tr")
        print(f"[{idx}] Table ({len(rows)} rows):")
        for j, row in enumerate(rows):
            cells = row.findall(f"{ns}tc")
            cell_txts = []
            for c in cells:
                ts = [t.text for t in c.findall(f".//{ns}t") if t.text]
                cell_txts.append(" ".join(ts) if ts else "")
            print(f"  R{j}: {cell_txts}")

from docx import Document
from docx.shared import Pt, Cm
doc = Document(r'e:\桌面\测试\深圳人保-王玉香报告.docx')
print('=== 段落分析 ===')
for i, p in enumerate(doc.paragraphs):
    text = p.text.strip()
    if not text:
        continue
    style_name = p.style.name if p.style else 'None'
    alignment = str(p.alignment) if p.alignment else 'None'
    runs_info = []
    for r in p.runs:
        font = r.font
        runs_info.append({
            'text': r.text[:30],
            'bold': font.bold,
            'size': str(font.size) if font.size else 'None',
            'font_name': font.name
        })
    print(f'P{i}: [{style_name}] align={alignment} text={text[:80]}')
    for ri in runs_info:
        print(f'   Run: bold={ri["bold"]} size={ri["size"]} font={ri["font_name"]} text={ri["text"][:50]}')

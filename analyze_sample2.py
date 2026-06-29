# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

from docx import Document
from docx.shared import Pt, Cm

doc = Document(r'e:\桌面\测试\深圳人保-王玉香报告.docx')

with open(r'e:\案件处理启动器\sample_analysis.txt', 'w', encoding='utf-8') as f:
    f.write('=== 段落分析 ===\n')
    for i, p in enumerate(doc.paragraphs):
        text = p.text.strip()
        if not text:
            continue
        style_name = p.style.name if p.style else 'None'
        alignment = str(p.alignment) if p.alignment else 'None'
        f.write(f'P{i}: [{style_name}] align={alignment} text={text[:80]}\n')
        for r in p.runs:
            font = r.font
            f.write(f'   Run: bold={font.bold} size={str(font.size) if font.size else "None"} font={font.name} text={r.text[:50]}\n')
    
    # 检查页面设置
    section = doc.sections[0]
    f.write(f'\n=== 页面设置 ===\n')
    f.write(f'页面宽度: {section.page_width}\n')
    f.write(f'页面高度: {section.page_height}\n')
    f.write(f'左边距: {section.left_margin}\n')
    f.write(f'右边距: {section.right_margin}\n')
    f.write(f'上边距: {section.top_margin}\n')
    f.write(f'下边距: {section.bottom_margin}\n')

print('分析完成，结果已写入 sample_analysis.txt')

import re
import ast

filepath = r"e:\案件处理启动器\combined_backend.py"

with open(filepath, "r", encoding="utf-8-sig", errors="replace") as f:
    lines = f.readlines()

# 找出所有可能有问题的行
problem_patterns = [
    r'\?\)$',           # 末尾的 ?)
    r'\?"$',            # 末尾的 ?"
    r"'\?$",            # 末尾的 '?
    r'^[^"]*"[^"]*$',   # 未闭合的引号
    r"^[^']*'[^']*$",   # 未闭合的单引号
]

# 修复策略
fixes = {
    "PaddleOCR ?": "PaddleOCR",
    "PaddleOCR...": "PaddleOCR",
    "OCR ?": "OCR",
    "OCR...": "OCR",
    "PADDLE_OCR_TIMEOUT}": "PADDLE_OCR_TIMEOUT}",
}

new_lines = []
for i, line in enumerate(lines):
    # 跳过完全损坏的行（只有引号或问号）
    stripped = line.strip()
    if stripped in ['"', "'", '"', "'", '?', '"', "'"]:
        continue
    
    # 应用修复
    new_line = line
    for old, new in fixes.items():
        if old in new_line:
            new_line = new_line.replace(old, new)
    
    new_lines.append(new_line)

with open(filepath, "w", encoding="utf-8-sig") as f:
    f.writelines(new_lines)

print("Batch fix applied!")

# 验证语法
try:
    with open(filepath, "r", encoding="utf-8-sig") as f:
        ast.parse(f.read())
    print("Syntax check passed!")
except SyntaxError as e:
    print(f"Syntax error at line {e.lineno}: {e.msg}")

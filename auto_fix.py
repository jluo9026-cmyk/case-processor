import re
import ast

filepath = r"e:\案件处理启动器\combined_backend.py"

def check_syntax():
    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            ast.parse(f.read())
        return True, None
    except SyntaxError as e:
        return False, e

def fix_line(line_num):
    with open(filepath, "r", encoding="utf-8-sig", errors="replace") as f:
        lines = f.readlines()
    
    if line_num <= len(lines):
        line = lines[line_num - 1]
        print(f"Line {line_num}: {repr(line[:60])}")
        
        # 尝试修复常见的损坏模式
        # 如果行以引号开头或结尾，可能是被拆分的字符串
        stripped = line.strip()
        if stripped.endswith('"') or stripped.endswith("'"):
            # 检查下一行
            if line_num < len(lines):
                next_line = lines[line_num]
                print(f"  Next line: {repr(next_line[:60])}")
    else:
        print(f"Line {line_num} does not exist")

# 循环修复
max_iterations = 50
for i in range(max_iterations):
    ok, error = check_syntax()
    if ok:
        print(f"Syntax OK after {i} iterations!")
        break
    
    print(f"Iteration {i+1}: Error at line {error.lineno}")
    fix_line(error.lineno)
    
    # 尝试自动修复
    with open(filepath, "r", encoding="utf-8-sig", errors="replace") as f:
        lines = f.readlines()
    
    line_num = error.lineno - 1  # 0-indexed
    
    # 检查是否是未闭合的引号
    line = lines[line_num]
    
    # 简单修复：如果是未闭合的字符串，添加闭合引号
    if "= '" in line or '= "' in line:
        # 检查是否缺少闭合引号
        if line.count("'") % 2 != 0:
            lines[line_num] = line.rstrip() + "'\n"
        elif line.count('"') % 2 != 0:
            lines[line_num] = line.rstrip() + '"\n'
    
    with open(filepath, "w", encoding="utf-8-sig") as f:
        f.writelines(lines)
else:
    print("Max iterations reached")

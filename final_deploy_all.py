"""
最后一次部署脚本 - 用户在自己电脑上直接运行
"""
import subprocess, os

BASE = r"e:\案件处理启动器"
os.chdir(BASE)

# 1. 建立远程仓库连接（不带Token，手动认证）
print("Step 1: 设置远程仓库...")
subprocess.run(["git", "remote", "set-url", "origin",
    "https://github.com/jluo9026-cmyk/case-processor.git"],
    capture_output=True)

# 2. 只添加我们需要的核心文件
print("Step 2: 添加核心文件...")
core_files = [
    "index.html",              # 工具启动器主页
    "combined_backend.py",     # 后端API
    "renderer.js",             # 主页脚本
    "requirements.txt",        # 依赖
    "tools/renderer.js",       # 审批表工具
    "tools/index4.html",       # 目录工具
    "tools/index3.html",       # 结案审批表
    "tools/report_generate/index.html",    # 报告生成工具
    "tools/report_generate/report_generate.js",  # 报告生成脚本
    "tools/report_generate/style.css",     # 报告生成样式
    "templates/index.html",               # 报告标准化页面
    "static/js/app.js",                   # 报告标准化脚本
    "static/css/style.css",               # 报告标准化样式
    "Dockerfile",
    "render.yaml",
    "template_preset_1.docx",
    "template_preset_2.docx",
    "template_preset_3.docx",
    "modules/app_core.py",
    "modules/config.py",
    "modules/routes.py",
    "modules/docx_merge.py",
    "modules/helpers.py",
    "modules/template_data.py",
    "modules/ocr_service.py",
    "modules/__init__.py",
]

for f in core_files:
    fp = os.path.join(BASE, f)
    if os.path.exists(fp):
        subprocess.run(["git", "add", "-f", f], capture_output=True)
        print(f"  + {f}")
    else:
        print(f"  ! {f} (NOT FOUND)")

# 3. 设置代理并推送
print("\nStep 3: 提交并推送...")
result = subprocess.run(["git", "commit", "-m", "完整部署：全部5个工具+案件启动器主页"],
                       capture_output=True, text=True)

# 4. 用代理推送（如果VPN开着）
env = os.environ.copy()
env["HTTP_PROXY"] = "http://127.0.0.1:7890"
env["HTTPS_PROXY"] = "http://127.0.0.1:7890"
env["http_proxy"] = "http://127.0.0.1:7890"
env["https_proxy"] = "http://127.0.0.1:7890"

print("推送中（会弹出GitHub登录窗口）...")
result = subprocess.run(
    ["git", "push", "origin", "main", "--force"],
    capture_output=True, text=True, timeout=120, env=env
)
print("STDOUT:", result.stdout[:500])
print("STDERR:", result.stderr[:500])
print("Return:", result.returncode)

if result.returncode == 0:
    print("\n✅ 推送成功！现在去 Render Dashboard 点 Manual Deploy")
    print("https://dashboard.render.com/web/srv-d916j377f7vs73d6h240")
else:
    print("\n❌ 推送失败，请检查VPN或GitHub登录")
    print("或者手动执行: git push origin main --force")
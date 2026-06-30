"""
在您自己电脑上运行此脚本：一键推送所有核心文件到GitHub
打开命令提示符(cmd) -> cd e:\案件处理启动器 -> python push_all.py
"""
import subprocess, os

os.chdir(r"e:\案件处理启动器")

# 核心文件清单（确保这些文件必须上传）
FILES = [
    "index.html", "combined_backend.py", "renderer.js", "requirements.txt",
    "tools/renderer.js", "tools/index4.html", "tools/index3.html",
    "tools/report_generate/index.html", "tools/report_generate/report_generate.js",
    "templates/index.html", "static/js/app.js", "static/css/style.css",
    "Dockerfile", "template_preset_1.docx", "template_preset_2.docx", "template_preset_3.docx",
    "modules/app_core.py", "modules/config.py", "modules/routes.py",
    "modules/docx_merge.py", "modules/helpers.py", "modules/template_data.py",
    "modules/ocr_service.py", "modules/__init__.py",
    "tools/report_generate/style.css",
]

print("=" * 50)
print("一键推送工具 - 案件处理启动器完整部署")
print("=" * 50)

# Step 1: 设置远程仓库（不含Token，推送时会弹窗登录）
subprocess.run(["git", "remote", "set-url", "origin",
    "https://github.com/jluo9026-cmyk/case-processor.git"],
    capture_output=True)

# Step 2: 添加所有核心文件
print("\n添加核心文件...")
count = 0
for f in FILES:
    if os.path.exists(f):
        subprocess.run(["git", "add", "-f", f], capture_output=True)
        print(f"  ✓ {f}")
        count += 1
    else:
        print(f"  ✗ {f} (不存在)")

print(f"\n共添加 {count} 个文件")

# Step 3: 提交
subprocess.run(["git", "commit", "-m", "完整部署：案件启动器主页+5个工具完整功能"],
               capture_output=True)

# Step 4: 强制推送（会弹出GitHub登录窗口）
print("\n开始推送到 GitHub...")
print("如果弹出GitHub登录窗口，请用浏览器登录。")
print("等待推送完成...\n")

result = subprocess.run(
    ["git", "push", "origin", "main", "--force"],
    capture_output=True, text=True, timeout=120
)

print("STDOUT:", result.stdout[-500:])
print("STDERR:", result.stderr[-500:])
print("状态码:", result.returncode)

if result.returncode == 0:
    print("\n" + "=" * 50)
    print("✅ 推送成功！")
    print("\n请手动触发 Render 部署：")
    print("1. 打开 https://dashboard.render.com/web/srv-d916j377f7vs73d6h240")
    print("2. 点击 Manual Deploy → Deploy latest commit")
    print("3. 等待3分钟")
    print("4. 打开 https://case-processor.onrender.com")
    print("=" * 50)
else:
    print("\n❌ 推送失败")
    print("\n请手动执行：")
    print("  git push origin main --force")
    print("（会弹出GitHub登录窗口）")
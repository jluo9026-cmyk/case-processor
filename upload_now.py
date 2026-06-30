"""在您电脑上运行此脚本，自动上传 combined_backend.py 到 GitHub"""
import subprocess, os

os.chdir(r"e:\案件处理启动器")

# 添加文件并提交
subprocess.run(["git", "add", "combined_backend.py", "index.html"], capture_output=True)
subprocess.run(["git", "commit", "-m", "修复附件处理器路由"], capture_output=True)

# 推送
print("正在推送到 GitHub...")
r = subprocess.run(["git", "push", "origin", "main", "--force"], 
                   capture_output=True, text=True, timeout=120)
print(r.stdout[-500:])
print(r.stderr[-500:])

if r.returncode == 0:
    print("\n✅ 推送成功！请告诉我，我触发部署")
else:
    print("\n❌ 推送失败，请手动执行: git push origin main --force")
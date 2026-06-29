"""
通过 HTTP 代理推送代码到 GitHub
"""
import subprocess, os

os.chdir(r"e:\案件处理启动器")

# Set proxy in environment
env = os.environ.copy()
env["HTTP_PROXY"] = "http://127.0.0.1:7890"
env["HTTPS_PROXY"] = "http://127.0.0.1:7890"

# Set git remote with token
subprocess.run([
    "git", "remote", "set-url", "origin",
    "https://jluo9026-cmyk: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@github.com/jluo9026-cmyk/case-processor.git"
], capture_output=True, text=True, env=env)

# Push
r = subprocess.run(["git", "push", "origin", "main"],
                   capture_output=True, text=True, timeout=120, env=env)
print("STDOUT:", r.stdout[-1000:])
print("STDERR:", r.stderr[-1000:])
print("Return:", r.returncode)

if r.returncode == 0:
    print("\n=== PUSH SUCCESS! ===")
else:
    # Try without proxy
    print("\nTrying without proxy...")
    r2 = subprocess.run(["git", "push", "origin", "main"],
                       capture_output=True, text=True, timeout=120)
    print("STDOUT:", r2.stdout[-500:])
    print("STDERR:", r2.stderr[-500:])
    print("Return:", r2.returncode)
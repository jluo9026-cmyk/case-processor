import subprocess, os

os.chdir(r"e:\案件处理启动器")

# Set proxy in env
env = os.environ.copy()
env["HTTP_PROXY"] = "http://127.0.0.1:7890"
env["HTTPS_PROXY"] = "http://127.0.0.1:7890"
env["http_proxy"] = "http://127.0.0.1:7890"
env["https_proxy"] = "http://127.0.0.1:7890"

# Set remote
subprocess.run([
    "git", "remote", "set-url", "origin",
    "https://jluo9026-cmyk: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@github.com/jluo9026-cmyk/case-processor.git"
], capture_output=True, text=True, env=env)

# Git push with proxy
result = subprocess.run(
    ["git", "-c", "http.proxy=http://127.0.0.1:7890", 
     "-c", "https.proxy=http://127.0.0.1:7890",
     "push", "origin", "main"],
    capture_output=True, text=True, timeout=120
)

with open(r"e:\案件处理启动器\push_out.txt", "w", encoding="utf-8") as f:
    f.write("STDOUT:\n" + result.stdout)
    f.write("\n\nSTDERR:\n" + result.stderr)
    f.write(f"\n\nReturn: {result.returncode}")

print("Done. Check push_out.txt")
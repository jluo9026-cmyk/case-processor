import subprocess, os, sys

os.chdir(r"e:\案件处理启动器")

# Setup remote with token
remote_url = "https://jluo9026-cmyk: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@github.com/jluo9026-cmyk/case-processor.git"

subprocess.run(["git", "remote", "set-url", "origin", remote_url],
               capture_output=True, text=True)

r = subprocess.run(["git", "push", "origin", "main"],
                   capture_output=True, text=True, timeout=120)
print("STDOUT:", r.stdout[-800:])
print("STDERR:", r.stderr[-800:])
print("Return:", r.returncode)

if r.returncode == 0:
    print("\nPUSH SUCCESS!")
else:
    print("\nPUSH FAILED!")
    sys.exit(1)
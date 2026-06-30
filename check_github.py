"""Check what's on GitHub and trigger a new Render deploy"""
import json, os, subprocess

# Step 1: Check git status
os.chdir(r"e:\案件处理启动器")

local = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
remote = subprocess.run(["git", "rev-parse", "origin/main"], capture_output=True, text=True).stdout.strip()

print(f"Local HEAD:  {local[:12]}")
print(f"Remote HEAD: {remote[:12]}")
print(f"Match: {local == remote}")

# Step 2: Check what files are at the remote
# List changed files between our local and remote
diff = subprocess.run(["git", "diff", "--name-only", "HEAD", "origin/main"], capture_output=True, text=True).stdout
if diff:
    print(f"\nFiles different from remote:\n{diff[:500]}")
else:
    print("\nNo diff - local and remote are in sync")

# Step 3: Verify key files exist with our changes
for f in ["combined_backend.py", "renderer.js", "requirements.txt", "tools/renderer.js", "tools/index4.html"]:
    exists = os.path.exists(f)
    size = os.path.getsize(f) if exists else 0
    print(f"  {'✅' if exists else '❌'} {f} ({size} bytes)")

print("\nTo fix: if local and remote differ, run:")
print("git push origin main --force")
import json, urllib.request, sys, time

TOKEN = "rnd_c4M2wYpZtw9mkOtbXRzIRb4PmeOt"
SERVICE = "srv-d916j377f7vs73d6h240"

# 1. Check git status
print("=== GIT STATUS ===")
import subprocess
local = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=r"e:\案件处理启动器").stdout.strip()
remote = subprocess.run(["git", "rev-parse", "origin/main"], capture_output=True, text=True, cwd=r"e:\案件处理启动器").stdout.strip()
print(f"Local HEAD:  {local[:12]}")
print(f"Remote HEAD: {remote[:12]}")
print(f"Match: {local == remote}")

if local != remote:
    print("\nPushing latest code...")
    r = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True, cwd=r"e:\案件处理启动器", timeout=60)
    print(r.stdout[-300:] if len(r.stdout) > 300 else r.stdout)
    # Re-check
    remote = subprocess.run(["git", "rev-parse", "origin/main"], capture_output=True, text=True, cwd=r"e:\案件处理启动器").stdout.strip()
    print(f"After push - Remote: {remote[:12]}, Match: {local == remote}")

# 2. Check deploy status
print("\n=== RENDER DEPLOY STATUS ===")
req = urllib.request.Request(f"https://api.render.com/v1/services/{SERVICE}/deploys?limit=1", headers={"Authorization": f"Bearer {TOKEN}"})
data = json.loads(urllib.request.urlopen(req).read().decode())
d = data[0]["deploy"]
print(f"Status: {d['status']}")
print(f"Commit ID: {d.get('commit',{}).get('id','')[:12]}")
print(f"Message: {d.get('commit',{}).get('message','')}")

# 3. If latest commit not deployed, trigger new deploy
commit_id = d.get("commit",{}).get("id","")
if local[:12] not in commit_id and d["status"] != "live":
    print(f"\nTriggering new deploy for commit {local[:12]}...")
    req = urllib.request.Request(
        f"https://api.render.com/v1/services/{SERVICE}/deploys",
        data=json.dumps({"clearCache": "clear"}).encode(),
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    )
    resp = json.loads(urllib.request.urlopen(req).read().decode())
    print(f"New Deploy ID: {resp.get('id')}")

# 4. Try accessing the website
print("\n=== WEBSITE CHECK ===")
try:
    resp = urllib.request.urlopen("https://case-processor.onrender.com", timeout=10)
    print(f"HTTP {resp.status} - Website is accessible!")
except Exception as e:
    print(f"Website not accessible yet: {str(e)[:80]}")
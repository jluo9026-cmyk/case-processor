
import subprocess, os, json, urllib.request, time, sys

os.chdir(r"e:\案件处理启动器")

# 1. Push to GitHub
print("=" * 50)
print("STEP 1: Git Push")
print("=" * 50)
result = subprocess.run(
    ["git", "push", "origin", "main"],
    capture_output=True, text=True, timeout=60
)
print("STDOUT:", result.stdout)
print("STDERR:", result.stderr)
print("Return:", result.returncode)

if result.returncode != 0 and "Everything up-to-date" not in result.stdout:
    print("Push failed, retrying with explicit remote...")
    subprocess.run(["git", "remote", "set-url", "origin",
        "https://jluo9026-cmyk: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@github.com/jluo9026-cmyk/case-processor.git"],
        capture_output=True)
    result = subprocess.run(["git", "push", "origin", "main"],
        capture_output=True, text=True, timeout=60)
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)

# 2. Verify the commit is on remote
print("\n" + "=" * 50)
print("STEP 2: Verify Remote")
print("=" * 50)
local = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
remote = subprocess.run(["git", "rev-parse", "origin/main"], capture_output=True, text=True).stdout.strip()
print(f"Local HEAD:  {local[:12]}")
print(f"Remote HEAD: {remote[:12]}")
print(f"Match: {local == remote}")

if local != remote:
    print("Remote not updated! Aborting deploy.")
    sys.exit(1)

# 3. Trigger Render deploy
print("\n" + "=" * 50)
print("STEP 3: Trigger Render Deploy")
print("=" * 50)
TOKEN = "rnd_c4M2wYpZtw9mkOtbXRzIRb4PmeOt"
SERVICE = "srv-d916j377f7vs73d6h240"

req = urllib.request.Request(
    f"https://api.render.com/v1/services/{SERVICE}/deploys",
    data=json.dumps({"clearCache": "clear"}).encode(),
    headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
)
resp = urllib.request.urlopen(req).read().decode()
deploy = json.loads(resp)
print(f"Deploy ID: {deploy.get('id')}")
print(f"Status: {deploy.get('status')}")

# 4. Wait for deploy
print("\n" + "=" * 50)
print("STEP 4: Wait for Deploy")
print("=" * 50)
for i in range(8):
    time.sleep(30)
    req = urllib.request.Request(
        f"https://api.render.com/v1/services/{SERVICE}/deploys?limit=1",
        headers={"Authorization": f"Bearer {TOKEN}"}
    )
    data = json.loads(urllib.request.urlopen(req).read())
    d = data[0]["deploy"]
    status = d["status"]
    print(f"[{i*30+30}s] Status: {status}")
    if status == "live":
        print("\n" + "✅" * 10)
        print("✅  DEPLOYMENT SUCCESSFUL!")
        print(f"🌐  https://case-processor.onrender.com")
        sys.exit(0)
    elif "failed" in status:
        print(f"\n❌ Failed: {status}")
        sys.exit(1)

print("\nStill building. Check: https://dashboard.render.com/web/" + SERVICE)
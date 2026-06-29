"""
Final deploy script - pushes code and triggers Render deployment
"""
import json
import urllib.request
import subprocess
import time
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Step 1: Git push
print("=" * 50)
print("STEP 1: Push code to GitHub")
print("=" * 50)
result = subprocess.run(
    ["git", "push", "origin", "main"],
    capture_output=True, text=True, timeout=60
)
print(result.stdout[-200:] if len(result.stdout) > 200 else result.stdout)
if result.returncode != 0:
    print("STDERR:", result.stderr[-200:])

# Step 2: Trigger Render deploy
print("\n" + "=" * 50)
print("STEP 2: Trigger Render deploy")
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
deploy_data = json.loads(resp)
print(f"Deploy ID: {deploy_data.get('id')}")
print(f"Status: {deploy_data.get('status')}")

# Step 3: Wait and check
print("\n" + "=" * 50)
print("STEP 3: Wait for deploy (checking every 30s)")
print("=" * 50)

for i in range(10):
    time.sleep(30)
    
    req = urllib.request.Request(
        f"https://api.render.com/v1/services/{SERVICE}/deploys?limit=1",
        headers={"Authorization": f"Bearer {TOKEN}"}
    )
    resp = urllib.request.urlopen(req).read().decode()
    data = json.loads(resp)
    dep = data[0]["deploy"] if isinstance(data, list) else data
    
    status = dep["status"]
    print(f"[{i*30+30}s] Status: {status}")
    
    if status == "live":
        print("\n" + "✅" * 10)
        print("✅  DEPLOYMENT SUCCESSFUL!")
        print("✅" * 10)
        print(f"\n🌐  Access at: https://case-processor.onrender.com")
        sys.exit(0)
    elif "failed" in status:
        print(f"\n❌ Deploy failed: {status}")
        sys.exit(1)

print("\n⏳ Still building, check Render dashboard:")
print("https://dashboard.render.com/web/" + SERVICE)
import urllib.request
import json
import sys

TOKEN = "rnd_c4M2wYpZtw9mkOtbXRzIRb4PmeOt"
SERVICE = "srv-d916j377f7vs73d6h240"

# Step 1: Check if current version has our new feature
print("Checking current deployed version...")
try:
    req = urllib.request.Request(
        "https://case-processor.onrender.com/tools/report_generate/report_generate.js",
        headers={"User-Agent": "Mozilla/5.0"}
    )
    resp = urllib.request.urlopen(req, timeout=15)
    js_content = resp.read().decode("utf-8")
    
    if "openOcrDetails" in js_content:
        print("SUCCESS: New version is already deployed!")
        print("The OCR details modal feature is live.")
        sys.exit(0)
    else:
        print("OLD version is still running. Triggering new deploy...")
except Exception as e:
    print(f"Warning: Could not check version ({e}). Will trigger deploy anyway.")

# Step 2: Trigger Render deploy
print("\nTriggering Render deploy...")
try:
    data = json.dumps({"clearCache": "clear"}).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.render.com/v1/services/{SERVICE}/deploys",
        data=data,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json"
        }
    )
    resp = urllib.request.urlopen(req, timeout=30)
    result = json.loads(resp.read().decode("utf-8"))
    print(f"Deploy ID: {result.get('id')}")
    print(f"Status: {result.get('status')}")
    print(f"Created: {result.get('createdAt')}")
    print("\nDeploy triggered! Wait ~2-3 minutes.")
    print("After that, open: https://case-processor.onrender.com/tools/report_generate/index.html")
except Exception as e:
    print(f"Error triggering deploy: {e}")
    sys.exit(1)
</write_to_file>
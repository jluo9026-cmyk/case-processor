import json, urllib.request, time, sys

print("=" * 50)
print("Triggering Render Deploy")
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

print("\nWaiting for deploy...")
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
        print("\n" + "[OK]" * 10)
        print("[OK] DEPLOYMENT SUCCESSFUL!")
        print("[WEB] https://case-processor.onrender.com")
        sys.exit(0)
    elif "failed" in status:
        print(f"\n[FAILED] Failed: {status}")
        sys.exit(1)

print("\nStill building. Check: https://dashboard.render.com/web/" + SERVICE)
</write_to_file>
import json, urllib.request

TOKEN = "rnd_c4M2wYpZtw9mkOtbXRzIRb4PmeOt"
SERVICE = "srv-d916j377f7vs73d6h240"

req = urllib.request.Request(f"https://api.render.com/v1/services/{SERVICE}/deploys?limit=1")
req.add_header("Authorization", f"Bearer {TOKEN}")
resp = urllib.request.urlopen(req).read().decode()
data = json.loads(resp)
dep = data[0]["deploy"] if isinstance(data, list) else data

print("=" * 50)
print("DEPLOY STATUS CHECK")
print("=" * 50)
print(f"Status:      {dep['status']}")
print(f"Commit msg:  {dep.get('commit', {}).get('message', 'N/A')}")
print(f"Finished at: {dep.get('finishedAt', 'in progress')}")

if dep['status'] == 'live':
    print("\n✅  DEPLOYMENT SUCCESSFUL!")
    print("   URL: https://case-processor.onrender.com")
elif dep['status'] == 'build_in_progress':
    print("\n⏳  Building... check back in 2-3 minutes")
elif 'failed' in dep['status']:
    print(f"\n❌  Deploy failed: {dep['status']}")
    print("   Check Render dashboard for logs")
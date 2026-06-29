import json, urllib.request

TOKEN = "rnd_c4M2wYpZtw9mkOtbXRzIRb4PmeOt"
SERVICE = "srv-d916j377f7vs73d6h240"

# Check service info
req1 = urllib.request.Request(
    f"https://api.render.com/v1/services/{SERVICE}",
    headers={"Authorization": f"Bearer {TOKEN}"}
)
svc = json.loads(urllib.request.urlopen(req1).read())
print("Service URL:", svc.get("serviceDetails", {}).get("url"))
print("Suspended:", svc.get("suspended"))

# Check latest deploy
req2 = urllib.request.Request(
    f"https://api.render.com/v1/services/{SERVICE}/deploys?limit=1",
    headers={"Authorization": f"Bearer {TOKEN}"}
)
data = json.loads(urllib.request.urlopen(req2).read())
dep = data[0]["deploy"]
print("\nLatest Deploy:")
print("  Status:", dep["status"])
print("  Commit:", dep.get("commit", {}).get("message", ""))
print("  Finished:", dep.get("finishedAt", "still building"))
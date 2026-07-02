import json, urllib.request, sys

TOKEN = "rnd_c4M2wYpZtw9mkOtbXRzIRb4PmeOt"
SERVICE = "srv-d916j377f7vs73d6h240"

try:
    # Trigger deploy
    print("Triggering deploy...")
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
    print("\nDeploy triggered! You can check progress at:")
    print("https://dashboard.render.com/web/" + SERVICE)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
</write_to_file>
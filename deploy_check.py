import json, urllib.request, time, sys

TOKEN = "rnd_c4M2wYpZtw9mkOtbXRzIRb4PmeOt"
SERVICE_ID = "srv-d916j377f7vs73d6h240"

def get_deploy():
    req = urllib.request.Request(
        f"https://api.render.com/v1/services/{SERVICE_ID}/deploys?limit=1"
    )
    req.add_header("Authorization", f"Bearer {TOKEN}")
    resp = urllib.request.urlopen(req, timeout=10).read().decode()
    data = json.loads(resp)
    return data[0]["deploy"] if isinstance(data, list) else data

# Wait up to 5 minutes
for i in range(15):
    d = get_deploy()
    status = d["status"]
    commit_msg = d.get("commit", {}).get("message", "N/A")
    print(f"[{i*20}s] Status: {status} | Commit: {commit_msg}")
    
    if status == "live":
        print("\n✅ 部署成功！")
        print(f"访问网址: https://case-processor.onrender.com")
        sys.exit(0)
    elif status in ("build_failed", "deploy_failed", "update_failed"):
        print(f"\n❌ 部署失败: {status}")
        if "finishedAt" in d:
            print(f"完成时间: {d['finishedAt']}")
        sys.exit(1)
    
    time.sleep(20)

print("\n⏳ 部署仍在进行中，请稍后查看 Dashboard")
print(f"管理后台: https://dashboard.render.com/web/{SERVICE_ID}")
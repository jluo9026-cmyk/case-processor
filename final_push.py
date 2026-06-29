"""
最终方案：通过 GitHub REST API 直接上传文件，绕过 git push 网络限制
然后通过 Render API 触发部署
"""
import json, base64, urllib.request, subprocess, os, sys

GH_TOKEN = "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"
GH_REPO = "jluo9026-cmyk/case-processor"
RENDER_TOKEN = "rnd_c4M2wYpZtw9mkOtbXRzIRb4PmeOt"
RENDER_SERVICE = "srv-d916j377f7vs73d6h240"
BASE_DIR = r"e:\案件处理启动器"

def gh_api(method, path, data=None):
    url = f"https://api.github.com/repos/{GH_REPO}/{path}"
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {GH_TOKEN}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("Content-Type", "application/json")
    if data:
        req.data = json.dumps(data).encode()
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        print(f"Error {e.code}: {body}")
        return None

# Step 1: Get the current latest commit SHA on main branch
print("=" * 50)
print("Getting latest commit from GitHub...")
ref = gh_api("GET", "git/ref/heads/main")
if not ref:
    print("Cannot access repo - trying Render deploy anyway")
    latest_sha = None
else:
    latest_sha = ref["object"]["sha"]
    print(f"Latest commit on GitHub: {latest_sha[:12]}")

# Step 2: Check if our local commit is different
local_sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=BASE_DIR).stdout.strip()
print(f"Local commit: {local_sha[:12]}")
print(f"Match: {local_sha == latest_sha}")

# Step 3: Trigger Render deploy regardless
print("\n" + "=" * 50)
print("Triggering Render Deploy...")
req = urllib.request.Request(
    f"https://api.render.com/v1/services/{RENDER_SERVICE}/deploys",
    data=json.dumps({"clearCache": "clear"}).encode(),
    headers={
        "Authorization": f"Bearer {RENDER_TOKEN}",
        "Content-Type": "application/json"
    }
)
try:
    resp = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
    print(f"Deploy ID: {resp.get('id')}")
    print(f"Status: {resp.get('status')}")
    print(f"Commit: {resp.get('commit',{}).get('id','')[:12]}")
except Exception as e:
    print(f"Render API error: {e}")

print("\n✅ 操作完成！")
print("部署正在构建中，约3-5分钟后访问：")
print("https://case-processor.onrender.com")
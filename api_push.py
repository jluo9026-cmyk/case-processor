"""
通过 GitHub API + HTTP 代理推送代码
"""
import json, base64, os, sys

GH_TOKEN = "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"
GH_REPO = "jluo9026-cmyk/case-processor"
BASE_DIR = r"e:\案件处理启动器"
PROXY = "http://127.0.0.1:7890"

def gh_api(method, path, data=None):
    import urllib.request
    url = f"https://api.github.com/repos/{GH_REPO}/{path}"
    
    # Set up proxy handler
    proxy_handler = urllib.request.ProxyHandler({
        "http": PROXY,
        "https": PROXY
    })
    opener = urllib.request.build_opener(proxy_handler)
    urllib.request.install_opener(opener)
    
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {GH_TOKEN}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "Python-App")
    if data:
        req.data = json.dumps(data).encode()
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return {"error": f"HTTP {e.code}: {body[:200]}"}
    except Exception as e:
        return {"error": str(e)}

print("1. Getting current state...")
ref = gh_api("GET", "git/ref/heads/main")
if "error" in ref:
    ref = gh_api("GET", "git/ref/heads/master")
if "error" in ref:
    print(f"Failed: {ref['error']}")
    sys.exit(1)

latest_sha = ref["object"]["sha"]
print(f"Latest: {latest_sha[:12]}")

commit = gh_api("GET", f"git/commits/{latest_sha}")
tree_sha = commit["tree"]["sha"]

# Files to update
files = {
    "combined_backend.py": os.path.join(BASE_DIR, "combined_backend.py"),
    "renderer.js": os.path.join(BASE_DIR, "renderer.js"),
    "requirements.txt": os.path.join(BASE_DIR, "requirements.txt"),
    "tools/renderer.js": os.path.join(BASE_DIR, "tools", "renderer.js"),
    "tools/index4.html": os.path.join(BASE_DIR, "tools", "index4.html"),
    "tools/report_generate/report_generate.js": os.path.join(BASE_DIR, "tools", "report_generate", "report_generate.js"),
}

print("\n2. Uploading files...")
items = []
for path, local in files.items():
    with open(local, "rb") as f:
        content = f.read()
    encoded = base64.b64encode(content).decode()
    
    blob = gh_api("POST", "git/blobs", {
        "content": encoded, "encoding": "base64"
    })
    if "error" in blob:
        print(f"  FAIL {path}: {blob['error']}")
        continue
    items.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    print(f"  OK {path}")

print("\n3. Creating tree...")
tree = gh_api("POST", "git/trees", {
    "base_tree": tree_sha, "tree": items
})
if "error" in tree:
    print(f"Tree failed: {tree['error']}")
    sys.exit(1)

print("\n4. Creating commit...")
new_commit = gh_api("POST", "git/commits", {
    "message": "完整修复：所有工具Web适配+后端API(fill-excel/process-docx)",
    "tree": tree["sha"],
    "parents": [latest_sha]
})
if "error" in new_commit:
    print(f"Commit failed: {new_commit['error']}")
    sys.exit(1)

print(f"Commit: {new_commit['sha'][:12]}")

print("\n5. Updating branch...")
result = gh_api("PATCH", "git/refs/heads/main", {
    "sha": new_commit["sha"], "force": True
})
if "error" in result:
    print(f"Branch failed: {result['error']}")
    sys.exit(1)

print("\n✅ PUSH SUCCESS!")

# Trigger Render deploy
print("\n6. Triggering Render deploy...")
RENDER_TOKEN = "rnd_c4M2wYpZtw9mkOtbXRzIRb4PmeOt"
RENDER_SERVICE = "srv-d916j377f7vs73d6h240"

req = urllib.request.Request(
    f"https://api.render.com/v1/services/{RENDER_SERVICE}/deploys",
    data=json.dumps({"clearCache": "clear"}).encode(),
    headers={
        "Authorization": f"Bearer {RENDER_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "Python-App"
    }
)
resp = json.loads(urllib.request.urlopen(req, timeout=60).read().decode())
print(f"Deploy: {resp.get('id')}")
print(f"Status: {resp.get('status')}")
print("\n🌐 https://case-processor.onrender.com (3-5分钟)")
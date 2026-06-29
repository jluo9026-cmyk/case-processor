"""
通过 GitHub REST API 直接推送代码（绕过 git push）
"""
import json, base64, os, subprocess, sys

GH_TOKEN = "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"
GH_REPO = "jluo9026-cmyk/case-processor"
BASE_DIR = r"e:\案件处理启动器"

def gh_api(method, path, data=None):
    import urllib.request
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
    except Exception as e:
        return {"error": str(e)}

# 1. Get current state
print("Getting GitHub state...")
ref = gh_api("GET", "git/ref/heads/main")
if "error" in ref:
    ref = gh_api("GET", "git/ref/heads/master")

latest_commit_sha = ref["object"]["sha"]
print(f"Latest commit: {latest_commit_sha}")

# 2. Get the commit and tree
commit = gh_api("GET", f"git/commits/{latest_commit_sha}")
tree_sha = commit["tree"]["sha"]
print(f"Tree SHA: {tree_sha}")

# 3. Files to update
files_to_update = {
    "combined_backend.py": os.path.join(BASE_DIR, "combined_backend.py"),
    "renderer.js": os.path.join(BASE_DIR, "renderer.js"),
    "requirements.txt": os.path.join(BASE_DIR, "requirements.txt"),
    "tools/renderer.js": os.path.join(BASE_DIR, "tools", "renderer.js"),
    "tools/index4.html": os.path.join(BASE_DIR, "tools", "index4.html"),
    "tools/report_generate/report_generate.js": os.path.join(BASE_DIR, "tools", "report_generate", "report_generate.js"),
}

# 4. Create blobs
print("\nCreating blobs...")
new_tree_items = []
for path, local_path in files_to_update.items():
    if not os.path.exists(local_path):
        print(f"  SKIP (not found): {path}")
        continue
    
    with open(local_path, "rb") as f:
        content = f.read()
    
    encoded = base64.b64encode(content).decode()
    
    blob = gh_api("POST", "git/blobs", {
        "content": encoded,
        "encoding": "base64"
    })
    
    if "error" in blob:
        print(f"  FAIL: {path} - {blob['error']}")
        continue
    
    new_tree_items.append({
        "path": path,
        "mode": "100644",
        "type": "blob",
        "sha": blob["sha"]
    })
    print(f"  OK: {path}")

# 5. Create new tree
print("\nCreating tree...")
new_tree = gh_api("POST", "git/trees", {
    "base_tree": tree_sha,
    "tree": new_tree_items
})

if "error" in new_tree:
    print(f"Tree creation failed: {new_tree['error']}")
    sys.exit(1)

new_tree_sha = new_tree["sha"]
print(f"New tree: {new_tree_sha}")

# 6. Create commit
print("\nCreating commit...")
new_commit = gh_api("POST", "git/commits", {
    "message": "完整修复：所有工具Web适配+后端API(fill-excel/process-docx)",
    "tree": new_tree_sha,
    "parents": [latest_commit_sha]
})

if "error" in new_commit:
    print(f"Commit failed: {new_commit['error']}")
    sys.exit(1)

new_commit_sha = new_commit["sha"]
print(f"New commit: {new_commit_sha}")

# 7. Update branch
print("\nUpdating branch reference...")
result = gh_api("PATCH", "git/refs/heads/main", {
    "sha": new_commit_sha,
    "force": True
})

if "error" in result:
    print(f"Branch update failed: {result['error']}")
    sys.exit(1)

print(f"\nCode pushed to GitHub! Commit: {new_commit_sha[:12]}")

# 8. Trigger Render deploy
print("\nTriggering Render deploy...")
import urllib.request
RENDER_TOKEN = "rnd_c4M2wYpZtw9mkOtbXRzIRb4PmeOt"
RENDER_SERVICE = "srv-d916j377f7vs73d6h240"

req = urllib.request.Request(
    f"https://api.render.com/v1/services/{RENDER_SERVICE}/deploys",
    data=json.dumps({"clearCache": "clear"}).encode(),
    headers={
        "Authorization": f"Bearer {RENDER_TOKEN}",
        "Content-Type": "application/json"
    }
)
resp = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
print(f"Deploy ID: {resp.get('id')}")
print(f"Status: {resp.get('status')}")

print("\nAccess: https://case-processor.onrender.com")
print("Wait 3-5 minutes for build to complete.")
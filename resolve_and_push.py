"""
1. First abort the merge (conflict state)
2. Force push local version via GitHub API 
"""
import subprocess, os, sys, json, base64
import urllib.request

BASE = r"e:\案件处理启动器"
os.chdir(BASE)

# Step 1: Abort merge and reset to our local version
print("Step 1: Resetting to local version...")
subprocess.run(["git", "merge", "--abort"], capture_output=True, text=True)
subprocess.run(["git", "reset", "--hard", "HEAD"], capture_output=True, text=True)

local_sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
print(f"Local commit: {local_sha[:12]}")

# Step 2: Upload each changed file's content via GitHub API + proxy
print("\nStep 2: Uploading files via GitHub API...")

GH_TOKEN = "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"
GH_REPO = "jluo9026-cmyk/case-processor"
PROXY = "http://127.0.0.1:7890"

def gh_api(method, path, data=None):
    url = f"https://api.github.com/repos/{GH_REPO}/{path}"
    proxy_h = urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
    opener = urllib.request.build_opener(proxy_h)
    
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {GH_TOKEN}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "Python-App")
    if data:
        req.data = json.dumps(data).encode()
    try:
        resp = opener.open(req, timeout=60)
        return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}

# Get latest commit
ref = gh_api("GET", "git/ref/heads/main")
if "error" in ref:
    print(f"GET ref failed: {ref['error']}")
    sys.exit(1)

latest = ref["object"]["sha"]
print(f"Remote commit: {latest[:12]}")

commit = gh_api("GET", f"git/commits/{latest}")
tree_sha = commit["tree"]["sha"]

# Files
files = {
    "combined_backend.py": os.path.join(BASE, "combined_backend.py"),
    "renderer.js": os.path.join(BASE, "renderer.js"),
    "requirements.txt": os.path.join(BASE, "requirements.txt"),
    "tools/renderer.js": os.path.join(BASE, "tools", "renderer.js"),
    "tools/index4.html": os.path.join(BASE, "tools", "index4.html"),
    "tools/report_generate/report_generate.js": os.path.join(BASE, "tools", "report_generate", "report_generate.js"),
}

items = []
for path, local in files.items():
    with open(local, "rb") as f:
        content = f.read()
    encoded = base64.b64encode(content).decode()
    
    blob = gh_api("POST", "git/blobs", {"content": encoded, "encoding": "base64"})
    if "error" in blob:
        print(f"  FAIL {path}: {blob['error']}")
        continue
    items.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    print(f"  OK {path}")

if not items:
    print("No files uploaded!")
    sys.exit(1)

# Create tree
tree = gh_api("POST", "git/trees", {"base_tree": tree_sha, "tree": items})
if "error" in tree:
    print(f"Tree: {tree['error']}")
    sys.exit(1)

# Create commit
new_c = gh_api("POST", "git/commits", {
    "message": "完整修复：所有工具Web适配(fill-excel/process-docx)+openpyxl",
    "tree": tree["sha"], "parents": [latest]
})
if "error" in new_c:
    print(f"Commit: {new_c['error']}")
    sys.exit(1)

print(f"Commit: {new_c['sha'][:12]}")

# Update branch
result = gh_api("PATCH", "git/refs/heads/main", {"sha": new_c["sha"], "force": True})
if "error" in result:
    print(f"Branch: {result['error']}")
    sys.exit(1)

print("\n✅ PUSH SUCCESS!")

# Trigger Render
print("\nStep 3: Triggering Render deploy...")
RTOKEN = "rnd_c4M2wYpZtw9mkOtbXRzIRb4PmeOt"
RSVC = "srv-d916j377f7vs73d6h240"

proxy_h = urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
opener = urllib.request.build_opener(proxy_h)
req = urllib.request.Request(
    f"https://api.render.com/v1/services/{RSVC}/deploys",
    data=json.dumps({"clearCache": "clear"}).encode(),
    headers={"Authorization": f"Bearer {RTOKEN}", "Content-Type": "application/json", "User-Agent": "Python-App"}
)
resp = json.loads(opener.open(req, timeout=60).read().decode())
print(f"Deploy: {resp.get('id')} | Status: {resp.get('status')}")
print("\n🌐 https://case-processor.onrender.com (等待3-5分钟构建)")
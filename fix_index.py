"""
直接通过 GitHub API 上传正确的 index.html 文件内容
"""
import json, urllib.request, os

GH_TOKEN = "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"
GH_REPO = "jluo9026-cmyk/case-processor"
PROXY = "http://127.0.0.1:7890"

# The correct index.html content (5-tool launcher)
INDEX_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>案件处理启动器</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Microsoft YaHei',sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);min-height:100vh;padding:30px}
.container{max-width:1000px;margin:0 auto}
.header{background:#fff;border-radius:16px;padding:28px;margin-bottom:24px;text-align:center}
.header h1{color:#1a1a2e;font-size:26px}
.header p{color:#666;font-size:14px;margin-top:6px}
.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:16px;margin-top:20px}
.card{background:#fff;border-radius:16px;padding:28px;text-align:center;cursor:pointer;box-shadow:0 4px 20px rgba(0,0,0,0.1)}
.card:hover{transform:translateY(-4px);border-color:#667eea}
.icon{font-size:42px;margin-bottom:12px}
.name{font-size:18px;font-weight:600;color:#1a1a2e;margin-bottom:6px}
.desc{font-size:13px;color:#888}
.bar{background:#fff;border-radius:12px;padding:14px;margin-top:20px;text-align:center}
.ft{text-align:center;color:rgba(255,255,255,0.7);margin-top:24px}
</style>
</head>
<body>
<div class="container">
<div class="header"><h1>📋 案件处理启动器</h1><p>集成多个案件处理工具，统一管理，高效协作</p></div>
<div class="grid">
<div class="card" onclick="window.open('/tools/report_generate/index.html','_blank')"><div class="icon">📝</div><div class="name">报告生成</div><div class="desc">上传图片+笔录→自动生成勘查报告</div></div>
<div class="card" onclick="window.open('/report-standard','_blank')"><div class="icon">📄</div><div class="name">报告标准化</div><div class="desc">DOCX格式转换+预设模板</div></div>
<div class="card" onclick="window.open('/tools/index4.html','_blank')"><div class="icon">📑</div><div class="name">目录工具</div><div class="desc">生成附件清单Word表格</div></div>
<div class="card" onclick="window.open('/tools/index3.html','_blank')"><div class="icon">✅</div><div class="name">结案审批表</div><div class="desc">填写结案审批表</div></div>
<div class="card" onclick="window.open('/tools/attachment_web/index.html','_blank')"><div class="icon">🖼️</div><div class="name">附件处理器</div><div class="desc">上传图片→生成附件Word报告</div></div>
</div>
<div class="bar">✅ 系统就绪，共 5 个工具</div>
<div class="ft">深圳市德泰保险公估有限公司</div>
</div>
</body>
</html>
"""

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
        return {"error": f"HTTP {e.code}: {e.read().decode()[:200]}"}

# 1. Get current file SHA
print("Getting current index.html info...")
file_info = gh_api("GET", "contents/index.html")
if "error" in file_info:
    print(f"Error: {file_info['error']}")
    sha = None
else:
    sha = file_info.get("sha")
    print(f"Current SHA: {sha}")

# 2. Upload new content
print("Uploading correct index.html...")
import base64
content_encoded = base64.b64encode(INDEX_HTML.encode()).decode()

result = gh_api("PUT", "contents/index.html", {
    "message": "修复index.html为5工具启动器",
    "content": content_encoded,
    "sha": sha
})

if "error" in result:
    print(f"Upload failed: {result['error']}")
    print("\nPlease upload manually:")
    print("1. Open https://github.com/jluo9026-cmyk/case-processor/blob/main/index.html")
    print("2. Click Edit, paste the content from e:\\案件处理启动器\\fix_index.py (the INDEX_HTML variable)")
else:
    print(f"✅ Upload success! Commit: {result['commit']['sha'][:12]}")
    print("\nNow triggering Render deploy...")
    
    # 3. Trigger deploy
    RENDER_TOKEN = "rnd_c4M2wYpZtw9mkOtbXRzIRb4PmeOt"
    RENDER_SERVICE = "srv-d916j377f7vs73d6h240"
    deploy_req = urllib.request.Request(
        f"https://api.render.com/v1/services/{RENDER_SERVICE}/deploys",
        data=json.dumps({"clearCache": "clear"}).encode(),
        headers={"Authorization": f"Bearer {RENDER_TOKEN}", "Content-Type": "application/json"}
    )
    deploy_resp = json.loads(urllib.request.urlopen(deploy_req, timeout=30).read().decode())
    print(f"Deploy: {deploy_resp.get('id')} | Status: {deploy_resp.get('status')}")
    print("\n✅ 3分钟后打开 https://case-processor.onrender.com 查看5个工具")
import urllib.request
import json

TOKEN = "rnd_c4M2wYpZtw9mkOtbXRzIRb4PmeOt"
SERVICE = "srv-d916j377f7vs73d6h240"

# 设置环境变量
env_vars = {
    "BAIDU_API_KEY": {"value": "R0rX3CVmWrRqklcLkW7UXCQ8"},
    "BAIDU_SECRET_KEY": {"value": "0XnqhRxhNj4HhpfAgZtQ3qWm3gyIv6M4"},
    "QWEN_VL_API_KEY": {"value": "sk-6852f63399514561b164eeac3e4c588f"},
    "QWEN_VL_BASE_URL": {"value": "https://dashscope.aliyuncs.com/compatible-mode/v1"}
}

data = json.dumps({"envVars": env_vars}).encode("utf-8")
req = urllib.request.Request(
    f"https://api.render.com/v1/services/{SERVICE}/env-vars",
    data=data,
    method="PATCH",
    headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
)

print("正在配置Render环境变量...")
try:
    resp = urllib.request.urlopen(req, timeout=30)
    result = json.loads(resp.read().decode("utf-8"))
    print("环境变量设置成功!")
except urllib.error.HTTPError as e:
    error_body = e.read().decode("utf-8")
    print(f"HTTP错误 {e.code}: {error_body}")
except Exception as e:
    print(f"请求失败: {e}")

# 触发部署
print("\n正在触发部署...")
deploy_data = json.dumps({"clearCache": "clear"}).encode("utf-8")
deploy_req = urllib.request.Request(
    f"https://api.render.com/v1/services/{SERVICE}/deploys",
    data=deploy_data,
    headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
)

try:
    deploy_resp = urllib.request.urlopen(deploy_req, timeout=30)
    deploy_result = json.loads(deploy_resp.read().decode("utf-8"))
    print(f"部署已触发!")
    print(f"部署ID: {deploy_result.get('id')}")
    print(f"状态: {deploy_result.get('status')}")
    print("\n等待2-3分钟后访问:")
    print("https://case-processor.onrender.com/tools/report_generate/index.html")
except urllib.error.HTTPError as e:
    error_body = e.read().decode("utf-8")
    print(f"部署触发失败 {e.code}: {error_body}")
</write_to_file>
import urllib.request
import json

TOKEN = "rnd_c4M2wYpZtw9mkOtbXRzIRb4PmeOt"
SERVICE = "srv-d916j377f7vs73d6h240"

# 获取当前环境变量
try:
    req = urllib.request.Request(
        f"https://api.render.com/v1/services/{SERVICE}/env-vars",
        headers={"Authorization": f"Bearer {TOKEN}"}
    )
    resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read().decode("utf-8"))
    print("当前环境变量:")
    print(json.dumps(data, ensure_ascii=False, indent=2))
except urllib.error.HTTPError as e:
    error_body = e.read().decode("utf-8")
    print(f"获取环境变量失败 HTTP {e.code}: {error_body}")
except Exception as e:
    print(f"请求失败: {e}")

# 设置环境变量
print("\n====================")
print("设置环境变量...")
env_vars = {
    "BAIDU_API_KEY": {"value": "R0rX3CVmWrRqklcLkW7UXCQ8"},
    "BAIDU_SECRET_KEY": {"value": "0XnqhRxhNj4HhpfAgZtQ3qWm3gyIv6M4"},
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

try:
    resp = urllib.request.urlopen(req, timeout=30)
    result = json.loads(resp.read().decode("utf-8"))
    print("环境变量设置成功!")
    print(json.dumps(result, ensure_ascii=False, indent=2))
except urllib.error.HTTPError as e:
    error_body = e.read().decode("utf-8")
    print(f"设置失败 HTTP {e.code}: {error_body[:500]}")
except Exception as e:
    print(f"请求失败: {e}")
</write_to_file>
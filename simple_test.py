import http.client
import json

# 测试健康检查
print("测试健康检查...")
conn = http.client.HTTPConnection("127.0.0.1", 8766)
conn.request("GET", "/api/health")
response = conn.getresponse()
print(f"状态码: {response.status}")
print(f"响应: {response.read().decode('utf-8')}")
conn.close()

print("\n测试模板列表...")
conn = http.client.HTTPConnection("127.0.0.1", 8766)
conn.request("GET", "/api/templates")
response = conn.getresponse()
print(f"状态码: {response.status}")
print(f"响应: {response.read().decode('utf-8')}")
conn.close()

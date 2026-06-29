# 🚀 Render.com 部署指南

> 将"案件处理启动器"部署到 Render.com 云平台，5 分钟上线

---

## 📋 前置条件

| 条件 | 说明 |
|------|------|
| ✅ GitHub 账号 | 用于存放代码仓库 |
| ✅ Render.com 账号 | 用 GitHub 登录 https://render.com |
| ✅ 项目代码 | 本项目的所有文件 |

---

## ⏱ 5 分钟部署步骤

### 第 1 步：上传代码到 GitHub

```bash
# 在项目目录中执行：
git init
git add .
git commit -m "first commit"
git remote add origin https://github.com/你的用户名/case-processor.git
git push -u origin main
```

### 第 2 步：创建 Render Web Service

1. 登录 [Render Dashboard](https://dashboard.render.com)
2. 点击 **New +** → **Web Service**
3. 选择你刚上传的 GitHub 仓库
4. 填写配置：

| 配置项 | 值 |
|--------|-----|
| **Name** | `case-processor`（任意） |
| **Environment** | `Docker` |
| **Plan** | **Free** |
| **Health Check Path** | `/api/health` |

5. 点击 **Advanced** 添加环境变量（可选）：

| 环境变量 | 说明 | 必填？ |
|---------|------|-------|
| `DEEPSEEK_API_KEY` | AI 报告生成 API Key | 可选 |
| `BAIDU_API_KEY` | 百度 OCR 文字识别 Key | 可选 |
| `BAIDU_SECRET_KEY` | 百度 OCR Secret Key | 可选 |
| `QWEN_VL_API_KEY` | 千问视觉分析 Key | 可选 |

> ⚠️ **不配置 API Key 不影响核心功能**：报告文档的标准化转换（格式整理、章节识别、预设模板）完全离线运行，不需要任何 API Key。

### 第 3 步：部署

1. 点击 **Create Web Service**
2. 等待 3-5 分钟，Build 和 Deploy 完成
3. 看到 `✅ Your service is live 🎉` 即成功

### 第 4 步：访问

部署完成后，访问 `https://case-processor.onrender.com`（或 Render 分配的域名）

---

## ✅ 验证是否部署成功

| 验证项 | 方法 | 预期结果 |
|--------|------|---------|
| 健康检查 | 访问 `/api/health` | `{"status":"ok","modules":{...}}` |
| 预设模板 | 访问 `/api/template/presets` | 返回 3 个模板 |
| 首页 | 访问 `/` | 显示上传页面 |
| 文档转换 | 上传 .docx 文件测试 | 生成标准格式报告 |

---

## 📁 文件清单

部署所需的关键文件：

```
项目根目录/
├── combined_backend.py      # 主入口（已适配云部署）
├── Dockerfile                # Docker 构建配置
├── render.yaml               # Render 部署配置（可选）
├── requirements.txt          # Python 依赖
├── .env                      # 环境变量模板
├── modules/                  # 后端模块
│   ├── app_core.py
│   ├── config.py
│   ├── routes.py
│   ├── helpers.py
│   ├── ocr_service.py
│   ├── docx_merge.py
│   └── template_data.py
├── templates/index.html      # 前端页面
├── static/                   # 静态资源
├── template_preset_1.docx    # 预设模板文件
├── template_preset_2.docx
├── template_preset_3.docx
└── output/                   # 输出目录（运行时会创建）
```

---

## ⚠️ 已知限制（免费版）

| 限制 | 说明 | 如何应对 |
|------|------|---------|
| **512MB 内存** | 单个服务 512MB RAM | 大文件（>50页DOCX）可能内存不足 |
| **15 分钟无请求休眠** | 空闲 15 分钟自动暂停 | 首次访问等待 10-30 秒自动唤醒 |
| **临时磁盘** | 每次部署文件会清空 | 生成报告后及时下载 |
| **每月 750 小时** | 1 个服务 24x7 = 720h | 完全够用 |

> 💡 **建议**：用 [UptimeRobot](https://uptimerobot.com) 每 10 分钟 ping 一次 `/api/health`，可避免服务休眠。

---

## 🔧 本地开发 vs 云部署对比

| 对比项 | 本地运行 | Render 云部署 |
|--------|---------|-------------|
| 启动命令 | `py combined_backend.py` | 自动（Docker） |
| 监听地址 | `127.0.0.1` | `0.0.0.0` |
| 端口 | 10000 | 由 `$PORT` 环境变量指定 |
| 文件存储 | `output/` `uploads/` | `/tmp/case_processor/` |
| 前端访问 | `http://localhost:10000` | `https://xxx.onrender.com` |

---

## 🎯 需要 API Key 的功能

如果 **不配置任何 API Key**，以下功能可用：

| 功能 | 是否需要 API |
|------|-------------|
| ✅ DOCX 文档分析 | **不需要** |
| ✅ 报告标准化转换 | **不需要** |
| ✅ 三个预设模板 | **不需要** |
| ✅ 文件上传/下载 | **不需要** |
| ❌ AI 智能报告生成 | 需要 `DEEPSEEK_API_KEY` |
| ❌ OCR 图片文字识别 | 需要 `BAIDU_API_KEY` + `BAIDU_SECRET_KEY` |

---

## ❓ 常见问题

**Q: 部署后页面加载不出来？**
A: 等待 30 秒让服务唤醒，刷新页面即可。

**Q: 上传文件失败？**
A: 免费版限制文件大小，建议 <20MB。

**Q: 如何查看日志？**
A: Render Dashboard → Logs 标签页。

---

> 最后更新：2025 年
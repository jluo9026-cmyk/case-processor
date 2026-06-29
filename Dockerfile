# ========================================
# 案件处理启动器 - Render.com 部署 Dockerfile
# ========================================

FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（python-docx 和 lxml 需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 创建必要的目录（Render 使用临时磁盘）
RUN mkdir -p /tmp/case_processor/uploads /tmp/case_processor/output

# 清理本地开发不需要的文件
RUN rm -rf node_modules .git __pycache__ *.pyc 2>/dev/null || true

# Render 会通过 PORT 环境变量指定端口
EXPOSE 10000

# 启动命令
CMD uvicorn combined_backend:app --host 0.0.0.0 --port $PORT --log-level info
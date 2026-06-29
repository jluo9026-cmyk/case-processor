"""
案件处理启动器 - 合并后端服务 (Render.com 云部署版本)
FastAPI异步框架
支持：报告标准化转换 + 报告生成
"""

import os
import sys
import uuid
import socket
import asyncio
import json
import io
import re
import base64
import urllib.request
import urllib.parse
import httpx
from datetime import datetime
from pathlib import Path
from copy import deepcopy
import zipfile
from lxml import etree
import tempfile
import shutil
import traceback

# 加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 添加项目根目录到 sys.path
BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

# ============ 注册模块路由 ============
from modules.config import HAS_MODULES
from modules.app_core import app

# 触发 routes 模块加载
import modules.routes

# 从 routes 模块获取共享的生成报告字典
from modules.routes import _generated_reports

from modules.template_data import PRESET_TEMPLATES, _get_preset_template

from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi import HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

# ============ Render 兼容的路径配置 ============
RENDER = os.environ.get('RENDER', '') == 'true'
IS_RENDER = RENDER or 'RENDER_EXTERNAL_URL' in os.environ

# 临时文件目录
TEMP_DIR = Path(tempfile.gettempdir()) / 'case_processor'
TEMP_DIR.mkdir(exist_ok=True)
UPLOAD_DIR = TEMP_DIR / 'uploads'
OUTPUT_DIR = TEMP_DIR / 'output'
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

print(f'[INFO] 上传目录: {UPLOAD_DIR}')
print(f'[INFO] 输出目录: {OUTPUT_DIR}')
print(f'[INFO] 运行环境: {"Render.com" if IS_RENDER else "本地开发"}')

# ============ 静态文件服务（通过路由手动处理，避免StaticFiles mount阻塞路由）============
MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css',
    '.js': 'application/javascript',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
}


@app.get('/static/{file_path:path}')
async def serve_static(file_path: str):
    """提供 /static/ 目录下的文件"""
    static_dir = BASE_DIR / 'static'
    full_path = (static_dir / file_path).resolve()
    # 安全检查
    if not str(full_path).startswith(str(static_dir.resolve())):
        return HTMLResponse('Forbidden', status_code=403)
    if not full_path.exists() or not full_path.is_file():
        return HTMLResponse('Not Found', status_code=404)
    ext = full_path.suffix.lower()
    media_type = MIME_TYPES.get(ext, 'application/octet-stream')
    return FileResponse(str(full_path), media_type=media_type)


@app.get('/')
async def serve_index():
    """提供主页面"""
    for p in [BASE_DIR / 'templates' / 'index.html', BASE_DIR / 'index.html']:
        if p.exists():
            content = p.read_text(encoding='utf-8')
            return HTMLResponse(content)
    return HTMLResponse('<h1>案件处理启动器</h1><p>服务器运行正常</p>')


# ============ API 路由 ============

@app.get('/api/health')
async def health_check():
    return {
        'status': 'ok',
        'service': 'combined-backend',
        'version': '2.0.0',
        'environment': 'render' if IS_RENDER else 'local',
        'modules': {
            'report_standard': True,
            'report_generate': True
        }
    }


@app.post('/api/test')
async def test_endpoint():
    return {'success': True, 'message': '后端服务正常运行'}


@app.get('/api/download/{report_id}')
async def download_report(report_id: str):
    """下载生成的报告文件"""
    # 先检查 _generated_reports
    if report_id not in _generated_reports:
        # 尝试从 OUTPUT_DIR 查找文件
        report_path = OUTPUT_DIR / f'report_{report_id}.docx'
        if report_path.exists():
            return FileResponse(
                str(report_path),
                media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                filename=report_path.name
            )
        for f in OUTPUT_DIR.glob(f'{report_id}*'):
            if f.is_file():
                return FileResponse(
                    str(f),
                    media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    filename=f.name
                )
        for f in OUTPUT_DIR.glob(f'*{report_id}*'):
            if f.is_file():
                return FileResponse(
                    str(f),
                    media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    filename=f.name
                )
        raise HTTPException(404, '报告文件不存在')

    report = _generated_reports[report_id]
    report_path = Path(report['path'])
    if not report_path.exists():
        raise HTTPException(404, '报告文件已被删除')

    return FileResponse(
        str(report_path),
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        filename=report.get('filename', f'report_{report_id}.docx')
    )


# ============ 服务器启动 ============
if __name__ == '__main__':
    import uvicorn
    
    # 支持命令行参数指定端口: py combined_backend.py 10001
    # Render 通过环境变量 $PORT 指定端口
    default_port = 10000
    if len(sys.argv) > 1:
        try:
            default_port = int(sys.argv[1])
        except ValueError:
            pass
    
    port = int(os.environ.get('PORT', default_port))
    # 本地开发用 127.0.0.1，服务器用 0.0.0.0
    host = os.environ.get('HOST', '0.0.0.0')
    
    print(f'=== 后端服务启动在 {host}:{port} ===')
    print(f'=== 健康检查: http://localhost:{port}/api/health ===')
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level='info',
        access_log=False,
        timeout_keep_alive=600
    )

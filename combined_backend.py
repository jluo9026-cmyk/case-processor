"""
案件处理启动器 - 合并后端服务 (Render.com 云部署版本)
完整工具套件：报告标准化、报告生成、目录工具、结案审批表
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

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

# ============ 注册模块路由 ============
from modules.config import HAS_MODULES
from modules.app_core import app
import modules.routes
from modules.routes import _generated_reports
from modules.template_data import PRESET_TEMPLATES, _get_preset_template

from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi import HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

# ============ 路径配置 ============
RENDER = os.environ.get('RENDER', '') == 'true'
IS_RENDER = RENDER or 'RENDER_EXTERNAL_URL' in os.environ

TEMP_DIR = Path(tempfile.gettempdir()) / 'case_processor'
TEMP_DIR.mkdir(exist_ok=True)
UPLOAD_DIR = TEMP_DIR / 'uploads'
OUTPUT_DIR = TEMP_DIR / 'output'
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

print(f'[INFO] 上传目录: {UPLOAD_DIR}')
print(f'[INFO] 输出目录: {OUTPUT_DIR}')

# ============ 案件数据存储（取代Electron的本地文件存储）============
_case_data_store = {}

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

# ============ 工具信息 ============
WEB_TOOLS = [
    {'id': 'reportGenerate', 'name': '报告生成', 'icon': '📝', 'desc': '上传图片+笔录→自动生成勘查报告', 'url': '/tools/report_generate/index.html'},
    {'id': 'docxConverter', 'name': '报告标准化', 'icon': '📄', 'desc': 'DOCX格式转换+预设模板', 'url': '/report-standard'},
    {'id': 'catalogTool', 'name': '目录工具', 'icon': '📑', 'desc': '生成附件清单Word表格', 'url': '/tools/index4.html'},
    {'id': 'approvalForm', 'name': '结案审批表', 'icon': '✅', 'desc': '填写结案审批表', 'url': '/tools/index3.html'},
]


# ============ 文件服务 ============
def _serve_file(full_path: Path):
    if not full_path.exists() or not full_path.is_file():
        return None
    ext = full_path.suffix.lower()
    media_type = MIME_TYPES.get(ext, 'application/octet-stream')
    return FileResponse(str(full_path), media_type=media_type)


# ============ 路由：静态文件 ============
@app.get('/static/{file_path:path}')
async def serve_static(file_path: str):
    static_dir = BASE_DIR / 'static'
    full_path = (static_dir / file_path).resolve()
    if not str(full_path).startswith(str(static_dir.resolve())):
        return HTMLResponse('Forbidden', status_code=403)
    result = _serve_file(full_path)
    if result: return result
    return HTMLResponse('Not Found', status_code=404)


@app.get('/tools/{file_path:path}')
async def serve_tools(file_path: str):
    """提供 tools/ 下的所有工具文件（HTML/JS/CSS/图片等）"""
    tools_dir = BASE_DIR / 'tools'
    full_path = (tools_dir / file_path).resolve()
    if not str(full_path).startswith(str(tools_dir.resolve())):
        return HTMLResponse('Forbidden', status_code=403)
    
    # 如果是 report_generate 目录，从子目录提供
    result = _serve_file(full_path)
    if result: return result
    
    # 如果文件不存在且没有扩展名，尝试加 .html
    if '.' not in file_path:
        html_path = full_path.with_suffix('.html')
        if html_path.exists():
            result = _serve_file(html_path)
            if result: return result
    
    return HTMLResponse('Not Found', status_code=404)


# ============ 路由：首页 ============
@app.get('/')
async def serve_index():
    """提供主启动器页面"""
    index_path = BASE_DIR / 'index.html'
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding='utf-8'))
    # fallback to templates/index.html
    tpl_path = BASE_DIR / 'templates' / 'index.html'
    if tpl_path.exists():
        return HTMLResponse(tpl_path.read_text(encoding='utf-8'))
    return HTMLResponse('<h1>案件处理启动器</h1><p>服务器运行正常</p>')


@app.get('/report-standard')
async def serve_report_standard():
    """提供报告标准化页面"""
    tpl_path = BASE_DIR / 'templates' / 'index.html'
    if tpl_path.exists():
        return HTMLResponse(tpl_path.read_text(encoding='utf-8'))
    return HTMLResponse('报告标准化页面', status_code=200)


# ============ 路由：API ============

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


@app.get('/api/tools')
async def get_tool_list():
    """返回可用工具列表"""
    tools = []
    for t in WEB_TOOLS:
        tools.append({
            'id': t['id'],
            'name': t['name'],
            'icon': t['icon'],
            'desc': t['desc'],
            'url': t['url'],
            'exists': True
        })
    return {'success': True, 'tools': tools}


# ============ 案件数据 API（取代 Electron IPC）============
@app.post('/api/case-data/save')
async def save_case_data(request: Request):
    data = await request.json()
    _case_data_store['current'] = data
    return {'success': True}


@app.get('/api/case-data/load')
async def load_case_data():
    data = _case_data_store.get('current', {})
    return {'success': True, 'data': data}


@app.post('/api/case-data/clear')
async def clear_case_data():
    _case_data_store.clear()
    return {'success': True}


# ============ 运行工具 API ============
@app.post('/api/tools/run')
async def run_tool(request: Request):
    """执行工具 - Web版直接返回工具URL供前端跳转"""
    data = await request.json()
    tool_name = data.get('toolName', '')
    tool = next((t for t in WEB_TOOLS if t['id'] == tool_name), None)
    if not tool:
        return {'success': False, 'error': f'工具不存在: {tool_name}'}
    return {'success': True, 'url': tool['url']}


# ============ 下载 ============
@app.get('/api/download/{report_id}')
async def download_report(report_id: str):
    if report_id not in _generated_reports:
        report_path = OUTPUT_DIR / f'report_{report_id}.docx'
        if report_path.exists():
            return FileResponse(str(report_path), media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document', filename=report_path.name)
        for f in OUTPUT_DIR.glob(f'{report_id}*'):
            if f.is_file():
                return FileResponse(str(f), media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document', filename=f.name)
        for f in OUTPUT_DIR.glob(f'*{report_id}*'):
            if f.is_file():
                return FileResponse(str(f), media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document', filename=f.name)
        raise HTTPException(404, '报告文件不存在')
    report = _generated_reports[report_id]
    report_path = Path(report['path'])
    if not report_path.exists():
        raise HTTPException(404, '报告文件已被删除')
    return FileResponse(str(report_path), media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document', filename=report.get('filename', f'report_{report_id}.docx'))


# ============ 服务器启动 ============
if __name__ == '__main__':
    import uvicorn
    default_port = 10000
    if len(sys.argv) > 1:
        try: default_port = int(sys.argv[1])
        except ValueError: pass
    port = int(os.environ.get('PORT', default_port))
    host = os.environ.get('HOST', '0.0.0.0')
    print(f'=== 后端服务启动在 {host}:{port} ===')
    uvicorn.run(app, host=host, port=port, log_level='info', access_log=False, timeout_keep_alive=600)
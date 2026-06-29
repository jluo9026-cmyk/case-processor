"""
案件处理启动器 - 合并后端服务
Flask兼容层 + FastAPI异步框架
Electron桌面应用后端
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
from datetime import datetime
from pathlib import Path

# 修复 stdout/stderr 编码 - 安全版本，避免 Electron spawn 模式下崩溃
try:
    if sys.stdout is not None and hasattr(sys.stdout, 'detach'):
        sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8', errors='replace', line_buffering=True)
    if sys.stderr is not None and hasattr(sys.stderr, 'detach'):
        sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8', errors='replace', line_buffering=True)
except Exception:
    pass
try:
    sys.stdout.flush()
except Exception:
    pass
try:
    sys.stderr.flush()
except Exception:
    pass

# 加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response

from docx import Document
from docx.shared import Pt, Inches, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH

# Flask兼容层
try:
    from werkzeug.utils import secure_filename
    HAS_FLASK = True
except ImportError:
    # ✅ 修复：使用更安全的文件名生成方式
    def secure_filename(filename: str) -> str:
        """生成安全的文件名"""
        basename = os.path.basename(filename)
        ext = basename.rsplit('.', 1)[1].lower() if '.' in basename else ''
        return f"{uuid.uuid4().hex}_{basename}"
    HAS_FLASK = False

# ============ DeepSeek API 配置 ============
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_TIMEOUT = 120
DEEPSEEK_CONNECT_TIMEOUT = 30

SYSTEM_ROLE = """# 角色定位
你是一位专业的保险公估报告撰写专家，精通保险公估报告的撰写规范和格式要求。

# 任务说明
根据提供的OCR识别文本、案件信息和原始文本，撰写一份完整的保险公估报告。

# 报告结构要求
1. 报告标题
2. 案件基本信息（保单号、被保险人、出险时间等）
3. 事故调查情况
4. 保险责任分析
5. 调查结论
6. 免责声明
7. 签名栏

# 格式要求
1. 使用正式、专业的语言
2. 段落清晰，逻辑严谨
3. 事实描述准确客观
4. 法律依据引用准确
5. 结论明确

# 注意事项
1. 不要编造事实，只基于提供的信息撰写
2. 如果信息不足，明确标注"信息缺失"
3. 保持客观中立的态度
4. 使用规范的保险公估行业术语"""

MODEL_TEMPERATURE = 0.7
MODEL_TOP_P = 0.95
MODEL_MAX_TOKENS = 4000

# ============ OCR 配置 ============
BAIDU_API_KEY = os.getenv("BAIDU_API_KEY")
BAIDU_SECRET_KEY = os.getenv("BAIDU_SECRET_KEY")
QWEN_VL_API_KEY = os.getenv("QWEN_VL_API_KEY", "")
QWEN_VL_BASE_URL = os.getenv("QWEN_VL_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

# ============ 模块检测 ============
HAS_MODULES = False  # 设置为False，使用内置简化逻辑

# ============ 路径配置 ============
# config.py 位于 modules/ 下，所以 __file__ 的 parent 是项目的根目录
BASE_DIR = Path(__file__).parent.parent.resolve()
MODULES_DIR = BASE_DIR / 'modules'

# 确保 project_root/modules 目录存在（不是 recursive）
if MODULES_DIR.name == 'modules':
    MODULES_DIR.mkdir(exist_ok=True)

# 如果 modules 目录不存在，创建它
if not MODULES_DIR.exists():
    MODULES_DIR.mkdir(parents=True, exist_ok=True)
    # 创建 __init__.py 使其成为 Python 包
    init_file = MODULES_DIR / '__init__.py'
    if not init_file.exists():
        init_file.write_text('# modules package\n', encoding='utf-8')
    print(f'[INFO] 创建 modules 目录: {MODULES_DIR}')

# ============ 路径配置 ============
PORT_FILE = BASE_DIR / '.backend_port'
UPLOAD_DIR = BASE_DIR / 'uploads'
OUTPUT_DIR = BASE_DIR / 'output'

# 创建必要的目录
for dir_path in [UPLOAD_DIR, OUTPUT_DIR, MODULES_DIR]:
    dir_path.mkdir(exist_ok=True)

# ============ 任务管理 ============
JOBS = {}
JOBS_LOCK = asyncio.Lock()


async def create_job(job_id, metadata=None):
    async with JOBS_LOCK:
        JOBS[job_id] = {
            'id': job_id,
            'status': 'pending',
            'progress': 0,
            'message': '任务已创建',
            'created_at': datetime.now().isoformat(),
            'started_at': None,
            'finished_at': None,
            'result': None,
            'error': None,
            'metadata': metadata or {}
        }
        return JOBS[job_id]


async def update_job(job_id, **updates):
    async with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return None
        job.update(updates)
        return job


async def get_job(job_id):
    async with JOBS_LOCK:
        return JOBS.get(job_id)


def parse_word_template(content: bytes) -> dict:
    """解析Word模板内容，提取章节和段落信息"""
    import zipfile as _zipfile
    import io as _io
    from lxml import etree as _etree
    
    nsp = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    
    sections = []
    paragraphs = []
    
    try:
        z = _zipfile.ZipFile(_io.BytesIO(content))
        xml_content = z.read('word/document.xml')
        root = _etree.fromstring(xml_content)
        
        for para_elem in root.iter(f'{{{nsp["w"]}}}p'):
            texts = para_elem.findall('.//w:t', nsp)
            para_text = ''.join(t.text or '' for t in texts).strip()
            if not para_text:
                continue
            
            paragraphs.append(para_text)
            
            # 检测章节标题
            is_heading = False
            pPr = para_elem.find('w:pPr', nsp)
            if pPr is not None:
                pStyle = pPr.find('w:pStyle', nsp)
                if pStyle is not None:
                    style_val = pStyle.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', '')
                    if style_val and style_val.startswith('Heading'):
                        is_heading = True
            
            if not is_heading:
                if (para_text.startswith('第') and '章' in para_text) or \
                   re.match(r'^[一二三四五六七八九十]+[、．\.]', para_text):
                    is_heading = True
            
            if is_heading:
                sections.append({
                    'title': para_text,
                    'level': 1,
                    'content': []
                })
            elif sections:
                sections[-1]['content'].append(para_text)
    
    except Exception as e:
        print(f'[parse_word_template] 解析模板失败: {e}')
        sections = [{'title': '全文', 'level': 1, 'content': paragraphs}]
    
    return {
        'sections': sections,
        'paragraphs': paragraphs
    }


def allowed_file(filename):
    """检查文件是否允许上传"""
    ALLOWED_EXTENSIONS = {'docx'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

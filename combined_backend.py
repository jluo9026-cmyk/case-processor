"""
案件处理启动器 - 完全自包含版本（不依赖modules/routes.py）
"""
import os, sys, json, uuid
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware

from modules.app_core import app
from modules.config import BASE_DIR as C_BASE_DIR, UPLOAD_DIR, OUTPUT_DIR
# ===== 注册所有 API 路由 =====
from modules import routes

MIME = {
    '.html':'text/html; charset=utf-8','.css':'text/css','.js':'application/javascript',
    '.json':'application/json','.png':'image/png','.jpg':'image/jpeg',
    '.jpeg':'image/jpeg','.gif':'image/gif','.svg':'image/svg+xml','.ico':'image/x-icon',
    '.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}

HOME = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>案件处理启动器</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Microsoft YaHei",sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);min-height:100vh;padding:30px}
.c{max-width:1000px;margin:0 auto}.h{background:#fff;border-radius:16px;padding:28px;margin-bottom:24px;text-align:center;box-shadow:0 4px 20px rgba(0,0,0,.1)}
.h h1{color:#1a1a2e;font-size:26px}.h p{color:#666;font-size:14px;margin-top:6px}
.g{display:grid;grid-template-columns:repeat(2,1fr);gap:16px;margin-top:20px}
.i{background:#fff;border-radius:16px;padding:28px;text-align:center;cursor:pointer;box-shadow:0 4px 20px rgba(0,0,0,.1);transition:all .3s;border:2px solid transparent}
.i:hover{transform:translateY(-4px);border-color:#667eea}
.ic{font-size:42px;margin-bottom:12px}.nm{font-size:18px;font-weight:600;color:#1a1a2e;margin-bottom:6px}.de{font-size:13px;color:#888}
.b{background:#fff;border-radius:12px;padding:14px;margin-top:20px;text-align:center;font-size:13px;box-shadow:0 2px 10px rgba(0,0,0,.08)}
.f{text-align:center;color:rgba(255,255,255,.7);margin-top:24px;font-size:12px}
</style></head><body><div class="c">
<div class="h"><h1>📋 案件处理启动器</h1><p>集成多个案件处理工具</p></div>
<div class="g">
<div class="i" onclick="window.open('/report-standard')"><div class="ic">📄</div><div class="nm">报告标准化</div><div class="de">DOCX格式转换+预设模板</div></div>
<div class="i" onclick="window.open('/tools/report_generate/index.html')"><div class="ic">📋</div><div class="nm">报告生成</div><div class="de">AI生成勘查报告</div></div>
<div class="i" onclick="window.open('/tools/index4.html')"><div class="ic">📑</div><div class="nm">目录工具</div><div class="de">附件清单表格</div></div>
<div class="i" onclick="window.open('/tools/index3.html')"><div class="ic">✅</div><div class="nm">结案审批表</div><div class="de">填写结案审批表</div></div>
<div class="i" onclick="window.open('/tools/附件处理器-合并版/index.html')"><div class="ic">🖼️</div><div class="nm">附件处理器</div><div class="de">图片→Markdown→Word</div></div>
</div>
<div class="b">✅ 共 5 个工具</div>
<div class="f"></div>
</div></body></html>"""

@app.get('/')
async def root():
    return HTMLResponse(HOME)

@app.get('/api/health')
async def health():
    return {'status':'ok','service':'combined-backend','version':'2.0.0'}

@app.get('/static/{fp:path}')
async def serve_static(fp:str):
    sp=BASE_DIR/'static';p=(sp/fp).resolve()
    if not str(p).startswith(str(sp.resolve())) or not p.is_file():raise HTTPException(404)
    return FileResponse(str(p),media_type=MIME.get(p.suffix.lower(),'application/octet-stream'))

@app.get('/tools/{fp:path}')
async def serve_tools(fp:str):
    td=BASE_DIR/'tools';p=(td/fp).resolve()
    if not str(p).startswith(str(td.resolve())):raise HTTPException(403)
    if p.is_file():return FileResponse(str(p),media_type=MIME.get(p.suffix.lower(),'application/octet-stream'))
    h2=p.with_suffix('.html')
    if h2.is_file():return FileResponse(str(h2),media_type=MIME.get(h2.suffix.lower(),'application/octet-stream'))
    raise HTTPException(404)

@app.get('/report-standard')
async def report_standard():
    tp=BASE_DIR/'templates'/'index.html'
    if tp.exists():return HTMLResponse(tp.read_text(encoding='utf-8'))
    return HTMLResponse('<h1>报告标准化</h1>')

if __name__=='__main__':
    import uvicorn
    import multiprocessing
    p=int(os.environ.get('PORT',10000))
    w=int(os.environ.get('WORKERS',0))
    kw={}
    # 重要：多 workers 模式下内存中的 _generated_reports/_template_storage 不共享，
    # 因此生产环境只能使用单 worker，通过 Gunicorn 多进程部署时需改用文件存储。
    if w>0:
        kw['workers']=w
    else:
        kw['workers']=1
    uvicorn.run('combined_backend:app',host='0.0.0.0',port=p,log_level='info',access_log=False,timeout_keep_alive=600,**kw)

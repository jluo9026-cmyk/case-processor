"""
案件处理启动器 - 合并后端服务 (Render.com云部署版本)
包含附件处理器完整API支持 + 网页版首页（5个工具）
"""
import os, sys, uuid, json, io, re, base64, urllib.request, asyncio, zipfile
from datetime import datetime
from pathlib import Path
import tempfile

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

from modules.config import HAS_MODULES
from modules.app_core import app
import modules.routes as _routes
from modules.routes import _generated_reports
from modules.template_data import PRESET_TEMPLATES, _get_preset_template

from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi import HTTPException, Request

TEMP_DIR = Path(tempfile.gettempdir()) / 'case_processor'
TEMP_DIR.mkdir(exist_ok=True)
UPLOAD_DIR = TEMP_DIR / 'uploads'
OUTPUT_DIR = TEMP_DIR / 'output'
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

MIME_TYPES = {
    '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'application/javascript',
    '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.svg': 'image/svg+xml', '.ico': 'image/x-icon',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}

# ============ 附件处理器状态 ============
_attachment_images = []
_attachment_current_ranges = []
_sse_clients = set()

DEFAULT_ATTACHMENT_NAMES = ["案卷资料记载（报案记录）及保单","惠州市中拓模塑科技有限公司车间现场照片","大门监控视频截图","刘华妹询问笔录","马少康个体诊所走访记录","走访东莞市松山湖中心医院","走访社保局","黄昭伯身份证","受益人身份证","认定工伤决定书","工亡待遇核定单","死亡证明"]

DEFAULT_RANGES = [{"start":i*3,"end":min(i*3+2,53),"idx":i} for i in range(12)]


# ============ 网页版首页（5个工具，内嵌HTML，不依赖index.html）============
WEB_HOME = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>案件处理启动器</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Microsoft YaHei',sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);min-height:100vh;padding:30px}
.container{max-width:1000px;margin:0 auto}
.header{background:#fff;border-radius:16px;padding:28px;margin-bottom:24px;text-align:center;box-shadow:0 4px 20px rgba(0,0,0,.1)}
.header h1{color:#1a1a2e;font-size:26px}
.header p{color:#666;font-size:14px;margin-top:6px}
.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:16px;margin-top:20px}
.card{background:#fff;border-radius:16px;padding:28px;text-align:center;cursor:pointer;border:2px solid transparent;box-shadow:0 4px 20px rgba(0,0,0,.1);transition:all .3s}
.card:hover{transform:translateY(-4px);border-color:#667eea;box-shadow:0 8px 30px rgba(0,0,0,.15)}
.icon{font-size:42px;margin-bottom:12px}
.name{font-size:18px;font-weight:600;color:#1a1a2e;margin-bottom:6px}
.desc{font-size:13px;color:#888}
.bar{background:#fff;border-radius:12px;padding:14px;margin-top:20px;text-align:center;font-size:13px;box-shadow:0 2px 10px rgba(0,0,0,.08)}
.ft{text-align:center;color:rgba(255,255,255,.7);margin-top:24px;font-size:12px}
</style></head>
<body><div class="container">
<div class="header"><h1>📋 案件处理启动器</h1><p>集成多个案件处理工具，统一管理，高效协作</p></div>
<div class="grid">
<div class="card" onclick="window.open('/tools/report_generate/index.html','_blank')"><div class="icon">📝</div><div class="name">报告生成</div><div class="desc">上传图片+笔录→自动生成勘查报告</div></div>
<div class="card" onclick="window.open('/report-standard','_blank')"><div class="icon">📄</div><div class="name">报告标准化</div><div class="desc">DOCX格式转换+预设模板</div></div>
<div class="card" onclick="window.open('/tools/index4.html','_blank')"><div class="icon">📑</div><div class="name">目录工具</div><div class="desc">生成附件清单Word表格</div></div>
<div class="card" onclick="window.open('/tools/index3.html','_blank')"><div class="icon">✅</div><div class="name">结案审批表</div><div class="desc">填写结案审批表</div></div>
<div class="card" onclick="window.open('/attachment-tool','_blank')"><div class="icon">🖼️</div><div class="name">附件处理器</div><div class="desc">上传图片→映射→Markdown→Word一键生成</div></div>
</div>
<div class="bar">✅ 系统就绪，共 5 个工具</div>
<div class="ft">深圳市德泰保险公估有限公司</div>
</div></body></html>"""


def sse_broadcast(data):
    msg = f"data: {json.dumps(data)}\n\n"
    dead = set()
    for client in _sse_clients:
        try:
            client.write(msg.encode())
        except:
            dead.add(client)
    _sse_clients -= dead


# ============ 路由 ============
@app.get('/')
async def serve_index():
    """网页版首页 - 5个工具"""
    return HTMLResponse(WEB_HOME)


@app.get('/api/health')
async def health_check():
    return {'status':'ok','service':'combined-backend','version':'2.0.0','tools':5}


@app.post('/api/test')
async def test_endpoint():
    return {'success':True,'message':'后端服务正常运行'}


# ============ 静态文件服务 ============
@app.get('/static/{file_path:path}')
async def serve_static(file_path: str):
    static_dir = BASE_DIR / 'static'
    full_path = (static_dir / file_path).resolve()
    if not str(full_path).startswith(str(static_dir.resolve())) or not full_path.is_file():
        return HTMLResponse('', status_code=404)
    return FileResponse(str(full_path), media_type=MIME_TYPES.get(full_path.suffix.lower(), 'application/octet-stream'))


@app.get('/tools/{file_path:path}')
async def serve_tools(file_path: str):
    tools_dir = BASE_DIR / 'tools'
    full_path = (tools_dir / file_path).resolve()
    if not str(full_path).startswith(str(tools_dir.resolve())):
        raise HTTPException(403)
    if full_path.is_file():
        return FileResponse(str(full_path), media_type=MIME_TYPES.get(full_path.suffix.lower(), 'application/octet-stream'))
    if '.' not in file_path:
        h = full_path.with_suffix('.html')
        if h.is_file():
            return FileResponse(str(h), media_type=MIME_TYPES.get(h.suffix.lower(), 'application/octet-stream'))
    raise HTTPException(404)


@app.get('/report-standard')
async def serve_report_standard():
    tpl_path = BASE_DIR / 'templates' / 'index.html'
    if tpl_path.exists():
        return HTMLResponse(tpl_path.read_text(encoding='utf-8'))
    return HTMLResponse('报告标准化页面')


@app.get('/attachment-tool')
async def serve_attachment_tool():
    """附件处理器页面 - 从原始附件处理器读取"""
    att_path = BASE_DIR / 'tools' / '附件处理器-合并版' / 'index.html'
    if att_path.exists():
        return HTMLResponse(att_path.read_text(encoding='utf-8'))
    return HTMLResponse('<h1>附件处理器</h1><p>页面加载中</p>')


# 附件处理器API
@app.get('/api/default-names')
async def get_default_names():
    return {"names":DEFAULT_ATTACHMENT_NAMES,"ranges":DEFAULT_RANGES}

@app.get('/api/ranges')
async def get_ranges():
    global _attachment_current_ranges
    if not _attachment_current_ranges:
        _attachment_current_ranges = [dict(r) for r in DEFAULT_RANGES]
    return {"ranges":_attachment_current_ranges}

@app.put('/api/ranges')
async def update_ranges(request:Request):
    global _attachment_current_ranges
    data = await request.json()
    _attachment_current_ranges = data.get('ranges', _attachment_current_ranges)
    return {"success":True,"ranges":_attachment_current_ranges}

@app.post('/api/ranges/reset')
async def reset_ranges():
    global _attachment_current_ranges
    _attachment_current_ranges = [dict(r) for r in DEFAULT_RANGES]
    return {"success":True,"ranges":_attachment_current_ranges}

@app.get('/api/progress')
async def sse_progress(request:Request):
    from fastapi.responses import StreamingResponse
    async def gen():
        cid = id(request)
        _sse_clients.add(cid)
        try:
            yield f"data: {json.dumps({'type':'connected','message':'SSE连接已建立'})}\n\n"
            while True:
                await asyncio.sleep(30)
                yield ": keepalive\n\n"
        except:
            pass
        finally:
            _sse_clients.discard(cid)
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control":"no-cache","Connection":"keep-alive"})

@app.post('/api/upload-images')
async def upload_images(request:Request):
    global _attachment_images
    try:
        form = await request.form()
        images = []
        for key in form.keys():
            val = form.get(key)
            if val and hasattr(val,'read'):
                content = await val.read()
                if content:
                    fn = f"img_{uuid.uuid4().hex}.jpg"
                    fp = UPLOAD_DIR / fn
                    with open(fp,'wb') as f: f.write(content)
                    images.append({"index":len(_attachment_images)+len(images),"name":getattr(val,'filename',fn),"size":len(content),"filepath":str(fp)})
        _attachment_images.extend(images)
        sse_broadcast({"type":"images","status":"uploaded","count":len(images),"message":f"已上传 {len(images)} 张图片"})
        return {"success":True,"count":len(images),"images":images}
    except Exception as e:
        raise HTTPException(500,str(e))

@app.post('/api/upload-docx')
async def upload_docx(request:Request):
    try:
        form = await request.form()
        file = None
        for key in form.keys():
            val = form.get(key)
            if val and hasattr(val,'read'): file = val; break
        if not file: raise HTTPException(400,'请上传DOCX文件')
        content = await file.read()
        from docx import Document as DocxDocument
        doc = DocxDocument(io.BytesIO(content))
        text = '\n'.join([p.text for p in doc.paragraphs if p.text.strip()])
        title = next((l for l in text.split('\n') if len(l.strip())>5), '未命名文档')
        return {"success":True,"content":text,"title":title,"header":{"text":title,"hasIcon":False},"imageSizes":[]}
    except Exception as e:
        raise HTTPException(500,str(e))

@app.post('/api/generate-markdown')
async def generate_markdown(request:Request):
    try:
        data = await request.json()
        images = data.get('images',[])
        names_text = data.get('attachmentNames','')
        names = DEFAULT_ATTACHMENT_NAMES[:]
        if names_text.strip():
            lines = [l.strip() for l in names_text.split('\n') if l.strip()]
            for i,line in enumerate(lines):
                if i<len(names):
                    m = re.match(r'^附件[一二三四五六七八九十\d]+[：:.]?\s*(.*)', line)
                    if m and m.group(1): names[i] = m.group(1)
                    elif not line.startswith('附件'): names[i] = line
        ranges = data.get('customRanges') or DEFAULT_RANGES
        chn = ['一','二','三','四','五','六','七','八','九','十','十一','十二']
        md_lines = []
        for i,r in enumerate(ranges):
            idx_chn = chn[i] if i<12 else str(i+1)
            name = names[r['idx']] if r['idx']<len(names) else f"附件{idx_chn}"
            md_lines.append(f'<span style="float:right;color:red;font-weight:bold;">附件{idx_chn}</span>\n')
            md_lines.append(f'### <span style="text-align:center;display:block;">{name}</span>\n')
            for j in range(r['start'], r['end']+1):
                if j < len(images):
                    fp = images[j].get('filepath','')
                    if fp: md_lines.append(f'<img src="{fp}" width="100%" />\n')
        md = '\n'.join(md_lines)
        sse_broadcast({"type":"markdown","status":"done","message":"Markdown生成完成"})
        return {"success":True,"markdown":md,"attachments":[],"header":{"text":"","hasIcon":False}}
    except Exception as e:
        raise HTTPException(500,str(e))

@app.post('/api/convert-word')
async def convert_word(request:Request):
    try:
        data = await request.json()
        markdown = data.get('markdown','')
        images_data = data.get('images',[])
        from docx import Document as D, shared as S, enum.text as E
        doc = D()
        img_refs = re.findall(r'<img[^>]+src="([^"]+)"', markdown)
        for ref in img_refs:
            for img in images_data:
                fp = img.get('filepath','')
                if fp and os.path.exists(fp):
                    try: doc.add_picture(fp, width=S.Inches(5.5)); doc.paragraphs[-1].alignment = E.WD_ALIGN_PARAGRAPH.CENTER
                    except: pass
        out_fn = f"output_{uuid.uuid4().hex}.docx"
        out_path = TEMP_DIR / out_fn
        doc.save(str(out_path))
        sse_broadcast({"type":"word","status":"done","message":"Word文档生成完成！","outputPath":out_fn})
        return {"success":True,"outputPath":str(out_path),"size":os.path.getsize(out_path)}
    except Exception as e:
        raise HTTPException(500,str(e))

@app.post('/api/one-click')
async def one_click(request:Request):
    try:
        data = await request.json()
        images_data = data.get('images',[])
        total = len(images_data)
        sse_broadcast({"type":"oneclick","phase":"build","status":"processing","progress":0,"message":"构建附件映射..."})
        await asyncio.sleep(0.1)
        from docx import Document as D, shared as S, enum.text as E
        from PIL import Image as PILImage
        doc = D()
        for i, img in enumerate(images_data):
            fp = img.get('filepath','')
            chn = ['一','二','三','四','五','六','七','八','九','十','十一','十二']
            idx_chn = chn[i] if i<12 else str(i+1)
            if fp and os.path.exists(fp):
                p = doc.add_paragraph(); p.alignment = E.WD_ALIGN_PARAGRAPH.RIGHT
                r = p.add_run(f"附件{idx_chn}"); r.bold = True; r.font.size = S.Pt(11)
                try:
                    pil = PILImage.open(fp)
                    if pil.width > pil.height: doc.add_picture(fp, width=S.Inches(7.38))
                    else: doc.add_picture(fp, width=S.Inches(5.53))
                    doc.paragraphs[-1].alignment = E.WD_ALIGN_PARAGRAPH.CENTER
                except: pass
            pct = 10 + int((i+1)/total * 60)
            sse_broadcast({"type":"oneclick","phase":"progress","current":i+1,"total":total,"progress":pct})
        out_fn = f"output_{uuid.uuid4().hex}.docx"
        out_path = TEMP_DIR / out_fn
        doc.save(str(out_path))
        sse_broadcast({"type":"oneclick","phase":"done","status":"success","progress":100,"message":"全流程完成！","outputPath":out_fn,"stats":{"images":total,"size":os.path.getsize(out_path)}})
        return {"success":True,"outputPath":str(out_path),"filename":out_fn,"size":os.path.getsize(out_path)}
    except Exception as e:
        sse_broadcast({"type":"oneclick","phase":"error","status":"error","message":f"全流程失败：{str(e)}"})
        raise HTTPException(500,f'全流程失败: {str(e)}')

@app.get('/api/download/{filename}')
async def download_file(filename:str):
    for d in [TEMP_DIR, OUTPUT_DIR, UPLOAD_DIR]:
        fp = d / filename
        if fp.is_file(): return FileResponse(str(fp), filename=filename, media_type=MIME_TYPES.get(fp.suffix.lower(),'application/octet-stream'))
    raise HTTPException(404,'文件不存在')

@app.post('/api/cleanup')
async def cleanup_temp():
    cleaned = 0
    now = datetime.now().timestamp()
    for d in [TEMP_DIR, UPLOAD_DIR]:
        for f in d.glob('*'):
            if f.is_file() and (now - f.stat().st_mtime) > 3600:
                try: f.unlink(); cleaned+=1
                except: pass
    return {"success":True,"cleaned":cleaned}


# ============ 服务器启动 ============
if __name__ == '__main__':
    import uvicorn
    port = int(os.environ.get('PORT', 10000))
    host = os.environ.get('HOST', '0.0.0.0')
    print(f'=== 后端服务启动在 {host}:{port} ===')
    uvicorn.run(app, host=host, port=port, log_level='info', access_log=False, timeout_keep_alive=600)
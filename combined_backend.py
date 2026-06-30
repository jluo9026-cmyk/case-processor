"""
案件处理启动器 - 合并后端服务 (Render.com云部署版本)
"""
import os, sys, uuid, json, io, re, base64, asyncio, zipfile
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

from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi import HTTPException, Request, UploadFile, File, Form
from modules.app_core import app
import modules.routes
from modules.routes import _generated_reports
from modules.template_data import PRESET_TEMPLATES, _get_preset_template

TEMP_DIR = Path(tempfile.gettempdir()) / 'case_processor'
TEMP_DIR.mkdir(exist_ok=True)
UPLOAD_DIR = TEMP_DIR / 'uploads'
OUTPUT_DIR = TEMP_DIR / 'output'
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

MIME = {'.html':'text/html; charset=utf-8','.css':'text/css','.js':'application/javascript','.json':'application/json','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.gif':'image/gif','.svg':'image/svg+xml','.ico':'image/x-icon','.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}

# SSE queues for attachment processor
_sse_queues = {}

def sse_broadcast(data):
    dead = []
    for cid, q in list(_sse_queues.items()):
        try:
            q.put_nowait(data)
        except:
            dead.append(cid)
    for cid in dead:
        _sse_queues.pop(cid, None)

WEB_HOME = '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>案件处理启动器</title><style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:"Microsoft YaHei",sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);min-height:100vh;padding:30px}.c{max-width:1000px;margin:0 auto}.h{background:#fff;border-radius:16px;padding:28px;margin-bottom:24px;text-align:center}.h h1{color:#1a1a2e;font-size:26px}.h p{color:#666;font-size:14px;margin-top:6px}.g{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}.i{background:#fff;border-radius:16px;padding:28px;text-align:center;cursor:pointer;box-shadow:0 4px 20px rgba(0,0,0,.1)}.i:hover{transform:translateY(-4px)}.ic{font-size:42px;margin-bottom:12px}.nm{font-size:18px;font-weight:600;color:#1a1a2e;}.bar{background:#fff;border-radius:12px;padding:14px;margin-top:20px;text-align:center}.ft{text-align:center;color:rgba(255,255,255,.7);margin-top:24px;font-size:12px}</style></head><body><div class="c"><div class="h"><h1>📋 案件处理启动器</h1><p>集成多个案件处理工具</p></div><div class="g"><div class="i" onclick="window.open(\'/tools/report_generate/index.html\')"><div class="ic">📝</div><div class="nm">报告生成</div></div><div class="i" onclick="window.open(\'/report-standard\')"><div class="ic">📄</div><div class="nm">报告标准化</div></div><div class="i" onclick="window.open(\'/tools/index4.html\')"><div class="ic">📑</div><div class="nm">目录工具</div></div><div class="i" onclick="window.open(\'/tools/index3.html\')"><div class="ic">✅</div><div class="nm">结案审批表</div></div><div class="i" onclick="window.open(\'/attachment-tool\')"><div class="ic">🖼️</div><div class="nm">附件处理器</div></div></div><div class="bar">✅ 共 5 个工具</div><div class="ft">深圳市德泰保险公估有限公司</div></div></body></html>'

@app.get('/')
async def serve_index():
    return HTMLResponse(WEB_HOME)

@app.get('/api/health')
async def health_check():
    return {'status':'ok','service':'combined-backend','version':'2.0.0'}

@app.get('/static/{fp:path}')
async def serve_static(fp:str):
    sp = BASE_DIR/'static'; p = (sp/fp).resolve()
    if not str(p).startswith(str(sp.resolve())) or not p.is_file():
        raise HTTPException(404)
    return FileResponse(str(p), media_type=MIME.get(p.suffix.lower(),'application/octet-stream'))

@app.get('/tools/{fp:path}')
async def serve_tools(fp:str):
    td = BASE_DIR/'tools'; p = (td/fp).resolve()
    if not str(p).startswith(str(td.resolve())):
        raise HTTPException(403)
    if p.is_file(): return FileResponse(str(p), media_type=MIME.get(p.suffix.lower(),'application/octet-stream'))
    h2 = p.with_suffix('.html')
    if h2.is_file(): return FileResponse(str(h2), media_type=MIME.get(h2.suffix.lower(),'application/octet-stream'))
    raise HTTPException(404)

@app.get('/report-standard')
async def serve_report_standard():
    tp = BASE_DIR/'templates'/'index.html'
    if tp.exists(): return HTMLResponse(tp.read_text(encoding='utf-8'))
    return HTMLResponse('<h1>报告标准化</h1>')

@app.get('/attachment-tool')
async def serve_attachment_tool():
    ap = BASE_DIR/'tools'/'附件处理器-合并版'/'index.html'
    if ap.exists(): return HTMLResponse(ap.read_text(encoding='utf-8'))
    return HTMLResponse('<h1>附件处理器</h1>')

# ========== 附件处理器 API ==========
@app.get('/api/progress')
async def sse_progress():
    from fastapi.responses import StreamingResponse
    cid = str(uuid.uuid4())
    q = asyncio.Queue()
    _sse_queues[cid] = q
    async def gen():
        try:
            yield f"data: {json.dumps({'type':'connected','message':'SSE连接已建立'})}\n\n"
            while True:
                try:
                    data = await asyncio.wait_for(q.get(), timeout=25)
                    yield f"data: {json.dumps(data)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except:
            pass
        finally:
            _sse_queues.pop(cid, None)
    return StreamingResponse(gen(), media_type='text/event-stream',
        headers={'Cache-Control':'no-cache','Connection':'keep-alive'})

@app.get('/api/default-names')
async def get_default_names():
    names = ["案卷资料记载（报案记录）及保单","惠州市中拓模塑科技有限公司车间现场照片","大门监控视频截图","刘华妹询问笔录","马少康个体诊所走访记录","走访东莞市松山湖中心医院","走访社保局","黄昭伯身份证","受益人身份证","认定工伤决定书","工亡待遇核定单","死亡证明"]
    ranges = [{"start":i*3,"end":min(i*3+2,53),"idx":i} for i in range(12)]
    return {"names":names,"ranges":ranges}

@app.post('/api/upload-images')
async def upload_images(request:Request):
    form = await request.form()
    images = []
    for key in form.keys():
        val = form.get(key)
        if val and hasattr(val,'read'):
            data = await val.read()
            if data:
                fn = f"img_{uuid.uuid4().hex}.jpg"
                fp = UPLOAD_DIR/fn
                with open(fp,'wb') as f: f.write(data)
                images.append({"index":len(images),"name":getattr(val,'filename',fn),"size":len(data),"filepath":str(fp)})
    sse_broadcast({"type":"images","status":"uploaded","count":len(images),"message":f"已上传{len(images)}张图片"})
    return {"success":True,"count":len(images),"images":images}

@app.post('/api/upload-docx')
async def upload_docx(request:Request):
    form = await request.form()
    file = None
    for key in form.keys():
        val = form.get(key)
        if val and hasattr(val,'read'): file=val; break
    if not file: raise HTTPException(400,'请上传DOCX文件')
    content = await file.read()
    from docx import Document
    doc = Document(io.BytesIO(content))
    text = '\n'.join([p.text for p in doc.paragraphs if p.text.strip()])
    title = next((l for l in text.split('\n') if len(l.strip())>5),'未命名')
    return {"success":True,"content":text,"title":title,"header":{"text":title,"hasIcon":False},"imageSizes":[]}

@app.post('/api/one-click')
async def one_click(request:Request):
    data = await request.json()
    imgs = data.get('images',[])
    sse_broadcast({"type":"oneclick","phase":"build","status":"processing","progress":5,"message":"处理中..."})
    await asyncio.sleep(0.1)
    from docx import Document as D, shared as S, enum.text as E
    from PIL import Image
    doc = D()
    total = len(imgs)
    for i, img in enumerate(imgs):
        fp = img.get('filepath','')
        chn = ['一','二','三','四','五','六','七','八','九','十','十一','十二']
        idx = chn[i] if i<12 else str(i+1)
        if fp and os.path.exists(fp):
            p = doc.add_paragraph(); p.alignment = E.WD_ALIGN_PARAGRAPH.RIGHT
            r = p.add_run(f"附件{idx}"); r.bold=True
            try:
                pil = Image.open(fp)
                if pil.width>pil.height: doc.add_picture(fp,width=S.Inches(7.38))
                else: doc.add_picture(fp,width=S.Inches(5.53))
            except: pass
        sse_broadcast({"type":"oneclick","phase":"progress","current":i+1,"total":total,"progress":10+int((i+1)/total*80)})
    out_fn = f"output_{uuid.uuid4().hex}.docx"
    out_path = TEMP_DIR/out_fn
    doc.save(str(out_path))
    sse_broadcast({"type":"oneclick","phase":"done","status":"success","progress":100,"message":"完成！","outputPath":out_fn})
    return {"success":True,"outputPath":str(out_path),"filename":out_fn,"size":os.path.getsize(out_path)}

@app.get('/api/download/{fn}')
async def download_file(fn:str):
    for d in [TEMP_DIR,OUTPUT_DIR,UPLOAD_DIR]:
        fp = d/fn
        if fp.is_file(): return FileResponse(str(fp),filename=fn,media_type=MIME.get(fp.suffix.lower(),'application/octet-stream'))
    raise HTTPException(404)

if __name__ == '__main__':
    import uvicorn
    port = int(os.environ.get('PORT',10000))
    uvicorn.run(app, host='0.0.0.0', port=port, log_level='info', access_log=False, timeout_keep_alive=600)
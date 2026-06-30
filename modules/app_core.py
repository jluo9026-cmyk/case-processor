from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

MAX_FILE_SIZE = 50 * 1024 * 1024

class FileSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method == 'POST':
            content_length = request.headers.get('content-length')
            if content_length and int(content_length) > MAX_FILE_SIZE:
                return JSONResponse(
                    content={'success': False, 'error': f'文件大小超过限制（最大 {MAX_FILE_SIZE // (1024 * 1024)}MB）'},
                    status_code=413
                )
        return await call_next(request)

app = FastAPI(title='案件处理启动器', version='2.0.0', max_request_size=MAX_FILE_SIZE)

app.add_middleware(FileSizeLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# ===== 注册所有 API 路由（重要：必须在这里 import，才能被 uvicorn 加载）=====
import modules.routes as _routes

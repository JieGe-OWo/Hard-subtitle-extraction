import os
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import APP_TITLE, APP_VERSION, CORS_ORIGINS, DESKTOP_MODE
from app.database import init_db
from app.models import init_admin, init_local_user
from app.routers import admin, auth, extract

app = FastAPI(title=APP_TITLE, version=APP_VERSION, description='Vue3 + FastAPI 前后端分离字幕提取服务')

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(extract.router)


@app.on_event('startup')
def startup():
    init_db()
    if DESKTOP_MODE:
        # 桌面版：不建网页版管理员，只准备本地免登录用户
        init_local_user()
        print('[init] 桌面版启动完成（免登录，内置 SQLite）')
    else:
        init_admin()
        print('[init] 数据库初始化完成，管理员账号已就绪')


@app.get('/api/health')
def health():
    return {'status': 'ok', 'time': time.time()}


@app.get('/api/app-info')
def app_info():
    """前端启动时读取：是否桌面版（决定要不要免登录引导、隐藏账号相关入口）"""
    return {
        'title': APP_TITLE,
        'version': APP_VERSION,
        'desktop': DESKTOP_MODE,
    }


# 前端构建产物（可选）：frontend/dist 存在时由后端直接托管
# 注意：app/main.py 往上三层就是项目根目录（backend/app -> backend -> 项目根），
# 不要再加 '..'，否则会指到项目根的上一级去找 frontend/dist。
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_frontend_dist = os.path.join(_PROJECT_ROOT, 'frontend', 'dist')
if os.path.isdir(_frontend_dist):
    from fastapi.responses import FileResponse, HTMLResponse

    _abs_dist = os.path.abspath(_frontend_dist)

    @app.get('/{full_path:path}')
    def serve_spa(full_path: str):
        if full_path.startswith('api/'):
            raise HTTPException(status_code=404, detail='Not Found')
        candidate = os.path.normpath(os.path.join(_abs_dist, full_path))
        if candidate.startswith(_abs_dist) and os.path.isfile(candidate):
            return FileResponse(candidate)
        index_html = os.path.join(_abs_dist, 'index.html')
        if os.path.isfile(index_html):
            # 桌面/网页模式由后端直接注入到页面里：前端启动时同步就能读到，
            # 不依赖额外的异步请求（避免引导失败又被路由踢回登录页）
            with open(index_html, 'r', encoding='utf-8') as f:
                html = f.read()
            flag = (
                '<script>window.__ZIMU_DESKTOP__=%s;window.__ZIMU_TITLE__=%r;</script>'
                % ('true' if DESKTOP_MODE else 'false', APP_TITLE)
            )
            html = html.replace('</head>', flag + '</head>', 1)
            return HTMLResponse(html, headers={'Cache-Control': 'no-store'})
        raise HTTPException(status_code=404, detail='Not Found')

'''
Description: 
'''
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .config.settings import Settings
from .middleware.concurrency import ConcurrencyMiddleware
from .api.endpoints import dict, tts

# 加载配置
settings = Settings()

# 创建应用
app = FastAPI(
    title="Web Dictation App",
    description="支持中英文的在线听写系统",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加并发控制中间件
concurrency_middleware = ConcurrencyMiddleware(
    app=None,  # 这里设置为None，因为它会在add_middleware时被正确设置
    max_concurrency=settings.MAX_CONCURRENCY,
    timeout=settings.TIMEOUT
)
app.add_middleware(ConcurrencyMiddleware)

# 注册API路由
app.include_router(dict.router)
app.include_router(tts.router)

@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化"""
    # 初始化TTS缓存文件
    await tts.init_cache_files()

@app.get("/api/status")
async def get_status():
    """获取系统状态"""
    try:
        status = await concurrency_middleware.get_status()
        return {
            "success": True,
            "data": status
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }

# 挂载静态文件
# 先挂载特定的静态资源目录
app.mount("/js", StaticFiles(directory="frontend/js"), name="javascript")
app.mount("/css", StaticFiles(directory="frontend/css"), name="css")
app.mount("/img", StaticFiles(directory="frontend/img"), name="images")

# 最后挂载根目录的 index.html
app.mount("/", StaticFiles(directory="frontend", html=True), name="static")

@app.get("/")
async def root():
    """根路由"""
    return {
        "success": True,
        "message": "Web Dictation App API",
        "version": "1.0.0"
    } 
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from asyncio import Semaphore, Lock
import time
from typing import Dict, Optional, List

class ConcurrencyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_concurrency: int = 3, timeout: int = 300):
        """
        初始化并发控制中间件
        
        Args:
            app: ASGI应用
            max_concurrency: 最大并发数
            timeout: 会话超时时间（秒）
        """
        super().__init__(app)
        self.semaphore = Semaphore(max_concurrency)
        self.lock = Lock()
        self.max_concurrency = max_concurrency
        self.timeout = timeout
        self.active_sessions: Dict[str, float] = {}
        self.whitelist_paths = [
            "/",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/status",
            "/api/lessons",
            "/api/tts/voices",
            "/js/app.js",
            "/favicon.ico"
        ]
        
    async def _cleanup_expired_sessions(self):
        """清理过期会话"""
        current_time = time.time()
        async with self.lock:
            expired = [
                session_id
                for session_id, start_time in self.active_sessions.items()
                if current_time - start_time > self.timeout
            ]
            for session_id in expired:
                del self.active_sessions[session_id]
                
    async def get_status(self) -> dict:
        """获取当前并发状态"""
        await self._cleanup_expired_sessions()
        return {
            "currentConcurrency": len(self.active_sessions),
            "maxConcurrency": self.max_concurrency,
            "waiting": max(0, len(self.active_sessions) - self.max_concurrency)
        }
        
    async def dispatch(self, request: Request, call_next):
        """
        中间件主处理函数
        
        Args:
            request: FastAPI请求对象
            call_next: 下一个处理函数
            
        Returns:
            响应对象
        """
        # 检查是否是白名单路径
        if request.url.path in self.whitelist_paths:
            return await call_next(request)
            
        # 检查是否是静态文件
        if request.url.path.startswith(("/js/", "/css/", "/img/")):
            return await call_next(request)
            
        # 检查是否是API路由
        if request.url.path.startswith("/api/"):
            # 只对TTS生成接口进行并发控制
            if request.url.path == "/api/tts" and request.method == "POST":
                session_id = request.headers.get("X-Session-ID")
                if not session_id:
                    raise HTTPException(status_code=400, detail="缺少会话ID")
                    
                # 清理过期会话
                await self._cleanup_expired_sessions()
                
                # 检查是否是活跃会话
                current_time = time.time()
                async with self.lock:
                    if session_id in self.active_sessions:
                        self.active_sessions[session_id] = current_time
                        return await call_next(request)
                        
                try:
                    # 尝试获取信号量
                    async with self.semaphore:
                        async with self.lock:
                            self.active_sessions[session_id] = current_time
                        response = await call_next(request)
                        return response
                        
                except Exception as e:
                    # 发生错误时清理会话
                    async with self.lock:
                        self.active_sessions.pop(session_id, None)
                    raise e
            else:
                return await call_next(request)
                
        return await call_next(request) 
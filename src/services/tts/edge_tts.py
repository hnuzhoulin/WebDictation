import edge_tts
from typing import Optional, List, Dict, Any
import asyncio
from pathlib import Path
import tempfile
import hashlib
import time
import os
import aiohttp
from aiohttp import ClientSession, TCPConnector
import ssl
import certifi
import datetime
import sys

# 为旧版本 Python 添加 UTC 支持
if not hasattr(datetime, 'UTC'):
    datetime.UTC = datetime.timezone.utc

class EdgeTTSService:
    def __init__(self):
        # 使用项目根目录下的cache目录
        self._cache_dir = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))) / "cache/tts/words"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache = {}  # 内存缓存
        self._max_concurrent = 5  # 最大并发数
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._voices_cache = None  # 语音列表缓存
        self._voices_cache_time = 0  # 语音列表缓存时间
        self._voices_cache_ttl = 3600  # 缓存有效期（1小时）
        
        # 获取代理设置
        self._proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('HTTP_PROXY')
        if self._proxy and self._proxy.startswith('http://'):
            # 转换 HTTP 代理为 HTTPS 和 WSS
            self._proxy_host = self._proxy.split('://')[1].split(':')[0]
            self._proxy_port = int(self._proxy.split(':')[-1])
            self._https_proxy = f"http://{self._proxy_host}:{self._proxy_port}"
            self._wss_proxy = f"http://{self._proxy_host}:{self._proxy_port}"
        
        # 创建共享的 SSL 上下文和连接器
        self._ssl_context = ssl.create_default_context(cafile=certifi.where())
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE
        
        self._connector = TCPConnector(
            limit=self._max_concurrent,  # 限制最大连接数
            ttl_dns_cache=300,  # DNS缓存时间
            use_dns_cache=True,
            ssl=self._ssl_context  # 只使用 ssl 参数，不使用 verify_ssl
        )
        self._session = None  # ClientSession将在需要时创建
        
    async def _get_session(self) -> ClientSession:
        """获取或创建共享的会话"""
        if self._session is None or self._session.closed:
            # 配置代理
            if hasattr(self, '_proxy'):
                self._session = ClientSession(
                    connector=self._connector,
                    trust_env=True,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0'
                    }
                )
                if self._https_proxy:
                    self._session.proxy = self._https_proxy
            else:
                self._session = ClientSession(
                    connector=self._connector,
                    trust_env=True
                )
        return self._session
        
    async def _close_session(self):
        """关闭会话"""
        if self._session and not self._session.closed:
            await self._session.close()
            
    async def generate_audio_batch(
        self,
        texts: List[str],
        voice: str = "zh-CN-XiaoxiaoNeural",
        rate: float = 1.0,
        max_retries: int = 10,
        initial_retry_delay: float = 1.0,
        chunk_size: int = 5  # 每批处理的数量
    ) -> Dict[str, Optional[bytes]]:
        """
        批量生成音频数据
        
        Args:
            texts: 要转换的文本列表
            voice: 语音名称
            rate: 语速 (0.5-2.0)
            max_retries: 最大重试次数
            initial_retry_delay: 初始重试延迟（秒）
            chunk_size: 每批处理的数量
            
        Returns:
            Dict[str, Optional[bytes]]: 文本到音频数据的映射
        """
        results = {}
        session = await self._get_session()
        
        # 将文本分成多个批次
        for i in range(0, len(texts), chunk_size):
            chunk = texts[i:i + chunk_size]
            tasks = []
            
            # 创建当前批次的所有任务
            for text in chunk:
                task = asyncio.create_task(
                    self.generate_audio(
                        text=text,
                        voice=voice,
                        rate=rate,
                        max_retries=max_retries,
                        initial_retry_delay=initial_retry_delay,
                        session=session
                    )
                )
                tasks.append((text, task))
            
            # 等待当前批次的所有任务完成
            for text, task in tasks:
                try:
                    audio_data = await task
                    results[text] = audio_data
                except Exception as e:
                    print(f"生成音频失败 ({text}): {str(e)}")
                    results[text] = None
                    
        return results
        
    async def generate_audio(
        self,
        text: str,
        voice: str = "zh-CN-XiaoxiaoNeural",
        rate: float = 1.0,
        max_retries: int = 10,
        initial_retry_delay: float = 1.0,
        session: Optional[ClientSession] = None
    ) -> Optional[bytes]:
        """生成音频数据"""
        start_time = time.time()
        print(f"开始处理TTS请求: {text}")
        
        # 调整语速范围
        rate = max(0.5, min(2.0, rate))
        
        # 生成缓存键
        cache_key = self._get_cache_key(text, voice, rate)
        
        # 检查内存缓存
        if cache_key in self._cache:
            print(f"命中内存缓存，耗时: {(time.time() - start_time):.2f}秒")
            return self._cache[cache_key]
            
        # 检查文件缓存
        cache_file = self._cache_dir / f"{cache_key}.mp3"
        if cache_file.exists():
            # 检查文件大小
            if cache_file.stat().st_size > 0:
                audio_data = cache_file.read_bytes()
                self._cache[cache_key] = audio_data
                print(f"命中文件缓存，耗时: {(time.time() - start_time):.2f}秒")
                return audio_data
            else:
                # 删除空文件
                print(f"删除空的缓存文件: {cache_file}")
                cache_file.unlink()
        
        # 生成新的音频
        print("开始调用 Edge TTS 服务...")
        tts_start_time = time.time()
        temp_file = None
        
        # 使用提供的会话或创建新会话
        should_close_session = False
        if session is None:
            session = await self._get_session()
            should_close_session = True
            
        try:
            for attempt in range(max_retries):
                try:
                    async with self._semaphore:  # 限制并发数
                        # 创建通信对象
                        rate_str = "+" if rate >= 1 else "-"
                        rate_str += f"{abs(int((rate - 1) * 100))}%"
                        communicate = edge_tts.Communicate(
                            text,
                            voice,
                            rate=rate_str
                        )
                        
                        # 设置会话和代理
                        communicate._client_session = session
                        if hasattr(self, '_wss_proxy'):
                            communicate._websocket_kwargs = {
                                "proxy": self._wss_proxy,
                                "ssl": self._ssl_context
                            }
                        
                        # 生成音频
                        temp_file = cache_file.with_suffix('.tmp')
                        await communicate.save(str(temp_file))
                        
                        # 验证生成的文件
                        if not temp_file.exists() or temp_file.stat().st_size == 0:
                            raise Exception("生成的音频文件为空")
                        
                        # 读取音频数据
                        audio_data = temp_file.read_bytes()
                        
                        # 如果成功读取，将临时文件移动到缓存文件
                        temp_file.replace(cache_file)
                        
                        # 更新内存缓存
                        self._cache[cache_key] = audio_data
                        
                        print(f"Edge TTS 服务调用完成，耗时: {(time.time() - tts_start_time):.2f}秒")
                        total_time = time.time() - start_time
                        print(f"TTS请求处理完成，总耗时: {total_time:.2f}秒")
                        
                        return audio_data
                        
                except Exception as e:
                    # 清理临时文件
                    if temp_file and temp_file.exists():
                        temp_file.unlink()
                    
                    # 如果是最后一次尝试，则抛出异常
                    if attempt == max_retries - 1:
                        print(f"生成音频失败，已达到最大重试次数: {str(e)}")
                        print(f"错误发生时总耗时: {(time.time() - start_time):.2f}秒")
                        return None
                    
                    # 计算下一次重试的延迟时间（指数退避）
                    retry_delay = initial_retry_delay * (2 ** attempt)
                    print(f"第 {attempt + 1} 次尝试失败: {str(e)}")
                    print(f"等待 {retry_delay:.1f} 秒后重试...")
                    await asyncio.sleep(retry_delay)
                    
        finally:
            # 如果是我们创建的会话，则关闭它
            if should_close_session:
                await session.close()
                
    async def get_available_voices(self) -> list:
        """
        获取可用的语音列表
        
        Returns:
            语音列表
        """
        try:
            # 检查缓存是否有效
            current_time = time.time()
            if (self._voices_cache is not None and 
                current_time - self._voices_cache_time < self._voices_cache_ttl):
                print("使用缓存的语音列表")
                return self._voices_cache
                
            print("从 Edge TTS 服务获取语音列表...")
            start_time = time.time()
            voices = await edge_tts.list_voices()
            voices_list = [
                {
                    "name": voice["ShortName"],
                    "locale": voice["Locale"],
                    "gender": voice["Gender"]
                }
                for voice in voices
            ]
            
            # 更新缓存
            self._voices_cache = voices_list
            self._voices_cache_time = current_time
            
            print(f"获取语音列表完成，耗时: {(time.time() - start_time):.2f}秒")
            return voices_list
            
        except Exception as e:
            print(f"获取语音列表失败: {str(e)}")
            # 如果有缓存，在出错时返回缓存的数据
            if self._voices_cache is not None:
                print("使用缓存的语音列表（出错回退）")
                return self._voices_cache
            return [] 

    def check_cache_exists(self, text: str, voice: str, rate: float) -> bool:
        """检查指定文本的缓存是否存在"""
        cache_key = self._get_cache_key(text, voice, rate)
        return cache_key in self._cache or (self._cache_dir / f"{cache_key}.mp3").exists()

    async def ensure_cache(self, text: str, voice: str, rate: float) -> bool:
        """确保指定文本的缓存存在，如果不存在则生成"""
        try:
            if not self.check_cache_exists(text, voice, rate):
                await self.generate_audio(text, voice, rate)
            return True
        except Exception as e:
            print(f"缓存生成失败: {str(e)}")
            return False

    async def prepare_batch_cache(self, texts: list[str], voice: str, rate: float) -> tuple[bool, list[str]]:
        """为一批文本准备缓存"""
        # 使用批量生成方法
        results = await self.generate_audio_batch(
            texts=texts,
            voice=voice,
            rate=rate,
            chunk_size=5  # 每次并行处理5个请求
        )
        
        # 收集失败的文本
        failed_texts = [text for text, audio in results.items() if audio is None]
        return len(failed_texts) == 0, failed_texts
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        await self._close_session()

    def _get_cache_key(self, text: str, voice: str, rate: float) -> str:
        """生成缓存键"""
        return hashlib.md5(f"{text}_{voice}_{rate}".encode()).hexdigest() 
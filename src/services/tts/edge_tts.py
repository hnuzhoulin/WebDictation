import edge_tts
from typing import Optional
import asyncio
from pathlib import Path
import tempfile
import hashlib
import time

class EdgeTTSService:
    def __init__(self):
        self._temp_dir = Path(tempfile.gettempdir()) / "web_dictation_tts"
        self._temp_dir.mkdir(exist_ok=True)
        self._cache = {}  # 内存缓存
        self._max_concurrent = 3  # 最大并发数
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._voices_cache = None  # 语音列表缓存
        self._voices_cache_time = 0  # 语音列表缓存时间
        self._voices_cache_ttl = 3600  # 缓存有效期（1小时）
        
    def _get_cache_key(self, text: str, voice: str, rate: float) -> str:
        """生成缓存键"""
        return hashlib.md5(f"{text}_{voice}_{rate}".encode()).hexdigest()
        
    async def generate_audio(
        self,
        text: str,
        voice: str = "zh-CN-XiaoxiaoNeural",
        rate: float = 1.0
    ) -> Optional[bytes]:
        """
        生成音频数据
        
        Args:
            text: 要转换的文本
            voice: 语音名称
            rate: 语速 (0.5-2.0)
            
        Returns:
            音频数据（bytes）
        """
        try:
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
            temp_file = self._temp_dir / f"{cache_key}.mp3"
            if temp_file.exists():
                audio_data = temp_file.read_bytes()
                self._cache[cache_key] = audio_data
                print(f"命中文件缓存，耗时: {(time.time() - start_time):.2f}秒")
                return audio_data
            
            # 生成新的音频
            print("开始调用 Edge TTS 服务...")
            tts_start_time = time.time()
            
            async with self._semaphore:  # 限制并发数
                # 创建通信对象
                communicate = edge_tts.Communicate(
                    text,
                    voice,
                    rate=f"+{int((rate - 1) * 100)}%"
                )
                
                # 生成音频
                await communicate.save(str(temp_file))
                
                # 读取音频数据
                audio_data = temp_file.read_bytes()
                self._cache[cache_key] = audio_data
                
                print(f"Edge TTS 服务调用完成，耗时: {(time.time() - tts_start_time):.2f}秒")
                total_time = time.time() - start_time
                print(f"TTS请求处理完成，总耗时: {total_time:.2f}秒")
                
                return audio_data
            
        except Exception as e:
            print(f"生成音频失败: {str(e)}")
            print(f"错误发生时总耗时: {(time.time() - start_time):.2f}秒")
            return None
        
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
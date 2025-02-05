from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from typing import Optional, List
from ...services.tts.factory import TTSFactory
from ...config.settings import Settings
from pydantic import BaseModel
import tempfile
from pathlib import Path
import asyncio
import os
import edge_tts
import time
import subprocess
import traceback
import logging
import platform
import shutil
import aiohttp
from aiohttp import ClientSession, TCPConnector
import json

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tts", tags=["tts"])
settings = Settings()

# 创建必要的目录
BASE_DIR = Path().absolute()
MP3_DIR = BASE_DIR / "MP3"
CACHE_DIR = BASE_DIR / "cache/tts"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
MP3_DIR.mkdir(exist_ok=True)

# 缓存文件路径
START_PROMPT_FILE = CACHE_DIR / "start_prompt.mp3"
END_PROMPT_FILE = CACHE_DIR / "end_prompt.mp3"
SILENCE_FILE = CACHE_DIR / "silence_1s.mp3"

async def init_cache_files():
    """初始化缓存文件"""
    try:
        # 生成开始提示音
        if not START_PROMPT_FILE.exists():
            logger.info("生成开始提示音缓存")
            communicate = edge_tts.Communicate(
                "请开始听写",
                settings.TTS_ENGINES["edge-tts"]["default_voice"]
            )
            await communicate.save(str(START_PROMPT_FILE))

        # 生成结束提示音
        if not END_PROMPT_FILE.exists():
            logger.info("生成结束提示音缓存")
            communicate = edge_tts.Communicate(
                "听写完成",
                settings.TTS_ENGINES["edge-tts"]["default_voice"]
            )
            await communicate.save(str(END_PROMPT_FILE))

        # 生成1秒静音文件
        if not SILENCE_FILE.exists():
            logger.info("生成静音文件缓存")
            cmd = [
                'ffmpeg', '-f', 'lavfi',
                '-i', 'anullsrc=r=44100:cl=stereo',
                '-t', '1',
                '-q:a', '9',
                '-acodec', 'libmp3lame',
                str(SILENCE_FILE),
                '-y'
            ]
            if platform.system() == 'Windows':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                result = subprocess.run(cmd, capture_output=True, startupinfo=startupinfo)
            else:
                result = subprocess.run(cmd, capture_output=True)

            if result.returncode != 0:
                stderr = result.stderr.decode('utf-8', errors='ignore')
                raise Exception(f"生成静音文件失败: {stderr}")

    except Exception as e:
        logger.error(f"初始化缓存文件失败: {str(e)}\n{traceback.format_exc()}")
        raise

class TTSRequest(BaseModel):
    text: str
    engine: str = "edge-tts"
    voice: Optional[str] = None
    rate: float = 1.0

class BatchTTSRequest(BaseModel):
    words: List[str]
    engine: str = "edge-tts"
    voice: Optional[str] = None
    rate: float = 1.0
    repeatCount: int = 1
    repeatInterval: float = 3.0
    grade: Optional[str] = None
    lesson: Optional[str] = None

class CacheCheckRequest(BaseModel):
    words: List[str]
    engine: str = "edge-tts"
    voice: Optional[str] = None
    rate: float = 1.0

class CheckCacheRequest(BaseModel):
    words: List[str]
    engine: str
    voice: str
    rate: float

class CheckCacheResponse(BaseModel):
    ready: bool
    failed_words: List[str]
    progress: int  # 添加进度字段
    total: int     # 添加总数字段

async def generate_audio_with_retry(text: str, voice: str, rate: float, output_file: Path, max_retries: int = 3, retry_delay: float = 1.0):
    """带重试机制的音频生成函数"""
    for attempt in range(max_retries):
        try:
            # 创建 Communicate 实例
            rate_str = "+" if rate >= 1 else "-"
            rate_str += f"{abs(int((rate - 1) * 100))}%"
            communicate = edge_tts.Communicate(
                text,
                voice,
                rate=rate_str
            )
            
            # 设置不验证 SSL
            communicate._client_session_kwargs = {
                "connector": TCPConnector(verify_ssl=False)
            }
            
            # 生成音频
            await communicate.save(str(output_file))
            return True
                
        except aiohttp.ClientError as e:
            logger.warning(f"第 {attempt + 1} 次尝试生成音频失败: {str(e)}")
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)  # 指数退避
                logger.info(f"等待 {wait_time:.1f} 秒后重试...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"生成音频失败，已达到最大重试次数: {str(e)}")
                raise
                
        except Exception as e:
            logger.error(f"生成音频时发生未知错误: {str(e)}\n{traceback.format_exc()}")
            raise

@router.post("/batch")
async def generate_batch_speech(request: BatchTTSRequest):
    """生成批量语音文件"""
    temp_dir = None
    temp_audio_dir = None
    audio_files = []
    concat_list = None
    output_file = None
    
    try:
        logger.info(f"开始处理批量语音生成请求: {request}")
        
        # 获取默认语音
        voice = request.voice or settings.TTS_ENGINES[request.engine]["default_voice"]
        logger.debug(f"使用语音: {voice}")
        
        # 创建临时目录
        temp_dir = CACHE_DIR / "temp"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir(exist_ok=True)
        logger.debug(f"使用临时目录: {temp_dir}")
        
        # 使用年级和课时信息生成文件名
        filename_parts = []
        if request.grade:
            safe_grade = "".join(x for x in request.grade if x.isalnum())
            filename_parts.append(safe_grade)
        if request.lesson:
            safe_lesson = "".join(x for x in request.lesson if x.isalnum())
            filename_parts.append(safe_lesson)
            
        # 如果没有年级和课时信息，使用时间戳
        if not filename_parts:
            filename_parts.append(str(int(time.time())))
            
        output_file = temp_dir / f"{'_'.join(filename_parts)}.mp3"
        logger.debug(f"输出文件: {output_file}")
        
        # 创建临时目录用于存放单个音频文件
        temp_audio_dir = temp_dir / "audio"
        temp_audio_dir.mkdir(exist_ok=True)
        
        try:
            # 生成每个词语的音频文件
            logger.info(f"开始生成 {len(request.words)} 个词语的音频")
            for i, word in enumerate(request.words, 1):
                logger.debug(f"生成第 {i}/{len(request.words)} 个词语: {word}")
                word_file = temp_audio_dir / f"word_{i}.mp3"
                await generate_audio_with_retry(
                    word,
                    voice,
                    request.rate,
                    word_file
                )
                audio_files.append(word_file)
            
            # 创建合并列表文件
            logger.info("创建音频合并列表")
            concat_list = temp_audio_dir / "concat.txt"
            with open(concat_list, "w", encoding="utf-8") as f:
                def write_file_path(path: Path, repeat: int = 1):
                    # 写入指定次数的文件路径
                    return "".join([f"file '{str(path.absolute())}'\n" for _ in range(repeat)])
                
                # 添加开始提示音和停顿
                f.write(write_file_path(START_PROMPT_FILE))
                f.write(write_file_path(SILENCE_FILE, 3))  # 3秒停顿
                
                for word_file in audio_files:
                    # 每个词语重复指定次数
                    for _ in range(request.repeatCount):
                        f.write(write_file_path(word_file))
                        if _ < request.repeatCount - 1:
                            # 词语重复之间的停顿
                            f.write(write_file_path(SILENCE_FILE, int(request.repeatInterval)))
                    if word_file != audio_files[-1]:
                        # 词语之间的停顿
                        f.write(write_file_path(SILENCE_FILE, int(request.repeatInterval * 2)))
                
                # 添加结束提示音和停顿
                f.write(write_file_path(SILENCE_FILE, 2))  # 2秒停顿
                f.write(write_file_path(END_PROMPT_FILE))
            
            # 打印合并列表内容用于调试
            logger.debug("合并列表文件内容:")
            with open(concat_list, "r", encoding="utf-8") as f:
                logger.debug(f.read())
            
            # 合并音频文件
            logger.info("开始合并音频文件")
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_list),
                '-c', 'copy',
                str(output_file),
                '-y'
            ]
            logger.debug(f"执行命令: {' '.join(cmd)}")
            
            # 在 Windows 上，需要禁用控制台窗口
            if platform.system() == 'Windows':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                result = subprocess.run(cmd, capture_output=True, startupinfo=startupinfo)
            else:
                result = subprocess.run(cmd, capture_output=True)
                
            if result.returncode != 0:
                stderr = result.stderr.decode('utf-8', errors='ignore')
                error_msg = f"合并音频文件失败: {stderr}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # 检查输出文件是否存在且大小大于0
            if not output_file.exists() or output_file.stat().st_size == 0:
                error_msg = "合并音频文件失败: 输出文件不存在或为空"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            logger.info("音频文件合并成功")
            
            # 复制输出文件到 MP3 目录
            final_output = MP3_DIR / f"{'_'.join(filename_parts)}.mp3"
            shutil.copy2(output_file, final_output)
            
            # 检查最终文件是否存在且大小大于0
            if not final_output.exists() or final_output.stat().st_size == 0:
                error_msg = "复制音频文件失败: 目标文件不存在或为空"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            logger.info(f"已将音频文件复制到: {final_output} (大小: {final_output.stat().st_size} 字节)")
            
            logger.info("批量语音生成完成")
            return FileResponse(
                final_output,
                media_type="audio/mpeg",
                filename=f"{'_'.join(filename_parts)}_听写.mp3"
            )
            
        finally:
            # 清理临时音频文件
            logger.debug("清理临时文件")
            try:
                if temp_audio_dir and temp_audio_dir.exists():
                    shutil.rmtree(temp_audio_dir)
                if output_file and output_file.exists():
                    output_file.unlink()
            except Exception as e:
                logger.error(f"清理临时文件时出错: {str(e)}\n{traceback.format_exc()}")
            
    except Exception as e:
        error_msg = f"生成批量语音失败: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("")
async def generate_speech(request: TTSRequest):
    """生成语音"""
    try:
        # Web Speech API 在前端处理
        if request.engine == "web-speech":
            raise HTTPException(status_code=400, detail="Web Speech API 在前端处理")
            
        # 获取TTS服务
        tts_service = TTSFactory.get_tts_service(request.engine)
        if tts_service is None:
            raise HTTPException(status_code=400, detail="不支持的TTS引擎")
            
        # 获取默认语音
        voice = request.voice or settings.TTS_ENGINES[request.engine]["default_voice"]
        
        # 生成音频
        audio_data = await tts_service.generate_audio(
            request.text,
            voice=voice,
            rate=request.rate
        )
        
        if audio_data is None:
            raise HTTPException(status_code=500, detail="生成语音失败")
            
        # 返回音频流
        return StreamingResponse(
            iter([audio_data]),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f'attachment; filename="{hash(request.text)}.mp3"'
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/voices")
async def get_voices(engine: str = "edge-tts"):
    """获取可用的语音列表"""
    try:
        # Web Speech API 在前端处理
        if engine == "web-speech":
            return {
                "success": True,
                "data": []  # Web Speech API 的语音列表在前端获取
            }
            
        tts_service = TTSFactory.get_tts_service(engine)
        if tts_service is None:
            raise HTTPException(status_code=400, detail="不支持的TTS引擎")
            
        voices = await tts_service.get_available_voices()
        return {
            "success": True,
            "data": voices
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/config")
async def get_config():
    """获取听写配置"""
    try:
        return {
            "success": True,
            "data": {
                "showWord": settings.SHOW_WORD
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/check-cache")
async def check_cache(request: CheckCacheRequest):
    """检查并准备缓存"""
    try:
        tts = get_tts_service(request.engine)
        failed_words = []
        progress = 0
        total = len(request.words)
        
        async def generate_progress():
            nonlocal progress, failed_words
            
            # 使用批量生成方法，每批5个
            chunk_size = 5
            for i in range(0, total, chunk_size):
                chunk = request.words[i:i + chunk_size]
                
                # 处理当前批次
                results = await tts.generate_audio_batch(
                    texts=chunk,
                    voice=request.voice,
                    rate=request.rate,
                    chunk_size=chunk_size
                )
                
                # 更新进度
                for text, audio in results.items():
                    if audio is None:
                        failed_words.append(text)
                    else:
                        progress += 1
                
                # 返回当前进度
                progress_data = {
                    "progress": progress,
                    "total": total,
                    "ready": False
                }
                yield json.dumps(progress_data) + "\n"
            
            # 返回最终结果
            final_data = {
                "progress": progress,
                "total": total,
                "ready": len(failed_words) == 0,
                "failed_words": failed_words
            }
            yield json.dumps(final_data) + "\n"
        
        return StreamingResponse(
            generate_progress(),
            media_type="application/x-ndjson"
        )
        
    except Exception as e:
        logger.error(f"检查缓存失败: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

def get_tts_service(engine: str):
    """获取TTS服务实例"""
    # Web Speech API 在前端处理
    if engine == "web-speech":
        return None
        
    # 获取TTS服务
    tts_service = TTSFactory.get_tts_service(engine)
    if tts_service is None:
        raise HTTPException(status_code=400, detail="不支持的TTS引擎")
        
    return tts_service 
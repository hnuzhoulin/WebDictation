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

router = APIRouter(prefix="/api/tts", tags=["tts"])
settings = Settings()

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

@router.post("/batch")
async def generate_batch_speech(request: BatchTTSRequest):
    """生成批量语音文件"""
    try:
        # 获取TTS服务
        tts_service = TTSFactory.get_tts_service(request.engine)
        if tts_service is None:
            raise HTTPException(status_code=400, detail="不支持的TTS引擎")
            
        # 获取默认语音
        voice = request.voice or settings.TTS_ENGINES[request.engine]["default_voice"]
        
        # 创建临时文件
        temp_dir = Path(tempfile.gettempdir()) / "web_dictation_batch"
        temp_dir.mkdir(exist_ok=True)
        output_file = temp_dir / f"dictation_{hash(''.join(request.words))}.mp3"
        
        # 生成所有音频片段
        audio_segments = []
        for word in request.words:
            # 生成单个词语的音频
            audio_data = await tts_service.generate_audio(
                word,
                voice=voice,
                rate=request.rate
            )
            if audio_data is None:
                raise HTTPException(status_code=500, detail=f"生成音频失败: {word}")
                
            # 将音频数据保存为临时文件
            temp_file = temp_dir / f"{hash(word)}.mp3"
            temp_file.write_bytes(audio_data)
            
            # 添加到片段列表
            for _ in range(request.repeatCount):
                audio_segments.append(str(temp_file))
                # 添加间隔静音
                if request.repeatInterval > 0:
                    audio_segments.append(f"silence {request.repeatInterval} 1 0")
        
        # 使用 sox 合并音频（需要系统安装 sox）
        cmd = f'sox {" ".join(audio_segments)} "{output_file}"'
        result = os.system(cmd)
        if result != 0:
            raise HTTPException(status_code=500, detail="合并音频失败")
            
        # 返回文件
        return FileResponse(
            output_file,
            media_type="audio/mpeg",
            filename=f"dictation_{len(request.words)}words.mp3"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("")
async def generate_speech(request: TTSRequest):
    """生成语音"""
    try:
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
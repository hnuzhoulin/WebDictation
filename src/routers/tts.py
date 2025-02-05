from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List
from ..services.tts import get_tts_service
from ..config import settings

router = APIRouter(prefix="/api/tts")

class CheckCacheRequest(BaseModel):
    words: List[str]
    engine: str
    voice: str
    rate: float

class CheckCacheResponse(BaseModel):
    ready: bool
    failed_words: List[str]

@router.post("/check-cache", response_model=CheckCacheResponse)
async def check_cache(request: CheckCacheRequest):
    try:
        tts = get_tts_service(request.engine)
        failed_words = []
        
        for word in request.words:
            try:
                # 检查是否已有缓存
                cache_key = tts._get_cache_key(word, request.voice, request.rate)
                if not tts._is_cached(cache_key):
                    # 尝试生成缓存
                    await tts.generate_audio(word, request.voice, request.rate)
            except Exception as e:
                failed_words.append(word)
        
        return CheckCacheResponse(
            ready=len(failed_words) == 0,
            failed_words=failed_words
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 
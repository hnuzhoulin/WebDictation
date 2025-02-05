from pydantic_settings import BaseSettings
from typing import List, Dict
from pathlib import Path

class Settings(BaseSettings):
    # 服务器配置
    PORT: int = 8000
    MAX_CONCURRENCY: int = 3
    TIMEOUT: int = 300  # 5分钟超时
    CORS_ORIGINS: List[str] = ["*"]
    
    # TTS配置
    DEFAULT_ENGINE: str = "edge-tts"
    TTS_ENGINES: Dict = {
        "edge-tts": {
            "enabled": True,
            "default_voice": "zh-CN-XiaoxiaoNeural",
            "default_rate": 1.0
        },
        "web-speech": {
            "enabled": True,
            "default_voice": "Microsoft Huihui",
            "default_rate": 1.0
        }
    }
    
    # 文件配置
    WORDS_FILE: Path = Path("data/words.xlsx")
    
    class Config:
        env_file = ".env" 
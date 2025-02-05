from typing import Optional
from .tts.edge_tts import EdgeTTSService

class TTSFactory:
    _instances = {}
    
    @staticmethod
    def get_tts_service(engine: str) -> Optional[EdgeTTSService]:
        """
        获取TTS服务实例
        
        Args:
            engine: TTS引擎类型 ('edge-tts' 或 'web-speech')
            
        Returns:
            TTS服务实例
        
        Raises:
            ValueError: 当指定的引擎类型不支持时
        """
        if engine not in TTSFactory._instances:
            if engine == "edge-tts":
                TTSFactory._instances[engine] = EdgeTTSService()
            elif engine == "web-speech":
                # Web Speech API 在前端实现，后端不需要实例
                return None
            else:
                raise ValueError(f"不支持的TTS引擎类型: {engine}")
        
        return TTSFactory._instances[engine] 
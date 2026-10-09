"""OmniDrama ElevenLabs 顶级人类级情绪配音驱动 (SOTA Voice Acting Driver).

ElevenLabs 是全球公认最强的情感语音合成大模型，拥有真实的呼吸喘息、
轻蔑冷笑、愤怒咆哮、悲伤抽泣与微表情叹息，是好莱坞影视级声音标准。
"""
import os
import requests
from typing import Optional, Dict, Any


class ElevenLabsProvider:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY", "")
        self.base_url = "https://api.elevenlabs.io/v1"

    def synthesize_emotional_speech(
        self,
        text: str,
        voice_id: str,
        output_path: str,
        stability: float = 0.65,
        similarity_boost: float = 0.85,
        style: float = 0.45
    ) -> str:
        """调用 ElevenLabs Turbo v2.5 生成带有人类呼吸声与情绪波动的奥斯卡级配音."""
        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY is not configured.")

        url = f"{self.base_url}/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
                "style": style,
                "use_speaker_boost": True
            }
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=45)
        resp.raise_for_status()

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(resp.content)

        return output_path

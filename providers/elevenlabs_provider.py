"""OmniDrama ElevenLabs 顶级人类级情绪配音驱动 (SOTA Voice Acting Driver).

ElevenLabs 是全球公认最强的情感语音合成大模型，拥有真实的呼吸喘息、
轻蔑冷笑、愤怒咆哮、悲伤抽泣与微表情叹息，是好莱坞影视级声音标准。
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
import requests
from typing import Optional, Dict, Any

try:
    from core.runtime_context import get_provider_key
    from core.net_safety import DownloadSizeExceededError, MAX_AUDIO_BYTES
except ImportError:
    from omnidrama.core.runtime_context import get_provider_key
    from omnidrama.core.net_safety import DownloadSizeExceededError, MAX_AUDIO_BYTES


class ElevenLabsProvider:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = get_provider_key("ELEVENLABS_API_KEY", explicit=api_key)
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

        resp = requests.post(
            url, headers=headers, json=payload, timeout=45, stream=True, allow_redirects=False
        )
        try:
            resp.raise_for_status()
            out_p = Path(output_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(prefix=".el_tts_", dir=str(out_p.parent))
            tmp_p = Path(tmp_name)
            total = 0
            try:
                with os.fdopen(fd, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > MAX_AUDIO_BYTES:
                            raise DownloadSizeExceededError(f"ElevenLabs 音频体积超过上限 {MAX_AUDIO_BYTES} 字节")
                        f.write(chunk)
                os.replace(tmp_p, out_p)
            except Exception:
                tmp_p.unlink(missing_ok=True)
                raise
        finally:
            resp.close()

        return output_path

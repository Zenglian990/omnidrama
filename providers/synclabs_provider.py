"""OmniDrama SyncLabs 毫秒级神经对口型驱动 (SOTA Neural Lip-Sync Driver).

SyncLabs (Sync.so) 是全球公认最先进的音频驱动面部与口型重塑大模型，
具备真实牙齿、舌位生理运动对齐，彻底告别传统 2D 变形与模糊 Wav2Lip。
"""
from __future__ import annotations

import os
import time
import requests
from typing import Optional, Dict, Any

try:
    from core.runtime_context import get_provider_key
    from core.net_safety import MAX_VIDEO_BYTES, safe_download_to_file, validate_safe_public_https_url
except ImportError:
    from omnidrama.core.runtime_context import get_provider_key
    from omnidrama.core.net_safety import MAX_VIDEO_BYTES, safe_download_to_file, validate_safe_public_https_url


class SyncLabsProvider:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = get_provider_key("SYNCLABS_API_KEY", explicit=api_key)
        self.base_url = "https://api.synclabs.so"

    def submit_lipsync_job(
        self,
        video_url: str,
        audio_url: str,
        model: str = "sync-1.6.0",
        synergize: bool = True
    ) -> str:
        """向 SyncLabs 提交神经音画对口型任务."""
        if not self.api_key:
            raise ValueError("SYNCLABS_API_KEY is not configured.")
        safe_video_url = validate_safe_public_https_url(video_url)
        safe_audio_url = validate_safe_public_https_url(audio_url)

        url = f"{self.base_url}/lipsync"
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "videoUrl": safe_video_url,
            "audioUrl": safe_audio_url,
            "model": model,
            "synergize": synergize,
            "maxCredits": 50
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        job_id = data.get("id")
        return job_id

    def poll_and_download(self, job_id: str, output_path: str, max_wait_sec: int = 300) -> str:
        """轮询查询对口型渲染状态并下载合成后的视频."""
        url = f"{self.base_url}/lipsync/{job_id}"
        headers = {"x-api-key": self.api_key}

        start = time.time()
        while time.time() - start < max_wait_sec:
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status")
                if status == "COMPLETED":
                    video_url = data.get("url")
                    # 下载视频（带 SSRF 防护与体积上限）
                    safe_download_to_file(video_url, output_path, max_bytes=MAX_VIDEO_BYTES, timeout=90)
                    return output_path
                elif status in ("FAILED", "REJECTED"):
                    raise RuntimeError(f"SyncLabs job failed: {data.get('error')}")
            time.sleep(5)

        raise TimeoutError("SyncLabs lip-sync timed out.")

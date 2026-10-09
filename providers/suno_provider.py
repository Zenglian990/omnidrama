"""OmniDrama Suno v3.5 顶级影视交响配乐驱动 (SOTA Cinematic Music Driver).

Suno v3.5 是全球顶级 AI 音乐生成大模型，能够根据短剧剧本的情绪曲线，
自动生成好莱坞汉斯·季默风格的交响乐、紧张悬疑低音氛围 (Drone) 以及高潮战歌。
"""
import os
import time
import requests
from typing import Optional, Dict, Any, List


class SunoMusicProvider:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or os.environ.get("SUNO_API_KEY", "")
        self.base_url = base_url or os.environ.get("SUNO_BASE_URL", "https://api.sunoapi.net/api/v1")

    def generate_soundtrack(
        self,
        prompt: str,
        tags: str = "Cinematic Orchestral, Epic, Suspense, Hans Zimmer Style, 48kHz, Masterpiece",
        title: str = "OmniDrama Score",
        make_instrumental: bool = True,
        output_path: str = "bgm.mp3"
    ) -> str:
        """调用 Suno 大模型生成纯音乐电影级配乐."""
        if not self.api_key:
            raise ValueError("SUNO_API_KEY is not configured.")

        url = f"{self.base_url}/gateway/generate"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "prompt": prompt,
            "tags": tags,
            "title": title,
            "make_instrumental": make_instrumental,
            "mv": "chirp-v3-5"
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        task_id = data.get("task_id") or data.get("id")
        if not task_id:
            raise RuntimeError(f"Unexpected Suno response: {data}")

        # 轮询获取音频文件
        audio_url = self._poll_result(task_id)
        
        # 下载音频
        dl_resp = requests.get(audio_url, timeout=60)
        dl_resp.raise_for_status()
        
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(dl_resp.content)

        return output_path

    def _poll_result(self, task_id: str, max_wait_sec: int = 240) -> str:
        """轮询查询 Suno 配乐生成结果."""
        poll_url = f"{self.base_url}/gateway/feed/{task_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        start = time.time()
        while time.time() - start < max_wait_sec:
            resp = requests.get(poll_url, headers=headers, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                # 兼容不同包装格式
                items = data if isinstance(data, list) else data.get("data", [data])
                for item in items:
                    if item.get("status") in ("streaming", "complete", "SUCCESS"):
                        audio_url = item.get("audio_url")
                        if audio_url:
                            return audio_url
                    elif item.get("status") in ("error", "failed"):
                        raise RuntimeError(f"Suno generation failed: {item.get('error_message')}")
            time.sleep(5)

        raise TimeoutError("Suno music generation timed out.")

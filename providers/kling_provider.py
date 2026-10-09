"""OmniDrama 快手可灵 Kling 2.0 Pro 顶级动作与物理驱动 (SOTA Video Driver).

快手可灵 2.0 Pro 是目前国内短剧工业化制作的绝对霸主，擅长大肢体动作、
大幅度打斗对抗、物理碰撞及运镜轨迹控制 (Camera Controls)。
"""
import os
import time
import requests
from typing import Optional, Dict, Any


class KlingVideoProvider:
    def __init__(self, access_key: Optional[str] = None, secret_key: Optional[str] = None):
        self.access_key = access_key or os.environ.get("KLING_ACCESS_KEY", "")
        self.secret_key = secret_key or os.environ.get("KLING_SECRET_KEY", "")
        self.base_url = "https://api.klingai.com/v1"

    def create_image_to_video_task(
        self,
        image_base64: str,
        prompt: str,
        duration: int = 5,
        camera_type: str = "zoom_in",
        mode: str = "pro"
    ) -> str:
        """向可灵 2.0 Pro 发起专业级图生视频渲染任务."""
        if not self.access_key:
            raise ValueError("KLING_ACCESS_KEY is not configured.")

        url = f"{self.base_url}/videos/image2video"
        headers = {
            "Authorization": f"Bearer {self.access_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model_name": "kling-v2-pro",
            "image": image_base64,
            "prompt": prompt,
            "mode": mode,
            "duration": duration,
            "camera_control": {
                "type": camera_type
            }
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        task_id = data.get("data", {}).get("task_id")
        return task_id

    def poll_kling_task(self, task_id: str, max_wait_sec: int = 300) -> str:
        """轮询查询可灵任务完成状态并获取 MP4 下载链接."""
        url = f"{self.base_url}/videos/image2video/{task_id}"
        headers = {"Authorization": f"Bearer {self.access_key}"}

        start = time.time()
        while time.time() - start < max_wait_sec:
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                status = data.get("task_status")
                if status == "succeed":
                    video_url = data.get("task_result", {}).get("videos", [{}])[0].get("url")
                    return video_url
                elif status == "failed":
                    raise RuntimeError(f"Kling task failed: {data.get('task_status_msg')}")
            time.sleep(10)

        raise TimeoutError("Kling video generation timed out.")

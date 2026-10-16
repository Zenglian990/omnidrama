"""OmniDrama 快手可灵 Kling 2.0 Pro 顶级动作与物理驱动 (SOTA Video Driver).

快手可灵 2.0 Pro 是目前国内短剧工业化制作的绝对霸主，擅长大肢体动作、
大幅度打斗对抗、物理碰撞及运镜轨迹控制 (Camera Controls)。
"""
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests


class KlingVideoProvider:
    def __init__(self, access_key: Optional[str] = None, secret_key: Optional[str] = None):
        self.access_key = access_key or os.environ.get("KLING_ACCESS_KEY") or os.environ.get("KLING_API_KEY", "")
        self.secret_key = secret_key or os.environ.get("KLING_SECRET_KEY", "")
        self.base_url = os.environ.get("KLING_API_BASE_URL", "https://api.klingai.com/v1").rstrip("/")

    def create_image_to_video_task(
        self,
        image_base64: str,
        prompt: str,
        duration: int = 5,
        camera_type: str = "zoom_in",
        mode: str = "pro",
        job_path: Optional[str | Path] = None,
    ) -> str:
        """向可灵 2.0 Pro 发起专业级图生视频渲染任务 (支持 job_path 断点续传防重复扣费)."""
        if not self.access_key:
            raise ValueError("KLING_ACCESS_KEY is not configured.")

        if job_path:
            jp = Path(job_path)
            if jp.exists():
                try:
                    saved = json.loads(jp.read_text(encoding="utf-8"))
                    if saved.get("task_id") and saved.get("status") not in ("failed",):
                        return saved["task_id"]
                except Exception:
                    pass

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
        if job_path and task_id:
            jp = Path(job_path)
            jp.parent.mkdir(parents=True, exist_ok=True)
            jp.write_text(
                json.dumps({"provider": "kling_video", "task_id": task_id, "status": "submitted"}, indent=2),
                encoding="utf-8",
            )
        return task_id

    def poll_kling_task(
        self,
        task_id: str,
        max_wait_sec: int = 300,
        job_path: Optional[str | Path] = None,
    ) -> str:
        """轮询查询可灵任务完成状态并获取 MP4 下载链接."""
        url = f"{self.base_url}/videos/image2video/{task_id}"
        headers = {"Authorization": f"Bearer {self.access_key}"}

        start = time.time()
        while time.time() - start < max_wait_sec:
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                status = data.get("task_status")
                if job_path:
                    try:
                        Path(job_path).write_text(
                            json.dumps({"provider": "kling_video", "task_id": task_id, "status": status}, indent=2),
                            encoding="utf-8",
                        )
                    except Exception:
                        pass
                if status == "succeed":
                    video_url = data.get("task_result", {}).get("videos", [{}])[0].get("url")
                    return video_url
                elif status == "failed":
                    raise RuntimeError(f"Kling task failed: {data.get('task_status_msg')}")
            time.sleep(10)

        raise TimeoutError("Kling video generation timed out.")

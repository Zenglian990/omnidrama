"""OmniDrama MiniMax 海螺 Video-01 顶级视频驱动 (SOTA Video Driver).

MiniMax Video-01 是目前全球公认电影质感最强、人物面部微表情、毛孔与眼神光最为细腻的视频模型。
专用于生成主角情感爆发、面部特写与电影级视听镜头。
"""
import os
import time
import requests
from typing import Optional, Dict, Any


class MiniMaxHailuoProvider:
    def __init__(self, api_key: Optional[str] = None, group_id: Optional[str] = None):
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.group_id = group_id or os.environ.get("MINIMAX_GROUP_ID", "")
        self.base_url = "https://api.minimax.chat/v1"

    def submit_image_to_video(
        self,
        first_frame_url: str,
        prompt: str,
        model: str = "video-01"
    ) -> str:
        """向海螺视频大模型提交图生视频生成任务."""
        if not self.api_key:
            raise ValueError("MINIMAX_API_KEY is not configured.")

        url = f"{self.base_url}/video_generation"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "first_frame_image": first_frame_url,
            "prompt": prompt
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        task_id = data.get("task_id")
        return task_id

    def poll_video_result(self, task_id: str, max_wait_sec: int = 300) -> str:
        """轮询查询海螺视频生成结果并获取最终高清 MP4 下载链接."""
        url = f"{self.base_url}/query/video_generation?task_id={task_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        start_time = time.time()
        while time.time() - start_time < max_wait_sec:
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status")
                if status == "Success":
                    file_id = data.get("file_id")
                    # 获取文件下载地址
                    download_url = f"{self.base_url}/files/retrieve?file_id={file_id}"
                    return download_url
                elif status == "Fail":
                    raise RuntimeError(f"MiniMax video generation failed: {data.get('message')}")
            time.sleep(10)

        raise TimeoutError("MiniMax video generation timed out.")

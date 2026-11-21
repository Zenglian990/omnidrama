"""OmniDrama FLUX.1 Pro 顶级电影级定妆与分镜生图驱动 (SOTA Image Generation Driver).

FLUX.1 Pro (由 Black Forest Labs 出品) 是目前全球摄影级质感最强、人体结构最准确、
材质光影与多角色特征还原最极致的文生图大模型，代表当今商业影视原画的工业巅峰。
"""
from __future__ import annotations

import os
import time
import requests
from typing import Optional, Dict, Any

try:
    from core.runtime_context import get_provider_key
    from core.net_safety import MAX_IMAGE_BYTES, safe_download_to_file, validate_safe_public_https_url
except ImportError:
    from omnidrama.core.runtime_context import get_provider_key
    from omnidrama.core.net_safety import MAX_IMAGE_BYTES, safe_download_to_file, validate_safe_public_https_url


class FluxProProvider:
    def __init__(self, api_key: Optional[str] = None, api_endpoint: Optional[str] = None):
        self.api_key = (
            get_provider_key("BFL_API_KEY", explicit=api_key)
            or get_provider_key("FLUX_API_KEY", explicit=api_key)
        )
        self.base_url = (api_endpoint or "https://api.bfl.ml/v1").rstrip("/")

    def generate_cinematic_frame(
        self,
        prompt: str,
        aspect_ratio: str = "9:16",
        output_path: str = "shot.png",
        raw: bool = True,
        safety_tolerance: int = 5,
        prompt_upsampling: bool = True
    ) -> str:
        """调用 FLUX.1 Pro 生成顶级胶片质感分镜剧照."""
        if not self.api_key:
            raise ValueError("BFL_API_KEY / FLUX_API_KEY is not configured.")
        validate_safe_public_https_url(self.base_url)

        url = f"{self.base_url}/flux-pro-1.1"
        headers = {
            "x-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        # 构图比例映射
        payload = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "raw": raw,
            "safety_tolerance": safety_tolerance,
            "prompt_upsampling": prompt_upsampling
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        task_id = data.get("id")
        if not task_id:
            raise RuntimeError(f"Unexpected BFL API response: {data}")

        # 轮询获取结果
        image_url = self._poll_result(task_id)
        
        # 下载图片保存到本地（带 SSRF 防护与体积上限）
        safe_download_to_file(image_url, output_path, max_bytes=MAX_IMAGE_BYTES, timeout=60)

        return output_path

    def _poll_result(self, task_id: str, max_wait_sec: int = 180) -> str:
        """轮询查询 BFL 渲染结果."""
        poll_url = f"{self.base_url}/get_result?id={task_id}"
        headers = {"x-key": self.api_key}

        start = time.time()
        while time.time() - start < max_wait_sec:
            resp = requests.get(poll_url, headers=headers, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status")
                if status == "Ready":
                    return data.get("result", {}).get("sample")
                elif status in ("Failed", "Error"):
                    raise RuntimeError(f"FLUX generation failed: {data}")
            time.sleep(3)

        raise TimeoutError("FLUX.1 Pro generation timed out.")

"""OmniDrama 字节跳动火山方舟 Seedance 2.0 / 2.5 视频生成直连适配器 (Volcengine Ark Seedance Provider).

净室吸收自 OpenMontage 的 seedance_ark 架构规范：
1. 直连火山方舟官方 REST API (https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks)，无需第三方中转。
2. 支持 doubao-seedance-2-0-260128 (Standard)、doubao-seedance-2-5-260628 (2.5) 等模型家族。
3. 支持文生视频 (text_to_video) 与首帧定妆照驱动视频 (image_to_video，支持本地图片自动编码为 Data URI)。
4. 内置 resume_job (job_path) 断点续传机制：任务创建后立即将 task_id 落盘到 shot_xxx_seedance_job.json；
   若轮询超时或进程重启，自动读取已有 task_id 恢复轮询，100% 杜绝重复扣费。
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests


class VolcengineSeedanceProvider:
    BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
    MODEL_IDS = {
        "2.5": "doubao-seedance-2-5-260628",
        "standard": "doubao-seedance-2-0-260128",
        "fast": "doubao-seedance-2-0-fast-260128",
        "mini": "doubao-seedance-2-0-mini-260615",
    }

    def __init__(self, api_key: Optional[str] = None, model_variant: str = "standard") -> None:
        raw_key = api_key or os.environ.get("ARK_API_KEY", "")
        if raw_key.lower().startswith("bearer "):
            raw_key = raw_key[7:].strip()
        self.api_key = raw_key.strip()
        self.base_url = os.environ.get("ARK_BASE_URL", self.BASE_URL).rstrip("/")
        self.model = os.environ.get("ARK_SEEDANCE_MODEL") or self.MODEL_IDS.get(model_variant, self.MODEL_IDS["standard"])

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    @staticmethod
    def encode_local_image_data_uri(image_path: str | Path) -> str:
        p = Path(image_path)
        if not p.exists():
            raise FileNotFoundError(f"Reference image not found: {p}")
        mime, _ = mimetypes.guess_type(str(p))
        mime = mime or "image/jpeg"
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{b64}"

    def _headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise ValueError("ARK_API_KEY is not configured.")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def create_generation_task(
        self,
        prompt: str,
        first_frame_image: Optional[str | Path] = None,
        aspect_ratio: str = "9:16",
        resolution: str = "720p",
        duration: int = 5,
        generate_audio: bool = True,
        job_path: Optional[str | Path] = None,
    ) -> str:
        """创建火山方舟 Seedance 视频生成任务（若 job_path 中已有未终结或已成功的 task_id，直接复用不重复扣费）."""
        if job_path:
            jp = Path(job_path)
            if jp.exists():
                try:
                    saved = json.loads(jp.read_text(encoding="utf-8"))
                    saved_id = saved.get("task_id", "")
                    saved_status = saved.get("status", "")
                    if saved_id and saved_status not in ("failed", "cancelled", "expired"):
                        return saved_id
                except Exception:
                    pass

        content_items = []
        if first_frame_image:
            img_str = str(first_frame_image)
            if not img_str.startswith(("http://", "https://", "data:")):
                img_str = self.encode_local_image_data_uri(img_str)
            content_items.append({
                "type": "image_url",
                "image_url": {"url": img_str},
                "role": "first_frame",
            })

        # Seedance 参数以文本控制指令或字段传递
        full_prompt = f"{prompt.strip()} --ratio {aspect_ratio} --rs {resolution} --dur {duration}"
        content_items.append({
            "type": "text",
            "text": full_prompt,
        })

        payload: Dict[str, Any] = {
            "model": self.model,
            "content": content_items,
        }
        if generate_audio:
            payload["generate_audio"] = True

        url = f"{self.base_url}/contents/generations/tasks"
        resp = requests.post(url, headers=self._headers(), json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        task_id = data.get("id") or data.get("data", {}).get("id")
        if not task_id:
            raise RuntimeError(f"Seedance task creation returned no id: {data}")

        if job_path:
            jp = Path(job_path)
            jp.parent.mkdir(parents=True, exist_ok=True)
            jp.write_text(
                json.dumps(
                    {
                        "provider": "volcengine_seedance",
                        "model": self.model,
                        "task_id": task_id,
                        "status": "queued",
                        "prompt": prompt,
                        "created_at": time.time(),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        return task_id

    def poll_and_download(
        self,
        task_id: str,
        output_path: str | Path,
        job_path: Optional[str | Path] = None,
        max_wait_sec: int = 180,
        poll_interval: float = 4.0,
    ) -> str:
        """轮询 Seedance 异步任务并下载 MP4 成片到本地，同步更新 job_path 状态."""
        url = f"{self.base_url}/contents/generations/tasks/{task_id}"
        start = time.time()
        video_url = ""

        while time.time() - start < max_wait_sec:
            resp = requests.get(url, headers=self._headers(), timeout=20)
            resp.raise_for_status()
            data = resp.json()
            status = (data.get("status") or data.get("data", {}).get("status") or "").lower()

            if job_path:
                try:
                    jp = Path(job_path)
                    saved = json.loads(jp.read_text(encoding="utf-8")) if jp.exists() else {}
                    saved["task_id"] = task_id
                    saved["status"] = status
                    jp.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
                except Exception:
                    pass

            if status == "succeeded":
                content_obj = data.get("content") or data.get("data", {}).get("content") or {}
                video_url = content_obj.get("video_url") or data.get("video_url") or ""
                break
            if status in ("failed", "cancelled", "expired"):
                err = data.get("error") or data.get("message") or status
                raise RuntimeError(f"Seedance task {task_id} ended with {status}: {err}")

            time.sleep(poll_interval)

        if not video_url:
            raise TimeoutError(f"Seedance task {task_id} timed out after {max_wait_sec}s (resume_job saved).")

        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        dl = requests.get(video_url, timeout=60)
        dl.raise_for_status()
        out_p.write_bytes(dl.content)
        return str(out_p)

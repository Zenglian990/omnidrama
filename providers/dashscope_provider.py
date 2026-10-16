"""OmniDrama 阿里云百炼 DashScope 全模态直连适配器 (通义万相 Qwen-Image 2.0 + Qwen3-TTS/CosyVoice).

净室吸收自 OpenMontage 的 DashScope 规范：
1. 使用 DASHSCOPE_API_KEY 直连阿里云百炼原生接口 (https://dashscope.aliyuncs.com/api/v1/...)。
2. 图像生成 (generate_shot_image)：原生支持中文古风、修仙、都市豪门、战神题材 9:16 竖屏高清出图，
   支持 seed 锁脸与 job_path 异步任务断点恢复。
3. 语音合成 (synthesize_speech)：支持根据角色性别/年龄自动匹配中文戏剧音色。
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests


class DashScopeProvider:
    BASE_URL = "https://dashscope.aliyuncs.com/api/v1"

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = (api_key or os.environ.get("DASHSCOPE_API_KEY", "")).strip()

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    def _headers(self, async_task: bool = False) -> Dict[str, str]:
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY is not configured.")
        h = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if async_task:
            h["X-DashScope-Async"] = "enable"
        return h

    @staticmethod
    def resolve_voice(speaker: str) -> str:
        s = (speaker or "").strip()
        if any(w in s for w in ["女", "姐", "妹", "雪", "婉", "清", "瑶", "妃", "妈", "母", "夫人", "千金"]):
            return "Cherry"
        if any(w in s for w in ["老", "爷", "长老", "太上", "宗主", "家主", "旁白"]):
            return "Ethan"
        return "Chelsie"

    def generate_shot_image(
        self,
        prompt: str,
        output_path: str | Path,
        size: str = "720*1280",
        seed: Optional[int] = None,
        model: str = "wanx2.1-t2i-turbo",
        job_path: Optional[str | Path] = None,
        max_wait_sec: int = 90,
    ) -> str:
        """调用阿里云百炼通义万相/Qwen-Image 异步生图接口并下载 9:16 竖屏图片 (含 job_path 断点续传)."""
        task_id = ""
        if job_path:
            jp = Path(job_path)
            if jp.exists():
                try:
                    saved = json.loads(jp.read_text(encoding="utf-8"))
                    if saved.get("status") not in ("FAILED", "CANCELED", "UNKNOWN"):
                        task_id = saved.get("task_id", "")
                except Exception:
                    task_id = ""

        if not task_id:
            url = f"{self.BASE_URL}/services/aigc/text2image/image-synthesis"
            params: Dict[str, Any] = {"size": size, "n": 1}
            if seed is not None and seed >= 0:
                params["seed"] = int(seed) % 2147483647
            payload = {
                "model": model,
                "input": {"prompt": prompt[:800]},
                "parameters": params,
            }
            resp = requests.post(url, headers=self._headers(async_task=True), json=payload, timeout=25)
            resp.raise_for_status()
            data = resp.json()
            task_id = data.get("output", {}).get("task_id", "")
            if not task_id:
                raise RuntimeError(f"DashScope image task creation returned no task_id: {data}")
            if job_path:
                jp = Path(job_path)
                jp.parent.mkdir(parents=True, exist_ok=True)
                jp.write_text(
                    json.dumps({"provider": "dashscope_image", "task_id": task_id, "status": "PENDING"}, indent=2),
                    encoding="utf-8",
                )

        # Poll task status
        poll_url = f"{self.BASE_URL}/tasks/{task_id}"
        start = time.time()
        img_url = ""
        while time.time() - start < max_wait_sec:
            r = requests.get(poll_url, headers=self._headers(async_task=False), timeout=15)
            r.raise_for_status()
            out = r.json().get("output", {})
            st = out.get("task_status", "")
            if job_path:
                try:
                    Path(job_path).write_text(
                        json.dumps({"provider": "dashscope_image", "task_id": task_id, "status": st}, indent=2),
                        encoding="utf-8",
                    )
                except Exception:
                    pass
            if st == "SUCCEEDED":
                results = out.get("results", [])
                if results and results[0].get("url"):
                    img_url = results[0]["url"]
                    break
            elif st in ("FAILED", "CANCELED", "UNKNOWN"):
                raise RuntimeError(f"DashScope image task {task_id} failed: {out.get('message', st)}")
            time.sleep(2.5)

        if not img_url:
            raise TimeoutError(f"DashScope image task {task_id} timed out.")

        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        dl = requests.get(img_url, timeout=45)
        dl.raise_for_status()
        out_p.write_bytes(dl.content)
        return str(out_p)

    def synthesize_speech(
        self,
        text: str,
        output_path: str | Path,
        speaker: str = "旁白",
        model: str = "qwen3-tts-flash",
    ) -> str:
        """调用阿里云百炼 Qwen3-TTS 接口生成角色配音音频."""
        url = f"{self.BASE_URL}/services/aigc/multimodal-generation/generation"
        voice = self.resolve_voice(speaker)
        payload = {
            "model": model,
            "input": {
                "text": text,
                "voice": voice,
            },
        }
        resp = requests.post(url, headers=self._headers(async_task=False), json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        audio_url = data.get("output", {}).get("audio", {}).get("url", "")
        if not audio_url:
            raise RuntimeError(f"DashScope TTS returned no audio URL: {data}")
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        dl = requests.get(audio_url, timeout=30)
        dl.raise_for_status()
        out_p.write_bytes(dl.content)
        return str(out_p)

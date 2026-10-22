"""OmniDrama 硅基流动 (SiliconFlow) 国内零门槛全能引擎驱动.

支持国内手机号直接注册，无需绑定海外信用卡：
1. 免费/高速文生图：支持 `black-forest-labs/FLUX.1-schnell` (免费) 与 `Kwai-Kolors/Kolors` (可图免费) 实时生成每镜独立分镜画面。
2. 剧本拆解大模型：支持 `deepseek-ai/DeepSeek-V3` 及免费模型 `Qwen/Qwen2.5-7B-Instruct`。
"""
from __future__ import annotations

import os
import base64
import requests
from typing import Optional


class SiliconFlowProvider:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = (api_key or os.environ.get("SILICONFLOW_API_KEY", "")).strip()
        self.base_url = "https://api.siliconflow.cn/v1"

    def generate_shot_image(
        self,
        prompt: str,
        output_path: str,
        model: str = "black-forest-labs/FLUX.1-schnell",
        image_size: str = "768x1024",
        seed: Optional[int] = None
    ) -> str:
        """调用硅基流动 FLUX.1-schnell (或 Kolors) 实时生成 9:16 竖屏分镜原画 (支持固定 seed 锁定画风与人物特征)."""
        if not self.api_key:
            raise ValueError("SILICONFLOW_API_KEY 未配置")

        url = f"{self.base_url}/images/generations"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        models_to_try = [model, "Kwai-Kolors/Kolors"]
        last_err = None

        for m in models_to_try:
            payload = {
                "model": m,
                "prompt": prompt,
                "image_size": image_size,
                "num_inference_steps": 20 if "Kolors" in m else 4
            }
            if seed is not None:
                payload["seed"] = abs(int(seed)) % 2147483647
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=45)
                if resp.status_code != 200:
                    last_err = f"HTTP {resp.status_code}: {resp.text[:120]}"
                    continue
                data = resp.json()
                images = data.get("images") or data.get("data") or []
                if not images:
                    last_err = f"Empty images list: {data}"
                    continue

                first_item = images[0]
                img_url = first_item.get("url")
                b64_data = first_item.get("b64_json")

                os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                if img_url:
                    img_resp = requests.get(img_url, timeout=45)
                    img_resp.raise_for_status()
                    with open(output_path, "wb") as f:
                        f.write(img_resp.content)
                    return output_path
                elif b64_data:
                    with open(output_path, "wb") as f:
                        f.write(base64.b64decode(b64_data))
                    return output_path
            except Exception as e:
                last_err = str(e)

        raise RuntimeError(f"SiliconFlow 生图失败: {last_err}")

    @staticmethod
    def resolve_cosyvoice(speaker: str) -> str:
        """根据角色名/性别自动匹配 CosyVoice2-0.5B 男女与年龄段音色."""
        spk = (speaker or "旁白").strip()
        if any(w in spk for w in ["女", "母", "柳", "妻", "姐", "妹", "妈", "雪", "妃", "婉", "瑶", "晴", "涵", "小姐"]):
            if any(w in spk for w in ["母", "妈", "太", "婆"]):
                return "FunAudioLLM/CosyVoice2-0.5B:claire"
            return "FunAudioLLM/CosyVoice2-0.5B:anna"
        if any(w in spk for w in ["老", "爷", "宗主", "师父", "长者", "太上", "家主"]):
            return "FunAudioLLM/CosyVoice2-0.5B:charles"
        if any(w in spk for w in ["赵", "少", "反派", "恶", "霸", "公子"]):
            return "FunAudioLLM/CosyVoice2-0.5B:david"
        if spk == "旁白":
            return "FunAudioLLM/CosyVoice2-0.5B:benjamin"
        return "FunAudioLLM/CosyVoice2-0.5B:alex"

    def synthesize_speech(
        self,
        text: str,
        speaker: str,
        output_path: str
    ) -> str:
        """调用硅基流动 CosyVoice2-0.5B 合成多角色情感语音 MP3."""
        if not self.api_key:
            raise ValueError("SILICONFLOW_API_KEY 未配置")

        url = f"{self.base_url}/audio/speech"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "FunAudioLLM/CosyVoice2-0.5B",
            "input": text,
            "voice": self.resolve_cosyvoice(speaker),
            "response_format": "mp3"
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=35)
        resp.raise_for_status()
        if len(resp.content) < 200:
            raise RuntimeError("SiliconFlow TTS returned empty audio")
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(resp.content)
        return output_path

    def chat_completion(self, system_prompt: str, user_prompt: str) -> tuple[str, str]:
        """调用硅基流动 LLM 接口（优先 DeepSeek-V3，若余额不足自动无缝降级至免费的 Qwen2.5-7B-Instruct）."""
        if not self.api_key:
            raise ValueError("SILICONFLOW_API_KEY 未配置")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        models_to_try = [
            ("deepseek-ai/DeepSeek-V3", "SiliconFlow DeepSeek-V3"),
            ("Qwen/Qwen2.5-7B-Instruct", "SiliconFlow Qwen2.5-7B (免费)"),
        ]
        last_err = None

        for model_id, display_name in models_to_try:
            payload = {
                "model": model_id,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 4000
            }
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=50)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    return content, display_name
                else:
                    last_err = f"HTTP {resp.status_code}: {resp.text[:100]}"
            except Exception as e:
                last_err = str(e)

        raise RuntimeError(f"SiliconFlow LLM 调用失败: {last_err}")

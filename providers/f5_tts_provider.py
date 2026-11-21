"""OmniDrama F5-TTS 专属云端神经角色声音克隆驱动器 (F5-TTS Voice Provider).

通过 Hugging Face ZeroGPU 提供的 A10G 免费算力（zenglian110110/f5-tts-studio），
为短剧男女主角实现零样本 (Zero-Shot) 极速音色克隆与电影级戏剧张力情感配音。
支持男主霸总、女主清澈等角色原声锚点，具备自动重试与离线降级能力。
"""
from __future__ import annotations


import os
import shutil
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

DEFAULT_SPACE_URL = "https://zenglian110110-f5-tts-studio.hf.space"

def _get_hf_token() -> str:
    try:
        from core.runtime_context import get_provider_key
    except ImportError:
        from omnidrama.core.runtime_context import get_provider_key
    token = get_provider_key("HF_TOKEN")
    if not token:
        try:
            token_path = Path.home() / ".huggingface" / "token"
            if token_path.exists():
                token = token_path.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return token


class F5TTSProvider:
    def __init__(
        self,
        space_url: Optional[str] = None,
        token: Optional[str] = None,
        enabled: bool = True
    ):
        self.space_url = space_url or os.environ.get("F5_TTS_SPACE_URL", DEFAULT_SPACE_URL)
        self._explicit_token = token
        self.enabled = enabled
        self._client = None

        # 角色声音锚点库路径
        base_dir = Path(__file__).resolve().parent.parent
        self.voices_dir = base_dir / "assets" / "character_voices"
        
        # 预置主角原声样本及对应台词
        self.character_anchors: Dict[str, Tuple[str, str]] = {
            "男主角": (
                str(self.voices_dir / "male_boss.mp3"),
                "OmniDrama 灵眸漫剧，开启全新短剧视听体验。"
            ),
            "女主角": (
                str(self.voices_dir / "female_lead.mp3"),
                "OmniDrama 灵眸漫剧，开启全新短剧视听体验。"
            ),
            "霸总": (
                str(self.voices_dir / "male_boss.mp3"),
                "OmniDrama 灵眸漫剧，开启全新短剧视听体验。"
            ),
            "大女主": (
                str(self.voices_dir / "female_lead.mp3"),
                "OmniDrama 灵眸漫剧，开启全新短剧视听体验。"
            ),
        }

    @property
    def token(self) -> str:
        """运行时动态读取 HF_TOKEN（避免导入期固化或跨请求污染）."""
        if self._explicit_token and str(self._explicit_token).strip():
            return str(self._explicit_token).strip()
        return _get_hf_token()

    @token.setter
    def token(self, value: Optional[str]) -> None:
        self._explicit_token = value

    @property
    def client(self):
        """懒加载 Gradio Client 连接（强制启用默认 TLS 证书校验，绝不探测代理并污染全局环境变量）."""
        if self._client is None and self.enabled:
            try:
                from gradio_client import Client
                tok = self.token or None
                self._client = Client(self.space_url, token=tok)
                logger.info(f"[F5-TTS] 成功连接云端声音克隆空间: {self.space_url}")
            except Exception as e:
                logger.warning(f"[F5-TTS] 连接云端配音空间异常: {e}")
                self._client = None
        return self._client

    def is_available(self) -> bool:
        """检查 F5-TTS 空间是否可用."""
        if not self.enabled:
            return False
        try:
            return self.client is not None
        except Exception:
            return False

    def synthesize_character_voice(
        self,
        text: str,
        role: str = "男主角",
        output_path: str = "output_voice.mp3",
        custom_ref_audio: Optional[str] = None,
        custom_ref_text: Optional[str] = None
    ) -> Optional[str]:
        """使用云端 A10G 显卡进行神经声音克隆并合成角色台词.

        Args:
            text: 需要配音的目标短剧台词
            role: 角色名称 ("男主角", "女主角", "反派" 等)
            output_path: 输出音频路径 (.mp3 / .wav)
            custom_ref_audio: 自定义音色参考音频
            custom_ref_text: 参考音频中的文本台词

        Returns:
            合成成功的音频文件绝对路径，失败返回 None
        """
        if not self.enabled:
            logger.info("[F5-TTS] 服务未启用，跳过云端配音")
            return None

        if not text.strip():
            logger.warning("[F5-TTS] 待合成文本为空")
            return None

        # 确定音色参考样本
        ref_audio = custom_ref_audio
        ref_text = custom_ref_text

        if not ref_audio or not os.path.exists(ref_audio):
            # 智能匹配角色原声
            matched_role = "男主角"
            if any(w in role for w in ["女", "妻", "妹", "小姐", "妈"]):
                matched_role = "女主角"
            
            anchor = self.character_anchors.get(matched_role, self.character_anchors["男主角"])
            ref_audio, ref_text = anchor[0], anchor[1]

        if not os.path.exists(ref_audio):
            logger.warning(f"[F5-TTS] 角色音色原声文件缺失: {ref_audio}")
            return None

        try:
            from gradio_client import handle_file

            cli = self.client
            if cli is None:
                logger.warning("[F5-TTS] 客户端未就绪，使用离线降级")
                return None

            logger.info(f"[F5-TTS] 正在请求 A10G 神经声音克隆 (角色: {role}, 台词: {text[:20]}...)...")

            # 调用 F5-TTS 专属云端 API: /predict
            # 参数: ref_audio, ref_text, gen_text, remove_silence
            generated_audio = cli.predict(
                handle_file(ref_audio),
                ref_text or "",
                text,
                False,  # remove_silence
                api_name="/predict"
            )

            if generated_audio and os.path.exists(generated_audio):
                os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                shutil.copy2(generated_audio, output_path)
                logger.info(f"[F5-TTS] 配音合成成功，已保存至: {output_path}")
                return output_path
            else:
                logger.warning(f"[F5-TTS] 云端返回文件异常: {generated_audio}")
                return None

        except Exception as e:
            logger.warning(f"[F5-TTS] 调用云端 A10G 配音异常，触发安全降级: {e}")
            return None

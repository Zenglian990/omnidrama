"""OmniDrama LivePortrait 专属云端神经动效驱动器 (LivePortrait Provider).

通过 Hugging Face ZeroGPU 提供的 A10G 免费算力（zenglian110110/liveportrait-studio），
为短剧角色定妆照注入电影级眼神流转、眨眼、挑眉与自然对白微动作。
具备自动降级与重试机制，若云端无网络或排队，优雅回退至本地离线渲染引擎。
"""
from __future__ import annotations


import os
import shutil
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

DEFAULT_SPACE_URL = "https://zenglian110110-liveportrait-studio.hf.space"

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


class LivePortraitProvider:
    def __init__(
        self,
        space_url: Optional[str] = None,
        token: Optional[str] = None,
        enabled: bool = True
    ):
        self.space_url = space_url or os.environ.get("LIVEPORTRAIT_SPACE_URL", DEFAULT_SPACE_URL)
        self._explicit_token = token
        self.enabled = enabled
        self._client = None

        # 内置动作资产路径
        base_dir = Path(__file__).resolve().parent.parent
        self.assets_dir = base_dir / "assets" / "driving_motions"
        self.motion_talking = str(self.assets_dir / "d6.mp4")
        self.motion_acting = str(self.assets_dir / "d0.mp4")

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
                logger.info(f"[LivePortrait] 成功建立与云端空间连接: {self.space_url}")
            except Exception as e:
                logger.warning(f"[LivePortrait] 连接云端空间异常: {e}")
                self._client = None
        return self._client

    def is_available(self) -> bool:
        """检查云端 A10G 空间是否可用."""
        if not self.enabled:
            return False
        try:
            return self.client is not None
        except Exception:
            return False

    def animate_character(
        self,
        image_path: str,
        output_path: str,
        motion_type: str = "talking",
        driving_video_path: Optional[str] = None
    ) -> Optional[str]:
        """将角色静态图转换为高质感动态表情视频.

        Args:
            image_path: 角色正面清晰肖像图片路径
            output_path: 输出视频 mp4 路径
            motion_type: 动作类型 ("talking" 对白微动 / "acting" 眼神流转微晃)
            driving_video_path: 自定义驱动动作视频，若不提供则使用预置最佳资产

        Returns:
            生成的 mp4 路径，失败返回 None（触发上层优雅降级）
        """
        if not self.enabled:
            logger.info("[LivePortrait] 服务未启用，跳过云端渲染")
            return None

        if not os.path.exists(image_path):
            logger.error(f"[LivePortrait] 角色图片不存在: {image_path}")
            return None

        # 确定驱动视频
        motion_file = driving_video_path
        if not motion_file or not os.path.exists(motion_file):
            motion_file = self.motion_talking if motion_type == "talking" else self.motion_acting

        if not os.path.exists(motion_file):
            logger.warning(f"[LivePortrait] 驱动视频模板缺失: {motion_file}")
            return None

        try:
            from gradio_client import handle_file

            cli = self.client
            if cli is None:
                logger.warning("[LivePortrait] 客户端未就绪，使用离线降级")
                return None

            logger.info(f"[LivePortrait] 正在请求 A10G 神经渲染 (图片: {Path(image_path).name}, 模板: {Path(motion_file).name})...")

            # 调用 LivePortrait 专属云端 API
            # 参数: param_0=Image, param_1={"video": Video}, param_2=True, param_3=True, param_4=True
            res = cli.predict(
                handle_file(image_path),
                {"video": handle_file(motion_file)},
                True,  # 相对动态映射 (relative motion)
                True,  # 头部自适应裁剪 (do_crop)
                True,  # 智能贴回高清基底 (pasteback)
                api_name="/gpu_wrapped_execute_video"
            )

            # 解析返回结果: res 是元组 (out_video_dict, extra_video_dict)
            video_dict = res[0] if isinstance(res, (tuple, list)) else res
            generated_video = video_dict.get("video") if isinstance(video_dict, dict) else str(video_dict)

            if generated_video and os.path.exists(generated_video):
                os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                shutil.copy2(generated_video, output_path)
                logger.info(f"[LivePortrait] 渲染成功，已保存至: {output_path}")
                return output_path
            else:
                logger.warning(f"[LivePortrait] 云端返回文件异常: {generated_video}")
                return None

        except Exception as e:
            logger.warning(f"[LivePortrait] 调用云端 A10G 异常，安全降级回本地: {e}")
            return None

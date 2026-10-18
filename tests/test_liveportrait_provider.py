"""OmniDrama LivePortrait Provider 与 TTS 角色配音联合单元测试 (Unit Tests)."""
import os
import sys
import unittest
from pathlib import Path

# 添加 omnidrama 路径
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from providers.liveportrait_provider import LivePortraitProvider
from core.compositor import VideoCompositor
from core.tts_engine import TTSEngine


class TestLivePortraitProvider(unittest.TestCase):
    def setUp(self):
        self.provider = LivePortraitProvider(enabled=True)
        self.compositor = VideoCompositor()
        self.tts = TTSEngine()

    def test_provider_initialization(self):
        """测试 LivePortrait Provider 初始化参数与空间绑定."""
        self.assertIn("liveportrait-studio", self.provider.space_url)
        self.assertIsNotNone(self.provider.token)
        self.assertTrue(self.provider.enabled)

    def test_driving_assets_exist(self):
        """测试预置的动作驱动视频模板完整性."""
        self.assertTrue(os.path.exists(self.provider.motion_talking), f"Missing: {self.provider.motion_talking}")
        self.assertTrue(os.path.exists(self.provider.motion_acting), f"Missing: {self.provider.motion_acting}")
        # 验证文件大小大于 1MB (真实视频而非 LFS 文本指针)
        self.assertGreater(os.path.getsize(self.provider.motion_talking), 1024 * 1024)
        self.assertGreater(os.path.getsize(self.provider.motion_acting), 1024 * 1024)

    def test_missing_image_graceful_fallback(self):
        """测试图片不存在时的安全降级拦截 (返回 None，不崩溃)."""
        res = self.provider.animate_character("non_existent_image.jpg", "out.mp4")
        self.assertIsNone(res)

    def test_disabled_mode(self):
        """测试禁用状态下的即时返回."""
        prov = LivePortraitProvider(enabled=False)
        self.assertFalse(prov.is_available())
        res = prov.animate_character("any.jpg", "out.mp4")
        self.assertIsNone(res)

    def test_voices_matrix_resolution(self):
        """测试所有核心短剧角色的声音矩阵解析."""
        roles = ["男主角", "女主角", "反派男配", "少女/妹妹", "成熟大叔", "旁白"]
        for role in roles:
            voice_id, rate, pitch = self.tts.resolve_voice(role)
            self.assertTrue(voice_id.startswith("zh-CN-"), f"Invalid voice for {role}: {voice_id}")
            self.assertIsNotNone(rate)
            self.assertIsNotNone(pitch)

    def test_compositor_neural_shot_interface(self):
        """测试 VideoCompositor 的 render_neural_shot 接口存在性."""
        self.assertTrue(hasattr(self.compositor, "render_neural_shot"))


if __name__ == "__main__":
    unittest.main()

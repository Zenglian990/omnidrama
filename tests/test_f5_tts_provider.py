"""OmniDrama F5-TTS 专属声音克隆与角色配音单元测试 (Unit Tests)."""
import os
import sys
import unittest
from pathlib import Path

# 添加 omnidrama 路径
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from providers.f5_tts_provider import F5TTSProvider


class TestF5TTSProvider(unittest.TestCase):
    def setUp(self):
        self.provider = F5TTSProvider(enabled=True)

    def test_provider_initialization(self):
        """测试 F5-TTS Provider 初始化参数与空间绑定."""
        self.assertIn("f5-tts-studio", self.provider.space_url)
        self.assertIsNotNone(self.provider.token)
        self.assertTrue(self.provider.enabled)

    def test_voice_anchors_exist(self):
        """测试男女主角的声音锚点样本是否存在."""
        male_anchor = self.provider.character_anchors["男主角"][0]
        female_anchor = self.provider.character_anchors["女主角"][0]
        self.assertTrue(os.path.exists(male_anchor), f"Missing: {male_anchor}")
        self.assertTrue(os.path.exists(female_anchor), f"Missing: {female_anchor}")
        self.assertGreater(os.path.getsize(male_anchor), 1024)
        self.assertGreater(os.path.getsize(female_anchor), 1024)

    def test_empty_text_handling(self):
        """测试空文本台词的拦截逻辑."""
        res = self.provider.synthesize_character_voice(text="   ", role="男主角")
        self.assertIsNone(res)

    def test_disabled_mode(self):
        """测试禁用状态下的即时返回."""
        prov = F5TTSProvider(enabled=False)
        self.assertFalse(prov.is_available())
        res = prov.synthesize_character_voice("台词文本", role="男主角")
        self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()

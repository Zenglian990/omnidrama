"""OmniDrama 多模型插件化驱动基类 (Provider Base Interfaces).

支持在没有付费 API 时安全降级使用本地/离线/轻量模拟通道，
当后续配置商业 Key 时，无需改动任何业务代码即可热拔插接入顶级视频模型。
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class BaseLLMProvider(ABC):
    @abstractmethod
    def breakdown_script(self, text: str, title: str, genre: str) -> Dict[str, Any]:
        """将小说/文本拆解为结构化镜头与角色资产."""
        pass


class BaseImageProvider(ABC):
    @abstractmethod
    def generate_frame(self, prompt: str, aspect_ratio: str, output_path: str) -> str:
        """根据提示词生成单张高精度分镜画面."""
        pass


class BaseVideoProvider(ABC):
    @abstractmethod
    def image_to_video(
        self,
        image_path: str,
        motion_prompt: str,
        duration_seconds: float,
        output_path: str
    ) -> str:
        """根据分镜首帧与动作提示词，调用视频大模型 (如可灵/海螺/万相) 生成 3~5 秒连续动态视频."""
        pass


class BaseTTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, voice_id: str, output_path: str) -> float:
        """合成语音并返回时长."""
        pass

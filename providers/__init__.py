"""OmniDrama 顶级影视大模型驱动集成包 (SOTA Suite Providers)."""

from .base import (
    BaseLLMProvider,
    BaseImageProvider,
    BaseVideoProvider,
    BaseTTSProvider,
)
from .minimax_provider import MiniMaxHailuoProvider
from .kling_provider import KlingVideoProvider
from .elevenlabs_provider import ElevenLabsProvider
from .flux_provider import FluxProProvider
from .synclabs_provider import SyncLabsProvider
from .suno_provider import SunoMusicProvider

__all__ = [
    "BaseLLMProvider",
    "BaseImageProvider",
    "BaseVideoProvider",
    "BaseTTSProvider",
    "MiniMaxHailuoProvider",
    "KlingVideoProvider",
    "ElevenLabsProvider",
    "FluxProProvider",
    "SyncLabsProvider",
    "SunoMusicProvider",
]

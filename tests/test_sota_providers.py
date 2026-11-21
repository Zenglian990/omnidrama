"""测试 OmniDrama 行业顶配 SOTA 大模型驱动."""
import pytest
from omnidrama.providers import (
    MiniMaxHailuoProvider,
    KlingVideoProvider,
    ElevenLabsProvider,
    FluxProProvider,
    SyncLabsProvider,
    SunoMusicProvider
)


def test_minimax_provider_validation():
    provider = MiniMaxHailuoProvider(api_key="")
    with pytest.raises(ValueError, match="MINIMAX_API_KEY"):
        provider.submit_image_to_video("https://example.com/frame.png", "zoom in")


def test_kling_provider_validation():
    provider = KlingVideoProvider(access_key="", secret_key="")
    with pytest.raises(ValueError, match="KLING_ACCESS_KEY"):
        provider.create_image_to_video_task("base64data", "fight motion")


def test_elevenlabs_provider_validation():
    provider = ElevenLabsProvider(api_key="")
    with pytest.raises(ValueError, match="ELEVENLABS_API_KEY"):
        provider.synthesize_emotional_speech("台词", "voice123", "out.mp3")


def test_flux_provider_validation():
    provider = FluxProProvider(api_key="")
    with pytest.raises(ValueError, match="FLUX_API_KEY"):
        provider.generate_cinematic_frame("shot prompt", "9:16", "out.png")


def test_synclabs_provider_validation():
    provider = SyncLabsProvider(api_key="")
    with pytest.raises(ValueError, match="SYNCLABS_API_KEY"):
        provider.submit_lipsync_job("https://example.com/video.mp4", "https://example.com/audio.mp3")


def test_suno_provider_validation():
    provider = SunoMusicProvider(api_key="")
    with pytest.raises(ValueError, match="SUNO_API_KEY"):
        provider.generate_soundtrack("epic score")

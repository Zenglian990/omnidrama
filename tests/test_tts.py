import pytest
import os
import asyncio
from pathlib import Path
from omnidrama.core.tts_engine import TTSEngine
from omnidrama.schemas.drama_schema import Shot, ShotScaleEnum, CameraMotionEnum

@pytest.mark.asyncio
async def test_generate_speech(tmp_path):
    tts = TTSEngine()
    out_file = str(tmp_path / "test_voice.mp3")
    text = "三年期满，恭迎龙王归位！"
    duration = await tts.generate_speech(text, voice="zh-CN-YunxiNeural", output_path=out_file)
    
    assert os.path.exists(out_file)
    assert os.path.getsize(out_file) > 0
    assert duration > 0.5  # 正常念完至少0.5秒以上

def test_generate_srt(tmp_path):
    tts = TTSEngine()
    shots = [
        Shot(
            shot_id=1,
            shot_scale=ShotScaleEnum.CLOSE_UP,
            camera_motion=CameraMotionEnum.ZOOM_IN,
            speaker="主角",
            dialogue="今日谁敢动她分毫，我便灭谁满门！",
            visual_prompt="man with cold fierce eyes, glowing golden aura",
            duration_seconds=3.0
        ),
        Shot(
            shot_id=2,
            shot_scale=ShotScaleEnum.WIDE_SHOT,
            camera_motion=CameraMotionEnum.SHAKE,
            speaker="反派",
            dialogue="狂妄小儿，死到临头还不自知！",
            visual_prompt="evil elder laughing arrogantly, dark clouds",
            duration_seconds=2.5
        )
    ]
    srt_file = str(tmp_path / "subs.srt")
    tts.generate_srt(shots, srt_file)
    
    assert os.path.exists(srt_file)
    with open(srt_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert "今日谁敢动她分毫" in content
    assert "00:00:00,000 --> 00:00:03,000" in content
    assert "00:00:03,000 --> 00:00:05,500" in content

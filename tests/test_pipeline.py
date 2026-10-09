import pytest
import os
import asyncio
from omnidrama.core.pipeline import OmniDramaPipeline

@pytest.mark.asyncio
async def test_end_to_end_pipeline(tmp_path):
    pipeline = OmniDramaPipeline(
        output_dir=str(tmp_path / "test_out"),
        width=720,
        height=1280,
        fps=24
    )

    sample_story = """
    【第一幕：决战时刻】
    狂风呼啸，夜幕笼罩整座古城。
    主角叶辰：“一切恩怨，今夜彻底了结！”
    反派赵天龙怒吼：“痴心妄想，纳命来！”
    轰然一声巨响，两道光芒在虚空中剧烈碰撞。
    """

    result = await pipeline.run_from_text(
        story_text=sample_story,
        title="测试短剧第一集",
        genre="玄幻热血",
        burn_subtitles=False
    )

    assert os.path.exists(result["final_video"])
    assert os.path.getsize(result["final_video"]) > 1024
    assert os.path.exists(result["subtitles_srt"])
    assert len(result["shots"]) == 4
    for shot in result["shots"]:
        assert shot.duration_seconds is not None and shot.duration_seconds > 0
        assert os.path.exists(shot.audio_path)
        assert os.path.exists(shot.image_path)

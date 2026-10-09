import pytest
import os
import subprocess
from PIL import Image, ImageDraw
from omnidrama.core.compositor import VideoCompositor
from omnidrama.schemas.drama_schema import CameraMotionEnum

@pytest.fixture
def dummy_assets(tmp_path):
    img_path = str(tmp_path / "dummy_frame.jpg")
    img = Image.new("RGB", (720, 1280), color=(30, 30, 40))
    draw = ImageDraw.Draw(img)
    draw.rectangle([100, 200, 620, 1080], fill=(200, 50, 50))
    draw.text((200, 600), "OmniDrama Test Shot", fill=(255, 255, 255))
    img.save(img_path)

    audio_path = str(tmp_path / "dummy_audio.mp3")
    # 生成 1.5 秒空声音频用于测试
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
        "-t", "1.5", "-q:a", "9", audio_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    return img_path, audio_path

def test_render_shot_zoom_in(tmp_path, dummy_assets):
    img_path, audio_path = dummy_assets
    compositor = VideoCompositor(width=720, height=1280, fps=24)
    out_clip = str(tmp_path / "clip_zoom_in.mp4")

    rendered = compositor.render_shot(
        image_path=img_path,
        audio_path=audio_path,
        camera_motion=CameraMotionEnum.ZOOM_IN,
        output_path=out_clip
    )

    assert os.path.exists(rendered)
    assert os.path.getsize(rendered) > 1024

def test_concat_clips(tmp_path, dummy_assets):
    img_path, audio_path = dummy_assets
    compositor = VideoCompositor(width=720, height=1280, fps=24)
    clip1 = str(tmp_path / "c1.mp4")
    clip2 = str(tmp_path / "c2.mp4")

    compositor.render_shot(img_path, audio_path, CameraMotionEnum.ZOOM_IN, clip1)
    compositor.render_shot(img_path, audio_path, CameraMotionEnum.SHAKE, clip2)

    final_video = str(tmp_path / "final_movie.mp4")
    res = compositor.concatenate_clips([clip1, clip2], final_video)

    assert os.path.exists(res)
    assert os.path.getsize(res) > os.path.getsize(clip1)

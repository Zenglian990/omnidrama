import pytest
import os
import subprocess
import numpy as np
import cv2
from omnidrama.core.motion_engine import LiveActionMotionEngine

@pytest.fixture
def dummy_face_and_audio(tmp_path):
    img_path = str(tmp_path / "test_face.jpg")
    # 创建一个具有明显人脸特征的基础图像 (720x1280)
    img = np.zeros((1280, 720, 3), dtype=np.uint8)
    img[:] = (30, 30, 40)
    # 画一个人形轮廓与面部
    cv2.circle(img, (360, 480), 120, (180, 150, 130), -1)
    # 眼睛
    cv2.circle(img, (320, 440), 15, (50, 40, 30), -1)
    cv2.circle(img, (400, 440), 15, (50, 40, 30), -1)
    # 嘴巴
    cv2.ellipse(img, (360, 530), (35, 12), 0, 0, 360, (60, 50, 140), -1)
    cv2.imwrite(img_path, img)

    audio_path = str(tmp_path / "test_speech.wav")
    # 生成 2 秒带起伏的测试音频
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "sine=f=300:d=2.0",
        "-af", "volume=1.0",
        "-c:a", "pcm_s16le", audio_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    return img_path, audio_path

def test_live_action_motion_synthesis(tmp_path, dummy_face_and_audio):
    img_path, audio_path = dummy_face_and_audio
    output_video = str(tmp_path / "animated_actor.mp4")

    engine = LiveActionMotionEngine(fps=24)
    rendered = engine.animate_portrait(
        image_path=img_path,
        audio_path=audio_path,
        output_path=output_video
    )

    assert os.path.exists(rendered)
    assert os.path.getsize(rendered) > 1024

import pytest
import os
import subprocess
from omnidrama.core.audio_mixer import AudioMixer

@pytest.fixture
def dummy_audio_files(tmp_path):
    voice_path = str(tmp_path / "voice.wav")
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=f=440:d=4.0",
        "-c:a", "pcm_s16le", voice_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return voice_path

def test_generate_sfx_library(tmp_path):
    mixer = AudioMixer(assets_dir=str(tmp_path / "assets"))
    sfx_paths = mixer.ensure_sfx_library()
    
    assert os.path.exists(sfx_paths["rain"])
    assert os.path.exists(sfx_paths["thunder"])
    assert os.path.exists(sfx_paths["impact_boom"])

def test_mix_multitrack(tmp_path, dummy_audio_files):
    voice_path = dummy_audio_files
    mixer = AudioMixer(assets_dir=str(tmp_path / "assets"))
    mixer.ensure_sfx_library()
    
    output_mixed = str(tmp_path / "final_mixed.wav")
    
    # 混音：对白 4 秒 + 背景音 + 2.0秒处雷鸣
    sfx_cues = [
        {"name": "thunder", "time_seconds": 1.5, "volume": 0.8}
    ]
    
    res = mixer.mix_soundtrack(
        voice_track=voice_path,
        total_duration=4.0,
        sfx_cues=sfx_cues,
        bgm_type="suspense",
        output_path=output_mixed
    )
    
    assert os.path.exists(res)
    assert os.path.getsize(res) > 1024

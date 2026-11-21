"""OmniDrama 影视级成片总混音与最终压制器 (Masterpiece Compositor).

将人声配音轨、拟音音效轨 (暴雨/雷鸣/重低音/下跪)、电影配乐轨与 2.5D 动漫分镜画面融合成院线级漫剧成片。
"""
import os
import sys
import subprocess
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from omnidrama.core.audio_mixer import AudioMixer

PROJECT_DIR = Path("omnidrama/output/至尊龙王归位")
SHOTS_DIR = PROJECT_DIR / "shots"


def main():
    print("=" * 60)
    print("[OmniDrama] 正在启动电影级三轨合一声音引擎与视听母带压制...")
    print("=" * 60)

    mixer = AudioMixer()
    mixer.ensure_sfx_library()

    # 1. 提取所有分镜的声音持续时间与触发时间点
    # 依次提取 shot_001 到 shot_010 的时长
    shot_durations = []
    for i in range(1, 11):
        audio_file = SHOTS_DIR / f"shot_{i:03d}.mp3"
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(audio_file)
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, check=True)
        shot_durations.append(float(res.stdout.strip()))

    # 计算各分镜起始绝对时间 (秒)
    shot_starts = [0.0]
    for d in shot_durations[:-1]:
        shot_starts.append(shot_starts[-1] + d)

    total_duration = sum(shot_durations)
    print(f"[时间线] 全片总长: {total_duration:.2f} 秒 (共 10 个分镜)")

    # 2. 拟音音效关键打点 (SFX Cues)
    # Shot 1 (0.0s): 雨夜开场 -> 持续环境音
    # Shot 4: 叶辰冷笑反击 -> whoosh 紧张起势
    # Shot 6 (惊雷炸裂): 触发 thunder 惊雷劈裂
    # Shot 7 (大门破碎，修罗破门): 触发 impact_boom 电影重低音轰鸣
    # Shot 8 (修罗战神跪迎龙王): 触发 sword_clash 金铁下跪碰撞
    # Shot 10 (杀无赦大结局): 触发 impact_boom 霸气收尾
    sfx_cues = [
        {"name": "rain", "time_seconds": 0.0, "volume": 0.35},
        {"name": "whoosh", "time_seconds": shot_starts[3], "volume": 0.6},
        {"name": "thunder", "time_seconds": shot_starts[5], "volume": 1.2},
        {"name": "impact_boom", "time_seconds": shot_starts[6], "volume": 1.4},
        {"name": "sword_clash", "time_seconds": shot_starts[7], "volume": 0.9},
        {"name": "impact_boom", "time_seconds": shot_starts[9], "volume": 1.2}
    ]

    # 3. 拼接所有分镜干音人声音轨
    voice_concat_txt = PROJECT_DIR / "voice_concat.txt"
    with open(voice_concat_txt, "w", encoding="utf-8") as f:
        for i in range(1, 11):
            p = (SHOTS_DIR / f"shot_{i:03d}.mp3").resolve()
            f.write(f"file '{str(p).replace('\\', '/')}'\n")

    raw_voice_master = PROJECT_DIR / "raw_voice_master.wav"
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(voice_concat_txt),
        "-c:a", "pcm_s16le", str(raw_voice_master)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    if os.path.exists(voice_concat_txt):
        os.remove(voice_concat_txt)

    # 4. 执行电影级多轨混音 (人声 + 拟音 + 战神高燃 BGM)
    master_soundtrack = PROJECT_DIR / "master_soundtrack.wav"
    print("[声音引擎] 正在融合人声、环境暴雨、惊雷破门拟音与战神原声 BGM...")
    mixer.mix_soundtrack(
        voice_track=str(raw_voice_master),
        total_duration=total_duration,
        sfx_cues=sfx_cues,
        bgm_type="epic_battle",
        output_path=str(master_soundtrack)
    )

    # 5. 将母带音轨与已渲染的 2.5D 高清二次元画面进行终极压制
    raw_video = PROJECT_DIR / "至尊龙王归位_动漫成片.mp4"
    final_masterpiece = PROJECT_DIR / "至尊龙王归位_影视级成片.mp4"

    print("[最终压制] 正在生成《至尊龙王归位》终极影视级成片...")
    cmd = [
        "ffmpeg", "-y",
        "-i", str(raw_video),
        "-i", str(master_soundtrack),
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "256k",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        str(final_masterpiece)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    print("\n" + "=" * 60)
    print("🏆 OmniDrama 终极大考第一阶段交付成片已诞生！")
    print(f"🎬 最终电影级成片: {final_masterpiece}")
    print(f"⏱️ 视频时长: {total_duration:.2f} 秒")
    print(f"🔊 音频轨道: 人声对白 + 暴雨环境 + 惊雷破门拟音 + 战神史诗配乐")
    print("=" * 60)


if __name__ == "__main__":
    main()

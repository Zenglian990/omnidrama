"""OmniDrama 真实国漫大片渲染脚本 (为曾先生重新打造《部族荣光》真成片)."""
import os
import sys
import asyncio
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# 确保 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# FFmpeg 注入
ffmpeg_dir = r"C:\Users\Asus\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin"
if os.path.exists(ffmpeg_dir) and ffmpeg_dir not in os.environ["PATH"]:
    os.environ["PATH"] = ffmpeg_dir + ";" + os.environ["PATH"]

import edge_tts
import edge_tts.constants
import edge_tts.communicate
import edge_tts.drm
from datetime import timezone as _tz

_NEW_WSS_URL = (
    "wss://api.msedgeservices.com/tts/cognitiveservices/websocket/v1"
    f"?Ocp-Apim-Subscription-Key={edge_tts.constants.TRUSTED_CLIENT_TOKEN}"
)
edge_tts.constants.WSS_URL = _NEW_WSS_URL
edge_tts.communicate.WSS_URL = _NEW_WSS_URL

FONT_PATH = "C:/Windows/Fonts/msyh.ttc"
SOURCE_ART = Path(r"C:\Users\Asus\.gemini\antigravity\brain\3ba7c1df-801f-4fa2-b387-225caa96fddd\buzu_shot_001_1792208568387.jpg")
OUTPUT_DIR = Path(r"C:\Users\Asus\Documents\antigravity\blissful-archimedes\omnidrama\output\部族荣光_精品重制")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SHOTS_DIR = OUTPUT_DIR / "shots"
SHOTS_DIR.mkdir(parents=True, exist_ok=True)

TARGET_W = 720
TARGET_H = 1280

SHOT_CONFIGS = [
    {
        "id": 1,
        "crop_mode": "full",
        "speaker": "旁白",
        "speaker_color": (220, 220, 220),
        "dialogue": "申屠强敌重兵压境，姜氏部族生死存亡，就在今日！",
        "voice": "zh-CN-YunyangNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "badge": "第 01 镜 · 兵临城下",
        "motion": "zoom_in",
        "sfx": "whoosh"
    },
    {
        "id": 2,
        "crop_mode": "brother_left", # 弟弟特写
        "speaker": "弟弟",
        "speaker_color": (0, 220, 255),
        "dialogue": "大哥，今日纵然血染残阳，我也绝不退缩半步！",
        "voice": "zh-CN-YunxiNeural",
        "rate": "+5%",
        "pitch": "+3Hz",
        "badge": "第 02 镜 · 少年战意",
        "motion": "zoom_in",
        "sfx": "sword_clash"
    },
    {
        "id": 3,
        "crop_mode": "brother_right", # 哥哥特写
        "speaker": "哥哥",
        "speaker_color": (255, 215, 0),
        "dialogue": "好兄弟！今日就让他们知道，我姜氏儿郎的骨头究竟有多硬！",
        "voice": "zh-CN-YunjianNeural",
        "rate": "+0%",
        "pitch": "-2Hz",
        "badge": "第 03 镜 · 豪声大笑",
        "motion": "zoom_in",
        "sfx": "thunder"
    },
    {
        "id": 4,
        "crop_mode": "full",
        "speaker": "姜氏双雄",
        "speaker_color": (255, 60, 60),
        "dialogue": "姜氏儿郎，随我杀——！",
        "voice": "zh-CN-YunyangNeural",
        "rate": "+15%",
        "pitch": "+4Hz",
        "badge": "第 04 镜 · 悍然冲阵",
        "motion": "zoom_in",
        "sfx": "impact_boom"
    }
]

def make_manga_frame(config, out_path):
    with Image.open(SOURCE_ART) as src:
        src = src.convert("RGB")
        sw, sh = src.size

        # 根据镜头模式裁剪出 720x1280 构图
        mode = config["crop_mode"]
        if mode == "brother_left":
            # 聚焦左侧弟弟 (居中略偏左，胸部以上到全身)
            crop_box = (0, int(sh * 0.20), int(sw * 0.70), int(sh * 0.85))
            cropped = src.crop(crop_box)
        elif mode == "brother_right":
            # 聚焦右侧哥哥
            crop_box = (int(sw * 0.35), int(sh * 0.15), sw, int(sh * 0.80))
            cropped = src.crop(crop_box)
        else:
            # 全景：等比填满 720x1280
            crop_box = (0, 0, sw, sh)
            cropped = src.crop(crop_box)

        # 缩放到 720x1280
        scale = max(TARGET_W / cropped.width, TARGET_H / cropped.height)
        new_w = int(cropped.width * scale)
        new_h = int(cropped.height * scale)
        resized = cropped.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - TARGET_W) // 2
        top = (new_h - TARGET_H) // 2
        frame = resized.crop((left, top, left + TARGET_W, top + TARGET_H))

    # 1. 顶部小徽标
    draw = ImageDraw.Draw(frame)
    badge_font = ImageFont.truetype(FONT_PATH, 22)
    badge_text = config["badge"]
    draw.rounded_rectangle([25, 25, 230, 68], radius=8, fill=(0, 0, 0, 200))
    draw.text((38, 33), badge_text, font=badge_font, fill=(0, 220, 255))

    # 2. 底部暗色渐变（电影级字幕背板）
    overlay = Image.new("RGBA", (TARGET_W, TARGET_H), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    gradient_top = TARGET_H - 260
    for y in range(gradient_top, TARGET_H):
        alpha = int(230 * ((y - gradient_top) / (TARGET_H - gradient_top)))
        overlay_draw.line([(0, y), (TARGET_W, y)], fill=(0, 0, 0, alpha))
    frame.paste(overlay, (0, 0), overlay)

    # 3. 说话人与台词排版
    draw = ImageDraw.Draw(frame)
    speaker_font = ImageFont.truetype(FONT_PATH, 28)
    dialogue_font = ImageFont.truetype(FONT_PATH, 32)

    # 绘制角色名
    draw.text((45, TARGET_H - 210), f"【{config['speaker']}】", font=speaker_font, fill=config["speaker_color"])

    # 绘制台词 (黑粗边 + 纯白文字)
    dialogue = config["dialogue"]
    max_chars = 18
    lines = [dialogue[i:i+max_chars] for i in range(0, len(dialogue), max_chars)]
    line_y = TARGET_H - 160
    for l in lines:
        for ox, oy in [(-2,0), (2,0), (0,-2), (0,2), (-2,-2), (2,2), (-2,2), (2,-2)]:
            draw.text((45 + ox, line_y + oy), l, font=dialogue_font, fill=(0, 0, 0))
        draw.text((45, line_y), l, font=dialogue_font, fill=(255, 255, 255))
        line_y += 42

    frame.save(out_path, quality=95)
    return out_path

async def main():
    print("=" * 60)
    print("🎬 开始重新制作《部族荣光》第162章 兄弟齐心 影视级真短剧成片")
    print("=" * 60)

    clip_paths = []
    durations = []

    for cfg in SHOT_CONFIGS:
        sid = cfg["id"]
        img_file = str(SHOTS_DIR / f"shot_{sid:03d}.jpg")
        audio_file = str(SHOTS_DIR / f"shot_{sid:03d}.mp3")
        clip_file = str(SHOTS_DIR / f"shot_{sid:03d}.mp4")

        # 1. 生成精美动漫分镜画面
        make_manga_frame(cfg, img_file)
        print(f"✅ 第 {sid} 镜已合成真实二次元国漫立绘: {cfg['speaker']} - {cfg['dialogue']}")

        # 2. 生成纯对白角色配音 (绝无任何旁白提示前缀)
        comm = edge_tts.Communicate(
            text=cfg["dialogue"],
            voice=cfg["voice"],
            rate=cfg["rate"],
            pitch=cfg["pitch"]
        )
        await comm.save(audio_file)

        # 获取音频时长
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", audio_file
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, check=True)
        dur = float(res.stdout.strip()) + 0.6 # 留出0.6秒呼吸时间
        durations.append(dur)
        print(f"   🔊 纯台词配音生成成功，时长: {dur:.2f}秒 (声线: {cfg['voice']})")

        # 3. 2.5D 平滑电影运镜渲染 (H.264 视频)
        # 使用 zoompan 滤镜实现极度丝滑的推进
        zoom_expr = "min(pzoom+0.0012,1.15)" if cfg["motion"] == "zoom_in" else "1.05"
        vf = f"zoompan=z='{zoom_expr}':d=1:s=720x1280:fps=25,format=yuv420p"
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", img_file,
            "-t", f"{dur:.2f}",
            "-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            clip_file
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        clip_paths.append(clip_file)

    # 4. 拼接视频流
    video_concat_txt = OUTPUT_DIR / "video_concat.txt"
    with open(video_concat_txt, "w", encoding="utf-8") as f:
        for cp in clip_paths:
            clean_p = str(Path(cp).resolve()).replace('\\', '/')
            f.write(f"file '{clean_p}'\n")

    video_only = OUTPUT_DIR / "video_stream.mp4"
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(video_concat_txt),
        "-c", "copy", str(video_only)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    if video_concat_txt.exists():
        video_concat_txt.unlink()

    # 5. 拼接纯人声干音频轨
    voice_concat_txt = OUTPUT_DIR / "voice_concat.txt"
    with open(voice_concat_txt, "w", encoding="utf-8") as f:
        for idx in range(1, len(SHOT_CONFIGS) + 1):
            p = str((SHOTS_DIR / f"shot_{idx:03d}.mp3").resolve()).replace('\\', '/')
            f.write(f"file '{p}'\n")

    raw_voice = OUTPUT_DIR / "raw_voice.wav"
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(voice_concat_txt),
        "-c:a", "pcm_s16le", str(raw_voice)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    if voice_concat_txt.exists():
        voice_concat_txt.unlink()

    total_dur = sum(durations)
    print(f"\n[混音] 全片总长: {total_dur:.2f}秒，正在合成三轨影视级音频 (人声 + 拟音 + 战神 BGM)...")

    # 6. 使用 AudioMixer 混音
    sys.path.insert(0, r"C:\Users\Asus\Documents\antigravity\blissful-archimedes\omnidrama")
    from core.audio_mixer import AudioMixer
    mixer = AudioMixer()
    mixer.ensure_sfx_library()

    # 计算各分镜时间起点
    shot_starts = [0.0]
    for d in durations[:-1]:
        shot_starts.append(shot_starts[-1] + d)

    sfx_cues = [
        {"name": "rain", "time_seconds": 0.0, "volume": 0.3},
        {"name": "whoosh", "time_seconds": shot_starts[0], "volume": 0.6},
        {"name": "sword_clash", "time_seconds": shot_starts[1], "volume": 0.9},
        {"name": "thunder", "time_seconds": shot_starts[2], "volume": 1.2},
        {"name": "impact_boom", "time_seconds": shot_starts[3], "volume": 1.4},
        {"name": "sword_clash", "time_seconds": shot_starts[3] + 0.8, "volume": 1.0}
    ]

    master_audio = OUTPUT_DIR / "master_audio.wav"
    mixer.mix_soundtrack(
        voice_track=str(raw_voice),
        total_duration=total_dur,
        sfx_cues=sfx_cues,
        bgm_type="epic_battle",
        output_path=str(master_audio)
    )

    # 7. 终极压制合成有声漫剧成片并覆盖至桌面
    desktop_output = Path(r"C:\Users\Asus\Desktop\部族荣光_第162章_兄弟齐心_成品样片.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_only),
        "-i", str(master_audio),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(desktop_output)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    print("\n" + "=" * 60)
    print(f"🎉 真正的高品质 AI 动漫短剧成片已成功压制！")
    print(f"📁 目标路径: {desktop_output}")
    print(f"📊 文件大小: {desktop_output.stat().st_size / (1024*1024):.2f} MB")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())

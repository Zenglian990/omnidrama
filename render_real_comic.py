"""为《至尊龙王归位》生成真正的二次元动漫分镜图并合成最终精美成片."""
import os
import sys
import shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from omnidrama.core.pipeline import OmniDramaPipeline
from omnidrama.schemas.drama_schema import CameraMotionEnum

BRAIN_DIR = Path(r"C:\Users\Asus\.gemini\antigravity\brain\f5542847-d167-4728-8184-c5a99580eb85")
IMG_YECHEN = BRAIN_DIR / "yechen_cold_eyes_1791544019688.jpg"
IMG_MATRIARCH = BRAIN_DIR / "haughty_matriarch_1791544048959.jpg"
IMG_YOUNG_MASTER = BRAIN_DIR / "arrogant_young_master_1791544074800.jpg"

OUTPUT_PROJECT = Path("omnidrama/output/至尊龙王归位")
SHOTS_DIR = OUTPUT_PROJECT / "shots"
FONT_PATH = "C:/Windows/Fonts/msyh.ttc"


def create_styled_manga_frame(source_img_path: Path, shot_id: int, speaker: str, dialogue: str, motion_name: str, out_path: str):
    """裁剪动漫立绘、添加暗角、添加精美漫剧字幕底栏与中文字幕."""
    with Image.open(source_img_path) as im:
        im = im.convert("RGB")
        target_w, target_h = 720, 1280
        
        # 居中等比缩放并裁剪至 720x1280
        scale = max(target_w / im.width, target_h / im.height)
        new_w = int(im.width * scale)
        new_h = int(im.height * scale)
        im_resized = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        frame = im_resized.crop((left, top, left + target_w, top + target_h))

    draw = ImageDraw.Draw(frame)

    # 1. 顶部小徽标（镜头信息）
    badge_font = ImageFont.truetype(FONT_PATH, 20)
    badge_text = f"第 {shot_id:02d} 镜 · {motion_name}"
    # 绘制半透明胶囊背景
    draw.rounded_rectangle([20, 20, 180, 56], radius=8, fill=(0, 0, 0, 180))
    draw.text((32, 26), badge_text, font=badge_font, fill=(0, 220, 255))

    # 2. 底部字幕黑透渐变遮罩 (防止画面太亮字看不清)
    overlay = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    gradient_top = target_h - 220
    for y in range(gradient_top, target_h):
        alpha = int(220 * ((y - gradient_top) / (target_h - gradient_top)))
        overlay_draw.line([(0, y), (target_w, y)], fill=(0, 0, 0, alpha))
    frame.paste(overlay, (0, 0), overlay)

    # 3. 绘制角色说话人与中文台词
    draw = ImageDraw.Draw(frame)
    speaker_font = ImageFont.truetype(FONT_PATH, 26)
    dialogue_font = ImageFont.truetype(FONT_PATH, 30)

    # 说话人标签
    speaker_color = (255, 215, 0) if speaker in ["叶辰", "主角"] else ((255, 100, 100) if "赵" in speaker or "母" in speaker else (100, 220, 255))
    draw.text((40, target_h - 180), f"【{speaker}】", font=speaker_font, fill=speaker_color)

    # 中文台词换行排版
    max_chars_per_line = 18
    dialogue_lines = [dialogue[i:i+max_chars_per_line] for i in range(0, len(dialogue), max_chars_per_line)]
    line_y = target_h - 135
    for line in dialogue_lines:
        # 黑描边 + 白字 (经典动漫字幕效果)
        for ox, oy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
            draw.text((40 + ox, line_y + oy), line, font=dialogue_font, fill=(0, 0, 0))
        draw.text((40, line_y), line, font=dialogue_font, fill=(255, 255, 255))
        line_y += 38

    frame.save(out_path, quality=95)
    return out_path


def main():
    print("=" * 60)
    print("[OmniDrama] 正在为《至尊龙王归位》注入真正的高清二次元漫画分镜立绘...")
    print("=" * 60)

    # 镜头与立绘映射
    # Shot 1: 旁白 (林家祖宅大堂) -> 岳母大宅背景
    # Shot 2: 岳母柳琴 -> 岳母冷笑
    # Shot 3: 旁白 (叶辰淡然) -> 叶辰特写
    # Shot 4: 叶辰 (三千万？) -> 叶辰怒意
    # Shot 5: 赵公子狂妄 -> 赵公子大笑
    # Shot 6: 旁白 (惊雷滚滚) -> 叶辰爆发
    # Shot 7: 旁白 (大门破碎) -> 叶辰
    # Shot 8: 修罗战神 (恭迎龙王) -> 叶辰王者
    # Shot 9: 岳母与赵公子瘫倒 -> 岳母震惊
    # Shot 10: 叶辰 (杀无赦) -> 叶辰冷冽大特写

    shot_configs = [
        (1, IMG_MATRIARCH, "旁白", "林家祖宅大堂，狂风骤雨拍打着雕花木窗。", "镜头推进"),
        (2, IMG_MATRIARCH, "岳母柳琴", "叶辰，入赘三年，今日若拿不出三千万，就立刻滚出林家！", "向左横移"),
        (3, IMG_YECHEN, "旁白", "叶辰神色淡然，深邃的双眸中隐现寒光。", "镜头推进"),
        (4, IMG_YECHEN, "叶辰", "三千万？当年若非我暗中相助，林家早在三年前就已灰飞烟灭！", "镜头推进"),
        (5, IMG_YOUNG_MASTER, "赵公子", "哈哈哈！大言不惭的废物，也不撒泡尿照照自己是个什么东西！", "镜头拉远"),
        (6, IMG_YECHEN, "旁白", "突然，天地间惊雷滚滚，整座大堂剧烈震颤！", "镜头震撼"),
        (7, IMG_YECHEN, "旁白", "大门轰然破碎，十八位身披黑金战铠的修罗战神破门而入！", "镜头拉远"),
        (8, IMG_YECHEN, "修罗战神", "恭迎龙王回归！十万修罗殿众将，随时听候调遣！", "镜头推进"),
        (9, IMG_MATRIARCH, "岳母与赵公子", "龙……龙王？！你竟然是那位镇守北境的至尊龙王！", "镜头震撼"),
        (10, IMG_YECHEN, "叶辰", "犯我逆鳞者，杀无赦！", "镜头推进")
    ]

    pipeline = OmniDramaPipeline(output_dir="omnidrama/output", width=720, height=1280, fps=24)
    clip_paths = []

    for shot_id, src_img, speaker, dialogue, motion_name in shot_configs:
        img_out = str(SHOTS_DIR / f"shot_{shot_id:03d}.jpg")
        audio_out = str(SHOTS_DIR / f"shot_{shot_id:03d}.mp3")
        clip_out = str(SHOTS_DIR / f"shot_{shot_id:03d}.mp4")

        # 生成精美漫画图
        create_styled_manga_frame(src_img, shot_id, speaker, dialogue, motion_name, img_out)
        print(f"[进度] 第 {shot_id:02d} 镜已合成真实漫画立绘与字幕: {speaker}")

        # 匹配运镜
        if "震撼" in motion_name:
            motion = CameraMotionEnum.SHAKE
        elif "拉远" in motion_name:
            motion = CameraMotionEnum.ZOOM_OUT
        elif "横移" in motion_name:
            motion = CameraMotionEnum.PAN_LEFT
        else:
            motion = CameraMotionEnum.ZOOM_IN

        pipeline.compositor.render_shot(
            image_path=img_out,
            audio_path=audio_out,
            camera_motion=motion,
            output_path=clip_out
        )
        clip_paths.append(clip_out)

    final_video = str(OUTPUT_PROJECT / "至尊龙王归位_动漫成片.mp4")
    pipeline.compositor.concatenate_clips(clip_paths, final_video)

    print("\n" + "=" * 60)
    print("[成功] 真正的 AI 动漫漫剧成片制作完成！")
    print(f"[成片视频] {final_video}")
    print("=" * 60)

if __name__ == "__main__":
    main()

"""OmniDrama 端到端导演与视频合成总管线 (Pipeline)."""
from __future__ import annotations

import os
import re
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

try:
    from omnidrama.schemas.drama_schema import DramaProject, Shot, CameraMotionEnum
    from omnidrama.core.director import DirectorAgent
    from omnidrama.core.tts_engine import TTSEngine
    from omnidrama.core.compositor import VideoCompositor
    from omnidrama.providers.liveportrait_provider import LivePortraitProvider
    from omnidrama.providers.f5_tts_provider import F5TTSProvider
    from omnidrama.providers.siliconflow_provider import SiliconFlowProvider
except ImportError:
    from schemas.drama_schema import DramaProject, Shot, CameraMotionEnum
    from core.director import DirectorAgent
    from core.tts_engine import TTSEngine
    from core.compositor import VideoCompositor
    from providers.liveportrait_provider import LivePortraitProvider
    from providers.f5_tts_provider import F5TTSProvider
    try:
        from providers.siliconflow_provider import SiliconFlowProvider
    except ImportError:
        SiliconFlowProvider = None


def _load_cjk_font(size: int):
    """跨平台中文字体加载器 (优先加载微软雅黑、黑体、Noto Sans等)."""
    candidates = [
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ]
    for fp in candidates:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _pick_source_actor_image(speaker: str, shot_id: int, assets_dir: Path) -> Path:
    """为剧本镜头精准匹配真实演员剧照或院线场景原画 (角色绝对绑定，杜绝纯黑占位框)."""
    # 1. 主角 / 战神 / 特工
    if any(k in speaker for k in ["易冷", "特工", "战神", "主角", "男主", "龙王", "修罗", "尊者", "叶辰"]):
        yileng = assets_dir / "actor_yileng.jpg"
        if yileng.exists():
            return yileng

    # 2. 萌娃 / 女儿 / 小女孩
    if any(k in speaker for k in ["暖暖", "女儿", "小女孩", "女孩", "小妹", "妹", "孩子", "童"]):
        nuannuan = assets_dir / "actor_yinuannuan.jpg"
        if nuannuan.exists():
            return nuannuan

    # 3. 恶霸 / 反派 / 刀疤混混
    if any(k in speaker for k in ["恶霸", "反派", "刀疤", "打手", "混混", "泼皮", "流氓", "坏人", "仇敌", "赵天龙"]):
        gangster = assets_dir / "actor_scar_gangster.jpg"
        if gangster.exists():
            return gangster

    # 4. 女性角色 / 女特工 / 夫人
    if any(k in speaker for k in ["女", "特工", "助手", "林", "苏", "姐", "夫人", "秘书"]):
        female = assets_dir / "female_agent_01.jpg"
        if female.exists():
            return female

    # 5. 旁白 / 宏大场景镜头
    if "旁白" in speaker or "Scene" in speaker or "环境" in speaker or not speaker:
        if shot_id <= 2:
            scene_rain = assets_dir / "scene_rain_alley.jpg"
            if scene_rain.exists():
                return scene_rain
        else:
            scene_fight = assets_dir / "scene_fight_action.jpg"
            if scene_fight.exists():
                return scene_fight

    # 6. 轮询本地已有真实剧照库
    available = sorted(list(assets_dir.glob("*.jpg")))
    if available:
        return available[(shot_id - 1) % len(available)]

    return assets_dir / "actor_yileng.jpg"


def _is_cjk_dominant(text: str) -> bool:
    """判断文本是否以中日韩等东亚方块字为主，用于选择按字断行或英文按词断行."""
    if not text:
        return True
    cjk_count = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff" or "\u3040" <= ch <= "\u30ff" or "\uac00" <= ch <= "\ud7af")
    return cjk_count >= max(1, len(text.strip()) // 4)


def _wrap_subtitle_lines(text: str, max_chars: int = 13, max_lines: int = 3) -> List[str]:
    """智能字幕断行：中日韩按标点与防孤字均衡断行，英语/拉丁语按单词边界整词折行绝不劈词."""
    clean = (text or "").strip()
    if not clean:
        return []

    # 英语/拉丁语整词断行（每行约 26~30 字符，避免把英文单词从中间劈开）
    if not _is_cjk_dominant(clean):
        latin_max = max(24, int(max_chars * 2.1))
        lines: List[str] = []
        for para in clean.splitlines():
            words = para.strip().split()
            cur = ""
            for w in words:
                cand = f"{cur} {w}".strip() if cur else w
                if len(cand) <= latin_max:
                    cur = cand
                else:
                    if cur:
                        lines.append(cur)
                    cur = w
            if cur:
                lines.append(cur)
        if len(lines) > max_lines:
            tail = " ".join(lines[max_lines - 1:])
            lines = lines[:max_lines - 1] + [tail[:latin_max - 1].rstrip() + "…"]
        return lines

    # 中日韩按标点与防末行孤字均衡断行
    segments = [seg.strip() for seg in re.split(r"(?<=[。！？!?；;，,、])", clean) if seg.strip()]
    lines = []
    cur = ""
    for seg in segments:
        if len(cur) + len(seg) <= max_chars:
            cur += seg
        else:
            if cur:
                lines.append(cur)
                cur = ""
            while len(seg) > max_chars:
                if len(seg) <= max_chars * 2:
                    mid = (len(seg) + 1) // 2
                    lines.append(seg[:mid])
                    seg = seg[mid:]
                    break
                lines.append(seg[:max_chars])
                seg = seg[max_chars:]
            cur = seg
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        merged_tail = "".join(lines[max_lines - 1:])
        lines = lines[:max_lines - 1] + [merged_tail[:max_chars - 1] + "…"]
    return lines


def _contains_chinese(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in (text or ""))


def _create_subtitle_overlay(
    shot_id: int,
    speaker: str,
    dialogue: str,
    motion_name: str,
    out_png_path: str,
    width: int = 720,
    height: int = 1280,
    show_debug_badge: bool = False,
    target_lang: str = "zh",
) -> str:
    """生成 9:16 商业级纯净安全区 RGBA 透明字幕层（默认无左上角调试水印，出海模式杜绝残留中文标签）."""
    os.makedirs(os.path.dirname(os.path.abspath(out_png_path)), exist_ok=True)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # 底部柔和电影渐暗遮罩（轻度压暗下缘，凸显字幕且不破坏主体画面）
    gradient_height = int(height * 0.30)
    gradient_top = height - gradient_height
    for y in range(gradient_top, height):
        ratio = (y - gradient_top) / max(1, gradient_height)
        alpha = int(165 * (ratio ** 1.35))
        draw.line([(0, y), (width, y)], fill=(6, 8, 16, alpha))

    lang = (target_lang or "zh").strip().lower()
    is_latin = (lang == "en") or (dialogue and not _is_cjk_dominant(dialogue))

    badge_size = max(18, int(height * 0.017))
    speaker_size = max(22, int(height * 0.022))
    dialogue_size = max(30, int(height * (0.028 if is_latin else 0.033)))

    badge_font = _load_cjk_font(badge_size)
    speaker_font = _load_cjk_font(speaker_size)
    dialogue_font = _load_cjk_font(dialogue_size)

    # 商业成片默认彻底关闭左上角调试编号水印，仅在显式开启 show_debug_badge 时绘制
    if show_debug_badge:
        badge_text = f"#{shot_id:02d} · {motion_name}"
        b_box = draw.textbbox((0, 0), badge_text, font=badge_font)
        badge_w = (b_box[2] - b_box[0]) + 28
        badge_h = (b_box[3] - b_box[1]) + 16
        draw.rounded_rectangle([24, 34, 24 + badge_w, 34 + badge_h], radius=10, fill=(10, 14, 26, 185), outline=(0, 220, 255, 160), width=1)
        draw.text((38, 41), badge_text, font=badge_font, fill=(0, 232, 255, 255))

    # 字幕垂直安全区：距离底部 18% ~ 31%，避开 TikTok / 抖音底部文案及播放器进度条
    lines = _wrap_subtitle_lines(dialogue, max_chars=13 if width <= 720 else 16, max_lines=3)
    line_spacing = int(dialogue_size * 1.38)
    total_text_h = len(lines) * line_spacing if lines else 0
    sub_bottom_y = height - int(height * 0.175)
    sub_top_y = sub_bottom_y - total_text_h

    # 角色名胶囊：旁白/环境镜头直接隐去胶囊提升电影沉浸感；非中文出海成片严禁渲染未翻译的中文角色名
    clean_speaker = (speaker or "").strip()
    is_narrator = (not clean_speaker) or any(k in clean_speaker for k in ["旁白", "叙事", "Scene", "环境", "Narrator"])
    hide_due_to_lang = (lang != "zh" and _contains_chinese(clean_speaker))
    if clean_speaker and not is_narrator and not hide_due_to_lang:
        if any(k in clean_speaker for k in ["恶霸", "反派", "刀疤", "打手", "混混", "赵", "母", "Villain"]):
            pill_bg, pill_fg = (153, 27, 27, 220), (254, 226, 226, 255)
        elif any(k in clean_speaker for k in ["暖暖", "女儿", "女孩", "女", "林", "苏", "妻", "Lady", "Miss"]):
            pill_bg, pill_fg = (131, 24, 67, 220), (252, 231, 243, 255)
        else:
            pill_bg, pill_fg = (120, 53, 15, 225), (254, 240, 138, 255)
        s_box = draw.textbbox((0, 0), clean_speaker, font=speaker_font)
        sp_w = (s_box[2] - s_box[0]) + 32
        sp_h = (s_box[3] - s_box[1]) + 14
        sp_x1 = (width - sp_w) // 2
        sp_y2 = sub_top_y - 16 if lines else (sub_bottom_y - 20)
        sp_y1 = sp_y2 - sp_h
        draw.rounded_rectangle([sp_x1, sp_y1, sp_x1 + sp_w, sp_y2], radius=sp_h // 2, fill=pill_bg, outline=(255, 255, 255, 90), width=1)
        draw.text((width // 2, (sp_y1 + sp_y2) // 2), clean_speaker, font=speaker_font, fill=pill_fg, anchor="mm")

    # 居中粗描边大字幕 + 柔和半透明圆角底托
    if lines:
        max_line_w = 0
        for ln in lines:
            l_box = draw.textbbox((0, 0), ln, font=dialogue_font)
            max_line_w = max(max_line_w, l_box[2] - l_box[0])
        pad_x, pad_y = 26, 14
        box_x1 = max(24, (width - max_line_w) // 2 - pad_x)
        box_x2 = min(width - 24, (width + max_line_w) // 2 + pad_x)
        box_y1 = sub_top_y - pad_y
        box_y2 = sub_bottom_y + pad_y - 6
        draw.rounded_rectangle([box_x1, box_y1, box_x2, box_y2], radius=16, fill=(8, 12, 22, 165))

        line_y = sub_top_y + line_spacing // 2
        stroke_offsets = [(-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, 2), (-2, 2), (2, -2)]
        for line in lines:
            for ox, oy in stroke_offsets:
                draw.text((width // 2 + ox, line_y + oy), line, font=dialogue_font, fill=(0, 0, 0, 255), anchor="mm")
            draw.text((width // 2, line_y), line, font=dialogue_font, fill=(255, 255, 255, 255), anchor="mm")
            line_y += line_spacing

    overlay.save(out_png_path, "PNG")
    return out_png_path


class OmniDramaPipeline:
    def __init__(
        self,
        output_dir: str = "omnidrama/output",
        width: int = 720,
        height: int = 1280,
        fps: int = 24
    ):
        self.output_dir = output_dir
        self.width = width
        self.height = height
        self.fps = fps
        self.director = DirectorAgent()
        self.tts = TTSEngine()
        self.compositor = VideoCompositor(width=width, height=height, fps=fps)
        self.liveportrait = LivePortraitProvider()
        self.f5_tts = F5TTSProvider()
        self.siliconflow = SiliconFlowProvider() if SiliconFlowProvider else None

        base_dir = Path(__file__).resolve().parent.parent
        self.assets_dir = base_dir / "assets" / "cinematic_actors"

    def _prepare_shot_image(self, shot: Shot, out_path: str) -> str:
        """为分镜准备高质量高清画面（优先调用硅基流动/阿里生图，未配置或离线时自动精准匹配真人定妆照并自适应裁剪调色）."""
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

        # 1. 尝试外置生图模型 (若配置了 SILICONFLOW_API_KEY)
        try:
            from core.runtime_context import get_provider_key
        except ImportError:
            from omnidrama.core.runtime_context import get_provider_key
        sf_key = get_provider_key("SILICONFLOW_API_KEY")
        if sf_key and self.siliconflow:
            try:
                prompt = f"Cinematic short drama shot, {shot.shot_scale.value}, {shot.visual_prompt}, high resolution, photorealistic, dramatic lighting"
                self.siliconflow.generate_shot_image(prompt, out_path)
                if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
                    return out_path
            except Exception as e:
                print(f"[Pipeline] SiliconFlow 生图降级至本地剧照库: {e}")

        # 2. 智能匹配本地真实真人定妆照/场景图
        src_path = _pick_source_actor_image(shot.speaker, shot.shot_id, self.assets_dir)
        if src_path and os.path.exists(src_path):
            with Image.open(src_path) as im:
                im = im.convert("RGB")
                scale = max(self.width / im.width, self.height / im.height)
                new_w = int(round(im.width * scale))
                new_h = int(round(im.height * scale))
                im_resized = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
                offset_x = (new_w - self.width) // 2
                offset_y = (new_h - self.height) // 2
                frame = im_resized.crop((offset_x, offset_y, offset_x + self.width, offset_y + self.height))
                frame = ImageEnhance.Contrast(frame).enhance(1.06)
                frame.save(out_path, quality=95)
                return out_path

        # 3. 终极兜底
        im = Image.new("RGB", (self.width, self.height), (16, 22, 34))
        im.save(out_path, quality=95)
        return out_path

    def _generate_placeholder_frame(self, shot: Shot, out_path: str) -> str:
        """向后兼容别名：生成真实高质量分镜画面."""
        return self._prepare_shot_image(shot, out_path)

    async def run_from_text(
        self,
        story_text: str,
        title: str = "短剧第一集",
        genre: str = "都市热血",
        burn_subtitles: bool = True,
        enable_liveportrait: bool = True,
        enable_f5_tts: bool = True
    ) -> Dict[str, Any]:
        """端到端全自动运行：剧本拆解 ➔ 神经声音克隆/TTS ➔ 真实分镜原画 ➔ 神经动效/2.5D运镜+双层字幕渲染 ➔ 导出成片."""
        try:
            from core.security import _safe_resolve_under, _safe_slug
            from core.runtime_context import get_provider_key
            from core.net_safety import MAX_VIDEO_BYTES, safe_download_to_file
        except ImportError:
            from omnidrama.core.security import _safe_resolve_under, _safe_slug
            from omnidrama.core.runtime_context import get_provider_key
            from omnidrama.core.net_safety import MAX_VIDEO_BYTES, safe_download_to_file

        safe_title = _safe_slug(title, default="short_drama")
        project_dir_p = _safe_resolve_under(self.output_dir, safe_title)
        shots_dir_p = _safe_resolve_under(project_dir_p, "shots")
        shots_dir_p.mkdir(parents=True, exist_ok=True)
        project_dir = str(project_dir_p)
        shots_dir = str(shots_dir_p)

        # 1. 导演拆解
        project = self.director.breakdown_story_offline(story_text, title=title, genre=genre)

        clip_paths = []
        for shot in project.shots:
            # 2. 语音生成 (优先使用 F5-TTS 专属声音克隆，未命中或离线时平滑降级至 Edge-TTS)
            audio_path = os.path.join(shots_dir, f"shot_{shot.shot_id:03d}.mp3")
            voice_rendered = False
            if enable_f5_tts and shot.dialogue and shot.speaker not in ["旁白", "Scene", "环境"]:
                cloned_audio = self.f5_tts.synthesize_character_voice(
                    text=shot.dialogue,
                    role=shot.speaker,
                    output_path=audio_path
                )
                if cloned_audio and os.path.exists(cloned_audio):
                    try:
                        shot.duration_seconds = self.compositor.get_audio_duration(audio_path)
                        shot.audio_path = audio_path
                        voice_rendered = True
                    except Exception:
                        voice_rendered = False

            if not voice_rendered:
                voice_id, rate, pitch = self.tts.resolve_voice(shot.speaker)
                duration = await self.tts.generate_speech(
                    text=shot.dialogue,
                    voice=voice_id,
                    output_path=audio_path,
                    rate=rate,
                    pitch=pitch
                )
                shot.duration_seconds = duration
                shot.audio_path = audio_path

            # 3. 画面资产（采用真实演员定妆照/院线场景，100% 拒绝纯黑框）
            img_path = os.path.join(shots_dir, f"shot_{shot.shot_id:03d}.jpg")
            if not os.path.exists(img_path):
                self._prepare_shot_image(shot, img_path)
            shot.image_path = img_path

            # 4. 生成该镜的独立透明字幕层 PNG (避免豆腐块，中文高保真描边)
            sub_png = os.path.join(shots_dir, f"sub_{shot.shot_id:03d}.png")
            _create_subtitle_overlay(
                shot_id=shot.shot_id,
                speaker=shot.speaker,
                dialogue=shot.dialogue,
                motion_name=shot.camera_motion.value,
                out_png_path=sub_png,
                width=self.width,
                height=self.height
            )

            # 4.5 尝试调用 SOTA 图生视频大模型 (快手可灵 Kling 2.0 / 字节火山方舟 Seedance)
            sota_video_path = None
            kling_key = get_provider_key("KLING_ACCESS_KEY") or get_provider_key("KLING_API_KEY")
            ark_key = get_provider_key("ARK_API_KEY")

            if ark_key:
                try:
                    try:
                        from omnidrama.providers.volcengine_seedance_provider import VolcengineSeedanceProvider
                    except ImportError:
                        from providers.volcengine_seedance_provider import VolcengineSeedanceProvider
                    sp = VolcengineSeedanceProvider(api_key=ark_key)
                    seedance_job = os.path.join(shots_dir, f"shot_{shot.shot_id:03d}_seedance_job.json")
                    seedance_out = os.path.join(shots_dir, f"seedance_vid_{shot.shot_id:03d}.mp4")
                    tid = sp.create_generation_task(
                        prompt=shot.visual_prompt,
                        image_path=shot.image_path,
                        ratio="9:16",
                        resolution="720p",
                        duration=5,
                        camera_fixed=False,
                        job_path=seedance_job
                    )
                    if tid:
                        vid_path = sp.poll_and_download(tid, seedance_out, seedance_job, 120)
                        if vid_path and os.path.exists(vid_path):
                            sota_video_path = vid_path
                except Exception as e:
                    print(f"[Pipeline] Seedance 视频生成异常: {e}")

            if not sota_video_path and kling_key:
                try:
                    import base64
                    try:
                        from omnidrama.providers.kling_provider import KlingVideoProvider
                    except ImportError:
                        from providers.kling_provider import KlingVideoProvider
                    with open(shot.image_path, "rb") as bf:
                        b64_img = base64.b64encode(bf.read()).decode("utf-8")
                    kp = KlingVideoProvider(access_key=kling_key)
                    kling_job = os.path.join(shots_dir, f"shot_{shot.shot_id:03d}_kling_job.json")
                    tid = kp.create_image_to_video_task(
                        image_base64=b64_img,
                        prompt=shot.visual_prompt,
                        duration=5,
                        camera_type="zoom_in",
                        mode="pro",
                        job_path=kling_job
                    )
                    if tid:
                        v_url = kp.poll_kling_task(tid, 120, kling_job)
                        if v_url:
                            kling_target = str(_safe_resolve_under(shots_dir_p, f"kling_vid_{shot.shot_id:03d}.mp4"))
                            safe_download_to_file(v_url, kling_target, max_bytes=MAX_VIDEO_BYTES, timeout=45)
                            sota_video_path = kling_target
                except Exception as e:
                    print(f"[Pipeline] Kling 视频生成异常: {e}")

            clip_path = os.path.join(shots_dir, f"shot_{shot.shot_id:03d}.mp4")

            if sota_video_path and os.path.exists(sota_video_path):
                self.compositor.render_video_shot(
                    video_clip_path=sota_video_path,
                    audio_path=shot.audio_path,
                    output_path=clip_path,
                    subtitle_overlay_path=sub_png
                )
                clip_paths.append(clip_path)
                continue

            # 5. 单镜头渲染 (支持 LivePortrait 神经动效与 2.5D 运镜自动融合)
            neural_rendered = False

            # 若启用神经动效，且为非旁白角色特写/对话镜头
            if enable_liveportrait and shot.speaker not in ["旁白", "Scene", "环境"]:
                raw_neural_video = os.path.join(shots_dir, f"neural_{shot.shot_id:03d}.mp4")
                motion_type = "talking" if shot.dialogue else "acting"
                res_path = self.liveportrait.animate_character(
                    image_path=shot.image_path,
                    output_path=raw_neural_video,
                    motion_type=motion_type
                )
                if res_path and os.path.exists(res_path):
                    try:
                        self.compositor.render_neural_shot(
                            video_path=res_path,
                            audio_path=shot.audio_path,
                            output_path=clip_path,
                            subtitle_overlay_path=sub_png
                        )
                        neural_rendered = True
                    except Exception as e:
                        print(f"[Pipeline] Neural mux failed, fallback to 2.5D: {e}")
                        neural_rendered = False

            # 若未启用神经动效或云端降级，执行经典 2.5D 运镜渲染
            if not neural_rendered:
                if shot.speaker not in ["旁白", "Scene", "环境"] and shot.dialogue:
                    try:
                        self.compositor.render_live_actor_shot(
                            image_path=shot.image_path,
                            audio_path=shot.audio_path,
                            output_path=clip_path,
                            subtitle_overlay_path=sub_png
                        )
                    except Exception:
                        self.compositor.render_shot(
                            image_path=shot.image_path,
                            audio_path=shot.audio_path,
                            camera_motion=shot.camera_motion,
                            output_path=clip_path,
                            subtitle_overlay_path=sub_png
                        )
                else:
                    self.compositor.render_shot(
                        image_path=shot.image_path,
                        audio_path=shot.audio_path,
                        camera_motion=shot.camera_motion,
                        output_path=clip_path,
                        subtitle_overlay_path=sub_png
                    )

            clip_paths.append(clip_path)

        # 6. 生成 SRT 字幕文件
        srt_path = str(_safe_resolve_under(project_dir_p, f"{safe_title}.srt"))
        self.tts.generate_srt(project.shots, srt_path)

        # 7. 拼接完整成片
        raw_final_video = str(_safe_resolve_under(project_dir_p, f"{safe_title}_raw.mp4"))
        self.compositor.concatenate_clips(clip_paths, raw_final_video)

        final_video_path = raw_final_video
        return {
            "title": title,
            "project": project,
            "shots": project.shots,
            "subtitles_srt": srt_path,
            "final_video": final_video_path
        }

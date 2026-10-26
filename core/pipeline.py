"""OmniDrama 端到端导演与视频合成总管线 (Pipeline)."""
from __future__ import annotations

import os
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


def _create_subtitle_overlay(
    shot_id: int,
    speaker: str,
    dialogue: str,
    motion_name: str,
    out_png_path: str,
    width: int = 720,
    height: int = 1280
) -> str:
    """生成 9:16 RGBA 全透明字幕与顶部徽标叠加层 (用于 FFmpeg 运镜后固定叠加，绝不放大裁切)."""
    os.makedirs(os.path.dirname(os.path.abspath(out_png_path)), exist_ok=True)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # 底部字幕渐变黑透遮罩 (营造电影下巴阴影，确保白字无论在任何背景下均极清晰)
    gradient_height = int(height * 0.18)
    gradient_top = height - gradient_height
    for y in range(gradient_top, height):
        ratio = (y - gradient_top) / max(1, gradient_height)
        alpha = int(220 * ratio)
        draw.line([(0, y), (width, y)], fill=(8, 10, 18, alpha))

    # 字体尺寸按分辨率自适应
    badge_size = max(16, int(height * 0.016))
    speaker_size = max(20, int(height * 0.021))
    dialogue_size = max(24, int(height * 0.024))

    badge_font = _load_cjk_font(badge_size)
    speaker_font = _load_cjk_font(speaker_size)
    dialogue_font = _load_cjk_font(dialogue_size)

    # 顶部镜头徽标 (固定在左上角安全区)
    badge_text = f"第 {shot_id:02d} 镜 · {motion_name}"
    badge_w = int(width * 0.38)
    badge_h = int(height * 0.038)
    draw.rounded_rectangle([20, 24, 20 + badge_w, 24 + badge_h], radius=8, fill=(10, 14, 26, 210), outline=(0, 200, 255, 180), width=1)
    draw.text((32, 28), badge_text, font=badge_font, fill=(0, 220, 255, 255))

    # 底部角色名标签
    if speaker and speaker not in ["Scene", "环境"]:
        speaker_color = (255, 215, 0, 255) if any(k in speaker for k in ["易冷", "叶辰", "主角", "男主"]) else (
            (255, 110, 110, 255) if any(k in speaker for k in ["恶霸", "反派", "刀疤", "打手", "赵天龙"]) else (
                (255, 180, 210, 255) if any(k in speaker for k in ["暖暖", "女儿", "女孩"]) else (120, 220, 255, 255)
            )
        )
        draw.text((36, height - int(height * 0.150)), f"【{speaker}】", font=speaker_font, fill=speaker_color)

    # 底部描边中文字幕
    if dialogue:
        max_chars_per_line = 18 if width <= 720 else 22
        dialogue_lines = [dialogue[i:i + max_chars_per_line] for i in range(0, len(dialogue), max_chars_per_line)][:3]
        line_y = height - int(height * 0.110)
        line_spacing = int(dialogue_size * 1.35)
        for line in dialogue_lines:
            for ox, oy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1), (-1, 1), (1, -1)]:
                draw.text((36 + ox, line_y + oy), line, font=dialogue_font, fill=(0, 0, 0, 255))
            draw.text((36, line_y), line, font=dialogue_font, fill=(255, 255, 255, 255))
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
        sf_key = os.environ.get("SILICONFLOW_API_KEY", "").strip()
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
        project_dir = os.path.join(self.output_dir, title)
        shots_dir = os.path.join(project_dir, "shots")
        os.makedirs(shots_dir, exist_ok=True)

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
            kling_key = (os.environ.get("KLING_ACCESS_KEY", "") or os.environ.get("KLING_API_KEY", "")).strip()
            ark_key = os.environ.get("ARK_API_KEY", "").strip()

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
                            import requests as _req
                            r_v = _req.get(v_url, timeout=45)
                            kling_target = os.path.join(shots_dir, f"kling_vid_{shot.shot_id:03d}.mp4")
                            with open(kling_target, "wb") as vf:
                                vf.write(r_v.content)
                            sota_video_path = kling_target
                except Exception as e:
                    print(f"[Pipeline] Kling 视频生成异常: {e}")

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
            clip_path = os.path.join(shots_dir, f"shot_{shot.shot_id:03d}.mp4")
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
        srt_path = os.path.join(project_dir, f"{title}.srt")
        self.tts.generate_srt(project.shots, srt_path)

        # 7. 拼接完整成片
        raw_final_video = os.path.join(project_dir, f"{title}_raw.mp4")
        self.compositor.concatenate_clips(clip_paths, raw_final_video)

        final_video_path = raw_final_video
        return {
            "title": title,
            "project": project,
            "shots": project.shots,
            "subtitles_srt": srt_path,
            "final_video": final_video_path
        }

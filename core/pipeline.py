"""OmniDrama 端到端导演与视频合成总管线 (Pipeline)."""
import os
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont

from omnidrama.schemas.drama_schema import DramaProject, Shot, CameraMotionEnum
from omnidrama.core.director import DirectorAgent
from omnidrama.core.tts_engine import TTSEngine
from omnidrama.core.compositor import VideoCompositor


class OmniDramaPipeline:
    def __init__(
        self,
        output_dir: str = "omnidrama/output",
        width: int = 1080,
        height: int = 1920,
        fps: int = 24
    ):
        self.output_dir = output_dir
        self.width = width
        self.height = height
        self.fps = fps
        self.director = DirectorAgent()
        self.tts = TTSEngine()
        self.compositor = VideoCompositor(width=width, height=height, fps=fps)

    def _generate_placeholder_frame(self, shot: Shot, out_path: str):
        """生成带影视排版与氛围的 2.5D 分镜基底图（用于未接入外置 GPU 生图时的极速渲染与验证）."""
        img = Image.new("RGB", (self.width, self.height), color=(18, 20, 28))
        draw = ImageDraw.Draw(img)

        # 绘制背景装饰与景别标识
        draw.rectangle([40, 80, self.width - 40, self.height - 80], outline=(60, 80, 120), width=4)

        # 镜头信息徽标
        badge_text = f"SHOT #{shot.shot_id:02d} | {shot.shot_scale.value.upper()} | {shot.camera_motion.value.upper()}"
        draw.text((80, 120), badge_text, fill=(0, 200, 255))

        # 说话人与台词区域
        speaker_box = f"【{shot.speaker}】"
        draw.text((80, self.height // 2 - 100), speaker_box, fill=(255, 215, 0))

        # 绘制视觉提示词说明
        prompt_snippet = f"Visual Prompt: {shot.visual_prompt[:60]}..."
        draw.text((80, self.height - 240), prompt_snippet, fill=(160, 160, 170))

        img.save(out_path, quality=95)
        return out_path

    async def run_from_text(
        self,
        story_text: str,
        title: str = "短剧第一集",
        genre: str = "都市热血",
        burn_subtitles: bool = False
    ) -> Dict[str, Any]:
        """端到端全自动运行：剧本拆解 ➔ 语音合成 ➔ 分镜生成 ➔ 2.5D 运镜渲染 ➔ 导出成片."""
        project_dir = os.path.join(self.output_dir, title)
        shots_dir = os.path.join(project_dir, "shots")
        os.makedirs(shots_dir, exist_ok=True)

        # 1. 导演拆解
        project = self.director.breakdown_story_offline(story_text, title=title, genre=genre)

        clip_paths = []
        for shot in project.shots:
            # 2. 语音生成
            audio_path = os.path.join(shots_dir, f"shot_{shot.shot_id:03d}.mp3")
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

            # 3. 画面资产（若未挂载生图模型，自动生成电影排版图）
            img_path = os.path.join(shots_dir, f"shot_{shot.shot_id:03d}.jpg")
            if not os.path.exists(img_path):
                self._generate_placeholder_frame(shot, img_path)
            shot.image_path = img_path

            # 4. 单镜头 2.5D 动态运镜渲染
            clip_path = os.path.join(shots_dir, f"shot_{shot.shot_id:03d}.mp4")
            self.compositor.render_shot(
                image_path=shot.image_path,
                audio_path=shot.audio_path,
                camera_motion=shot.camera_motion,
                output_path=clip_path
            )
            clip_paths.append(clip_path)

        # 5. 生成 SRT 字幕文件
        srt_path = os.path.join(project_dir, f"{title}.srt")
        self.tts.generate_srt(project.shots, srt_path)

        # 6. 拼接完整成片
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

"""OmniDrama 2.5D 影视运镜与视频合成器 (基于 FFmpeg)."""
import os
import subprocess
import json
import tempfile
from pathlib import Path
from typing import List, Optional
from omnidrama.schemas.drama_schema import CameraMotionEnum


class VideoCompositor:
    def __init__(self, width: int = 1080, height: int = 1920, fps: int = 24):
        self.width = width
        self.height = height
        self.fps = fps
        self.config_path = Path(__file__).parent.parent / "config" / "camera_motions.json"
        self.motions_map = {}
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.motions_map = data.get("camera_motions", {})

    def get_audio_duration(self, audio_path: str) -> float:
        """获取精确音频时长."""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ]
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True
        )
        return float(res.stdout.strip())

    def build_video_filter(self, motion: CameraMotionEnum, total_frames: int) -> str:
        """构造针对指定运镜的 FFmpeg 视频滤镜表达式."""
        motion_key = motion.value if isinstance(motion, CameraMotionEnum) else str(motion)

        if motion_key == "shake":
            # 镜头颤抖/震撼滤镜：先略微放大，再用正弦波平移坐标
            return f"scale={self.width+40}:{self.height+40},crop={self.width}:{self.height}:20+sin(n*1.5)*10:20+cos(n*2.0)*10"

        if motion_key == "zoom_in":
            return f"scale=-2:{self.height*2},zoompan=z='min(zoom+0.0015,1.25)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s={self.width}x{self.height}:fps={self.fps}"

        if motion_key == "zoom_out":
            return f"scale=-2:{self.height*2},zoompan=z='if(lte(zoom,1.0),1.25,max(1.001,zoom-0.0015))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s={self.width}x{self.height}:fps={self.fps}"

        if motion_key == "pan_left":
            return f"scale=-2:{self.height*2},zoompan=z=1.15:x='if(lte(on,1),(iw-iw/zoom),max(0,(iw-iw/zoom)*(1-on/{total_frames})))':y='(ih-ih/zoom)/2':d={total_frames}:s={self.width}x{self.height}:fps={self.fps}"

        if motion_key == "pan_right":
            return f"scale=-2:{self.height*2},zoompan=z=1.15:x='(iw-iw/zoom)*(on/{total_frames})':y='(ih-ih/zoom)/2':d={total_frames}:s={self.width}x{self.height}:fps={self.fps}"

        # 默认静态
        return f"scale={self.width}:{self.height}:force_original_aspect_ratio=increase,crop={self.width}:{self.height}"

    def render_shot(
        self,
        image_path: str,
        audio_path: str,
        camera_motion: CameraMotionEnum,
        output_path: str
    ) -> str:
        """为单张分镜静图注入 2.5D 电影级运镜并与配音音轨合成单镜头 MP4."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        duration = self.get_audio_duration(audio_path)
        total_frames = max(1, int(round(duration * self.fps)))

        vf_expr = self.build_video_filter(camera_motion, total_frames)

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", image_path,
            "-i", audio_path,
            "-vf", vf_expr,
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-t", f"{duration:.3f}",
            "-shortest",
            output_path
        ]

        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg render shot failed:\n{res.stderr}")

        return output_path

    def concatenate_clips(self, clip_paths: List[str], output_path: str) -> str:
        """无损将多个分镜视频片段拼接为完整短剧成片."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            concat_txt = f.name
            for p in clip_paths:
                # 兼容 Windows 路径反斜杠
                escaped = os.path.abspath(p).replace("\\", "/")
                f.write(f"file '{escaped}'\n")

        try:
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_txt,
                "-c", "copy",
                output_path
            ]
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            if res.returncode != 0:
                raise RuntimeError(f"FFmpeg concatenate failed:\n{res.stderr}")
        finally:
            if os.path.exists(concat_txt):
                os.remove(concat_txt)

        return output_path

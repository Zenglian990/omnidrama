"""OmniDrama 2.5D 影视运镜与双层字幕视频合成器 (基于 FFmpeg - 运镜与字幕分离架构)."""
import os
import subprocess
import json
import tempfile
from pathlib import Path
try:
    from omnidrama.schemas.drama_schema import CameraMotionEnum
except ImportError:
    from schemas.drama_schema import CameraMotionEnum


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
            return f"scale={self.width+40}:{self.height+40},crop={self.width}:{self.height}:20+sin(n*1.5)*10:20+cos(n*2.0)*10"

        if motion_key == "zoom_in":
            return f"scale=-2:{self.height*2},zoompan=z='min(zoom+0.0015,1.25)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s={self.width}x{self.height}:fps={self.fps}"

        if motion_key == "zoom_out":
            return f"scale=-2:{self.height*2},zoompan=z='if(lte(zoom,1.0),1.25,max(1.001,zoom-0.0015))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s={self.width}x{self.height}:fps={self.fps}"

        if motion_key == "pan_left":
            return f"scale=-2:{self.height*2},zoompan=z=1.15:x='if(lte(on,1),(iw-iw/zoom),max(0,(iw-iw/zoom)*(1-on/{total_frames})))':y='(ih-ih/zoom)/2':d={total_frames}:s={self.width}x{self.height}:fps={self.fps}"

        if motion_key == "pan_right":
            return f"scale=-2:{self.height*2},zoompan=z=1.15:x='(iw-iw/zoom)*(on/{total_frames})':y='(ih-ih/zoom)/2':d={total_frames}:s={self.width}x{self.height}:fps={self.fps}"

        return f"scale={self.width}:{self.height}:force_original_aspect_ratio=increase,crop={self.width}:{self.height}"

    def render_shot(
        self,
        image_path: str,
        audio_path: str,
        camera_motion: CameraMotionEnum,
        output_path: str,
        subtitle_overlay_path: Optional[str] = None
    ) -> str:
        """为单张分镜原画注入 2.5D 电影级运镜，并在顶层叠加固定不动的透明字幕层."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        duration = self.get_audio_duration(audio_path)
        total_frames = max(1, int(round(duration * self.fps)))

        vf_expr = self.build_video_filter(camera_motion, total_frames)

        if subtitle_overlay_path and os.path.exists(subtitle_overlay_path):
            filter_complex = (
                f"[0:v]{vf_expr}[bg];"
                f"[1:v]scale={self.width}:{self.height}[sub];"
                f"[bg][sub]overlay=0:0[vout]"
            )
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", image_path,
                "-i", subtitle_overlay_path,
                "-i", audio_path,
                "-filter_complex", filter_complex,
                "-map", "[vout]",
                "-map", "2:a:0",
                "-c:v", "libx264",
                "-tune", "stillimage",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-t", f"{duration:.3f}",
                "-shortest",
                output_path
            ]
        else:
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

    def render_live_actor_shot(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        subtitle_overlay_path: Optional[str] = None
    ) -> str:
        """生成『真人演员活化』专属镜头：聚焦人物面部特写 + 拟真呼吸律动 + 说话声波光影脉动."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        duration = self.get_audio_duration(audio_path)
        total_frames = max(1, int(round(duration * self.fps)))

        # 面部特写构图 + 拟真胸腔呼吸起伏与微晃动 + 声波微光脉动
        live_vf = (
            f"scale=-2:{self.height*2},"
            f"zoompan=z='1.32+0.025*sin(on*0.26)':"
            f"x='iw/2-(iw/zoom/2)+sin(on*0.13)*8':"
            f"y='ih*0.16+cos(on*0.26)*10':"
            f"d={total_frames}:s={self.width}x{self.height}:fps={self.fps},"
            f"eq=contrast=1.10:saturation=1.18:brightness=0.015"
        )

        if subtitle_overlay_path and os.path.exists(subtitle_overlay_path):
            filter_complex = (
                f"[0:v]{live_vf}[bg];"
                f"[1:v]scale={self.width}:{self.height}[sub];"
                f"[bg][sub]overlay=0:0[vout]"
            )
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", image_path,
                "-i", subtitle_overlay_path,
                "-i", audio_path,
                "-filter_complex", filter_complex,
                "-map", "[vout]",
                "-map", "2:a:0",
                "-c:v", "libx264",
                "-tune", "stillimage",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-t", f"{duration:.3f}",
                "-shortest",
                output_path
            ]
        else:
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", image_path,
                "-i", audio_path,
                "-vf", live_vf,
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
            raise RuntimeError(f"FFmpeg render live actor shot failed:\n{res.stderr}")

        return output_path

    def render_video_shot(
        self,
        video_clip_path: str,
        audio_path: str,
        output_path: str,
        subtitle_overlay_path: Optional[str] = None
    ) -> str:
        """将动态视频素材 (如 Pexels 实拍视频或图生视频片段) 与配音及固定透明字幕层合成为单镜 MP4."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        duration = self.get_audio_duration(audio_path)

        scale_crop = f"scale={self.width}:{self.height}:force_original_aspect_ratio=increase,crop={self.width}:{self.height},fps={self.fps}"

        if subtitle_overlay_path and os.path.exists(subtitle_overlay_path):
            filter_complex = (
                f"[0:v]{scale_crop}[bg];"
                f"[1:v]scale={self.width}:{self.height}[sub];"
                f"[bg][sub]overlay=0:0[vout]"
            )
            cmd = [
                "ffmpeg", "-y",
                "-stream_loop", "-1", "-i", video_clip_path,
                "-i", subtitle_overlay_path,
                "-i", audio_path,
                "-filter_complex", filter_complex,
                "-map", "[vout]",
                "-map", "2:a:0",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-t", f"{duration:.3f}",
                "-shortest",
                output_path
            ]
        else:
            cmd = [
                "ffmpeg", "-y",
                "-stream_loop", "-1", "-i", video_clip_path,
                "-i", audio_path,
                "-vf", scale_crop,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "libx264",
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
            raise RuntimeError(f"FFmpeg render video shot failed:\n{res.stderr}")

        return output_path

    def concatenate_clips(self, clip_paths: List[str], output_path: str) -> str:
        """无损将多个分镜视频片段拼接为完整短剧成片."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            concat_txt = f.name
            for p in clip_paths:
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

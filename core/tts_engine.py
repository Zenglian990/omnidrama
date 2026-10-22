"""OmniDrama 语音与字幕引擎 (基于微软 Edge-TTS)."""
import asyncio
import os
import json
import subprocess
from pathlib import Path
from typing import List, Optional

# Windows aiodns 补丁：强制使用 ThreadedResolver 避免 DNS 查询失败
import aiohttp.resolver
import aiohttp.connector
aiohttp.connector.DefaultResolver = aiohttp.resolver.ThreadedResolver

import edge_tts
import edge_tts.constants
import edge_tts.communicate
import edge_tts.drm
from datetime import timezone as _tz
from email.utils import parsedate_to_datetime as _parsedate_to_datetime
try:
    from omnidrama.schemas.drama_schema import Shot
except ImportError:
    from schemas.drama_schema import Shot

# 2026-10 微软 Edge-TTS 403 修复补丁：
# 旧版 speech.platform.bing.com WebSocket 合成端点已于 2026 年 10 月拒绝请求 (403)，
# 切换至 Edge 155+ 最新官方网关 api.msedgeservices.com，并修复中文 Windows 下 Date Header 解析失败问题。
_NEW_WSS_URL = (
    "wss://api.msedgeservices.com/tts/cognitiveservices/websocket/v1"
    f"?Ocp-Apim-Subscription-Key={edge_tts.constants.TRUSTED_CLIENT_TOKEN}"
)
edge_tts.constants.WSS_URL = _NEW_WSS_URL
edge_tts.communicate.WSS_URL = _NEW_WSS_URL


def _safe_parse_rfc2616_date(date: str) -> Optional[float]:
    try:
        parsed = _parsedate_to_datetime(date)
    except (TypeError, ValueError, IndexError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_tz.utc)
    return parsed.timestamp()


edge_tts.drm.DRM.parse_rfc2616_date = staticmethod(_safe_parse_rfc2616_date)


class TTSEngine:
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = str(Path(__file__).parent.parent / "config" / "voices.json")
        self.voices_map = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.voices_map = data.get("voices", {})

    def resolve_voice(self, speaker: str) -> tuple[str, str, str]:
        """根据角色名解析音色、语速与音调."""
        default_voice = "zh-CN-YunxiNeural"
        default_rate = "+0%"
        default_pitch = "+0Hz"

        if speaker in self.voices_map:
            v_info = self.voices_map[speaker]
            return v_info.get("voice_id", default_voice), v_info.get("rate", default_rate), v_info.get("pitch", default_pitch)
        
        if any(w in speaker for w in ["女", "妻", "妹", "小姐", "妈", "娘"]):
            v_info = self.voices_map.get("女主角", {})
            return v_info.get("voice_id", "zh-CN-XiaoxiaoNeural"), v_info.get("rate", default_rate), v_info.get("pitch", default_pitch)
        if any(w in speaker for w in ["老", "爷", "宗主", "师父", "长者"]):
            v_info = self.voices_map.get("成熟大叔", {})
            return v_info.get("voice_id", "zh-CN-YunyangNeural"), v_info.get("rate", default_rate), v_info.get("pitch", default_pitch)
        if any(w in speaker for w in ["反派", "贼", "魔", "恶", "霸"]):
            v_info = self.voices_map.get("反派男配", {})
            return v_info.get("voice_id", "zh-CN-YunjianNeural"), v_info.get("rate", default_rate), v_info.get("pitch", default_pitch)
        
        return default_voice, default_rate, default_pitch

    async def generate_speech(
        self,
        text: str,
        voice: Optional[str] = None,
        output_path: str = "output.mp3",
        rate: str = "+0%",
        pitch: str = "+0Hz"
    ) -> float:
        """调用 Edge-TTS 生成 MP3 音频，并返回音频时长（秒）."""
        if not voice:
            voice = "zh-CN-YunxiNeural"

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        try:
            communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
            await communicate.save(output_path)
        except Exception:
            pass

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            calc_dur = max(1.5, len(text) * 0.25)
            subprocess.run([
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "anullsrc=r=44100:cl=mono",
                "-t", f"{calc_dur:.2f}",
                "-acodec", "libmp3lame",
                output_path
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        duration = self.get_audio_duration(output_path)
        return duration

    def get_audio_duration(self, audio_path: str) -> float:
        """通过 ffprobe 获取精确音频秒数."""
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                audio_path
            ]
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=True
            )
            duration = float(result.stdout.strip())
            return duration
        except Exception:
            return 3.0

    def format_timestamp(self, seconds: float) -> str:
        """将浮点秒数格式化为 SRT 时间格式: 00:00:00,000."""
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int(round((seconds - int(seconds)) * 1000))
        return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"

    def generate_srt(self, shots: List[Shot], srt_path: str) -> str:
        """根据各镜头时长自动生成精准对齐的 SRT 字幕."""
        os.makedirs(os.path.dirname(os.path.abspath(srt_path)), exist_ok=True)
        current_time = 0.0
        lines = []

        for idx, shot in enumerate(shots, start=1):
            dur = shot.duration_seconds if shot.duration_seconds and shot.duration_seconds > 0 else 3.0
            start_str = self.format_timestamp(current_time)
            end_str = self.format_timestamp(current_time + dur)

            speaker_tag = f"【{shot.speaker}】" if shot.speaker and shot.speaker != "旁白" else ""
            dialogue_text = f"{speaker_tag}{shot.dialogue.strip()}"

            lines.append(f"{idx}")
            lines.append(f"{start_str} --> {end_str}")
            lines.append(dialogue_text)
            lines.append("")

            current_time += dur

        srt_content = "\n".join(lines)
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        return srt_path

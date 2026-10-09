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
from omnidrama.schemas.drama_schema import Shot


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
        communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
        await communicate.save(output_path)

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

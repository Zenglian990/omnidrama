"""OmniDrama 电影级多轨混音引擎 (Audio Mixer Engine).

提供三轨合一影视级声音体系：
Track 1: 人声台词轨 (Voice)
Track 2: 拟音音效轨 (SFX Foley - 暴雨、惊雷、重击、刀剑)
Track 3: 电影原声配乐轨 (BGM - 悬疑铺垫、绝地反击战歌，含说话自动避让 Ducking)
"""
import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional


class AudioMixer:
    def __init__(self, assets_dir: Optional[str] = None):
        if assets_dir is None:
            self.assets_dir = Path(__file__).parent.parent / "assets"
        else:
            self.assets_dir = Path(assets_dir)
        self.sfx_dir = self.assets_dir / "sfx"
        self.bgm_dir = self.assets_dir / "bgm"
        self.sfx_dir.mkdir(parents=True, exist_ok=True)
        self.bgm_dir.mkdir(parents=True, exist_ok=True)

    def ensure_sfx_library(self) -> Dict[str, str]:
        """合成并缓存电影拟音音效库 (SFX)."""
        library = {
            "rain": str(self.sfx_dir / "rain_ambient.wav"),
            "thunder": str(self.sfx_dir / "thunder_blast.wav"),
            "impact_boom": str(self.sfx_dir / "impact_boom.wav"),
            "sword_clash": str(self.sfx_dir / "sword_clash.wav"),
            "whoosh": str(self.sfx_dir / "whoosh_tension.wav")
        }

        # 1. 暴雨环境音 (Rain Ambience)
        if not os.path.exists(library["rain"]):
            cmd = [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "anoisesrc=c=white:a=0.035,bandpass=f=1200:w=1400",
                "-t", "120", "-c:a", "pcm_s16le", library["rain"]
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # 2. 惊雷劈裂 (Thunder Blast)
        if not os.path.exists(library["thunder"]):
            cmd = [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "anoisesrc=c=pink:a=0.9,lowpass=f=220,volume=4.0",
                "-af", "afade=t=in:ss=0:d=0.04,afade=t=out:st=1.2:d=2.0",
                "-t", "3.2", "-c:a", "pcm_s16le", library["thunder"]
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # 3. 影视重低音轰鸣 (Cinematic Sub-bass Boom)
        if not os.path.exists(library["impact_boom"]):
            cmd = [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "sine=f=55:d=2.5,volume=2.5",
                "-af", "afade=t=out:st=0.3:d=2.2",
                "-t", "2.5", "-c:a", "pcm_s16le", library["impact_boom"]
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # 4. 金铁交鸣 / 拔剑 (Sword Clash)
        if not os.path.exists(library["sword_clash"]):
            cmd = [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "sine=f=2400:d=1.5,volume=1.2",
                "-af", "afade=t=out:st=0.1:d=1.4,chorus=0.7:0.9:55:0.4:0.25:2",
                "-t", "1.5", "-c:a", "pcm_s16le", library["sword_clash"]
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # 5. 悬疑转场疾风呼啸 (Whoosh)
        if not os.path.exists(library["whoosh"]):
            cmd = [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "anoisesrc=c=brown:a=0.5,bandpass=f=400:w=300",
                "-af", "afade=t=in:ss=0:d=0.3,afade=t=out:st=0.6:d=0.9,volume=2.0",
                "-t", "1.5", "-c:a", "pcm_s16le", library["whoosh"]
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        return library

    def generate_bgm_track(self, bgm_type: str, duration: float, output_path: str) -> str:
        """根据剧情阶段生成影视原声配乐 (支持读取 assets/bgm 真实配乐，或合成电影感弦乐和声+心跳律动)."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        # 优先检查 assets/bgm 目录下是否有真实 MP3/WAV 配乐素材
        existing_bgm = list(self.bgm_dir.glob(f"{bgm_type}.*")) or list(self.bgm_dir.glob("*.mp3"))
        if existing_bgm:
            src_bgm = str(existing_bgm[0])
            cmd = [
                "ffmpeg", "-y",
                "-stream_loop", "-1",
                "-i", src_bgm,
                "-af", f"afade=t=in:ss=0:d=1.5,afade=t=out:st={max(0.5, duration - 2.0):.2f}:d=2.0,volume=0.32",
                "-t", f"{duration:.3f}",
                "-ar", "44100", "-ac", "2",
                "-c:a", "pcm_s16le",
                output_path
            ]
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0 and os.path.exists(output_path):
                return output_path

        # 使用 aevalsrc 合成柔和的 A小调/D小调电影大提琴和声铺底 + 史诗定音鼓律动 (消除刺耳单频正弦波)
        if bgm_type == "epic_battle":
            expr = (
                "0.12*sin(2*PI*110*t)*(0.6+0.4*sin(2*PI*0.5*t))"
                "+0.09*sin(2*PI*164.81*t)*(0.7+0.3*cos(2*PI*0.25*t))"
                "+0.07*sin(2*PI*220*t)*(0.5+0.5*sin(2*PI*0.33*t))"
                "+0.05*sin(2*PI*130.81*t)"
                "+0.14*sin(2*PI*65*t)*exp(-4*mod(t,1.5))"
            )
            af_chain = (
                f"lowpass=f=680,aecho=0.8:0.88:60:0.35,"
                f"afade=t=in:ss=0:d=1.2,afade=t=out:st={max(0.5, duration - 1.8):.2f}:d=1.8,volume=0.38"
            )
        else:
            expr = (
                "0.10*sin(2*PI*98*t)*(0.6+0.4*sin(2*PI*0.25*t))"
                "+0.08*sin(2*PI*146.83*t)*(0.6+0.4*cos(2*PI*0.2*t))"
                "+0.06*sin(2*PI*196*t)"
                "+0.10*sin(2*PI*55*t)*exp(-3.5*mod(t,2.0))"
            )
            af_chain = (
                f"lowpass=f=520,aecho=0.8:0.85:90:0.3,"
                f"afade=t=in:ss=0:d=1.2,afade=t=out:st={max(0.5, duration - 1.8):.2f}:d=1.8,volume=0.30"
            )

        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"aevalsrc='{expr}':s=44100:d={duration:.3f}",
            "-af", af_chain,
            "-t", f"{duration:.3f}",
            "-ar", "44100", "-ac", "2",
            "-c:a", "pcm_s16le",
            output_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return output_path

    def mix_soundtrack(
        self,
        voice_track: str,
        total_duration: float,
        sfx_cues: List[Dict[str, Any]],
        bgm_type: str = "epic_battle",
        output_path: str = "final_master.wav"
    ) -> str:
        """三轨融合混音：自动对齐时间线，含人声对白自动避让 (Sidechain Ducking)，将台词、拟音和配乐融合成母带音轨."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        sfx_lib = self.ensure_sfx_library()

        # 生成配乐轨
        bgm_file = os.path.join(os.path.dirname(output_path), "temp_bgm.wav")
        self.generate_bgm_track(bgm_type, total_duration, bgm_file)

        # 构造 FFmpeg 多输入与复杂滤镜
        inputs = ["-i", voice_track, "-i", bgm_file]
        filter_complex = [
            "[0:a]aresample=44100,pan=stereo|c0=c0|c1=c0,asplit=2[voice_main][voice_sc]",
            "[1:a]aresample=44100,pan=stereo|c0=c0|c1=c1[bgm_raw]",
            "[bgm_raw][voice_sc]sidechaincompress=threshold=0.03:ratio=5:attack=40:release=400[bgm_ducked]"
        ]
        mix_inputs = ["[voice_main]", "[bgm_ducked]"]

        # 处理各音效点 (SFX Cues)
        input_idx = 2
        for cue in sfx_cues:
            sfx_name = cue.get("name", "thunder")
            sfx_path = sfx_lib.get(sfx_name, sfx_lib["thunder"])
            delay_ms = int(cue.get("time_seconds", 0.0) * 1000)
            vol = min(0.45, float(cue.get("volume", 0.45)))

            inputs.extend(["-i", sfx_path])
            filter_complex.append(
                f"[{input_idx}:a]aresample=44100,adelay={delay_ms}|{delay_ms},volume={vol}[sfx_{input_idx}]"
            )
            mix_inputs.append(f"[sfx_{input_idx}]")
            input_idx += 1

        # 混音合并所有音轨，确保人声清晰突出
        mix_str = "".join(mix_inputs)
        filter_complex.append(
            f"{mix_str}amix=inputs={len(mix_inputs)}:duration=first:dropout_transition=2:normalize=0,alimiter=limit=0.95[aout]"
        )

        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", ";".join(filter_complex),
            "-map", "[aout]",
            "-t", f"{total_duration:.3f}",
            "-ar", "44100", "-ac", "2",
            "-c:a", "pcm_s16le",
            output_path
        ]

        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        if res.returncode != 0:
            raise RuntimeError(f"Audio mixing failed:\n{res.stderr}")

        if os.path.exists(bgm_file):
            try:
                os.remove(bgm_file)
            except Exception:
                pass

        return output_path

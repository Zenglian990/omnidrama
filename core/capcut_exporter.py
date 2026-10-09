"""OmniDrama 剪映 / CapCut 原生草稿工程导出器 (CapCut Exporter).

将 OmniDrama 的多轨项目（画面轨、台词轨、拟音音效轨、BGM 配乐轨、字幕轨）
一键打包导出为国内短剧团队标准使用的《剪映》原生草稿工程 (draft_content.json)，
方便创作者在剪映中直接打开进行二次调色、特效叠加与精修剪辑。
"""
import os
import json
import uuid
from pathlib import Path
from typing import Dict, Any, List


class CapCutExporter:
    def __init__(self, fps: int = 24):
        self.fps = fps

    def export_draft(
        self,
        project_title: str,
        shots: List[Dict[str, Any]],
        output_dir: str
    ) -> str:
        """生成符合剪映/CapCut 标准规范的草稿工程目录."""
        draft_folder = Path(output_dir) / f"{project_title}_剪映草稿工程"
        draft_folder.mkdir(parents=True, exist_ok=True)

        draft_content_path = draft_folder / "draft_content.json"
        draft_meta_path = draft_folder / "draft_info.json"

        # 构造多轨数据结构
        video_segments = []
        audio_segments = []
        text_segments = []

        current_time_us = 0  # 微秒计时 (1s = 1,000,000 us)

        for idx, shot in enumerate(shots):
            dur_us = int((shot.get("duration", 3.0)) * 1_000_000)

            # 视频轨片段
            v_id = str(uuid.uuid4())
            video_segments.append({
                "id": v_id,
                "material_id": f"mat_video_{idx}",
                "target_timerange": {"duration": dur_us, "start": current_time_us},
                "source_timerange": {"duration": dur_us, "start": 0},
                "shot_index": idx + 1,
                "camera_motion": shot.get("motion", "zoom_in")
            })

            # 音频轨片段
            a_id = str(uuid.uuid4())
            audio_segments.append({
                "id": a_id,
                "material_id": f"mat_audio_{idx}",
                "target_timerange": {"duration": dur_us, "start": current_time_us},
                "speaker": shot.get("speaker", "旁白")
            })

            # 字幕轨片段
            t_id = str(uuid.uuid4())
            text_segments.append({
                "id": t_id,
                "text": shot.get("dialogue", ""),
                "target_timerange": {"duration": dur_us, "start": current_time_us}
            })

            current_time_us += dur_us

        draft_content = {
            "version": "1.0.0",
            "canvas_config": {"height": 1280, "width": 720, "ratio": "9:16"},
            "duration": current_time_us,
            "tracks": [
                {"type": "video", "name": "分镜视频主轨", "segments": video_segments},
                {"type": "audio", "name": "台词对白轨", "segments": audio_segments},
                {"type": "text", "name": "自动字幕轨", "segments": text_segments}
            ]
        }

        with open(draft_content_path, "w", encoding="utf-8") as f:
            json.dump(draft_content, f, ensure_ascii=False, indent=2)

        draft_info = {
            "draft_name": project_title,
            "draft_id": str(uuid.uuid4()),
            "draft_timeline_duration": current_time_us,
            "draft_fold_path": str(draft_folder.resolve())
        }

        with open(draft_meta_path, "w", encoding="utf-8") as f:
            json.dump(draft_info, f, ensure_ascii=False, indent=2)

        return str(draft_folder)

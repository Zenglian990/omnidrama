"""测试 OmniDrama 剪映/CapCut 导出器."""
import os
import json
import pytest
from omnidrama.core.capcut_exporter import CapCutExporter


def test_capcut_draft_export(tmp_path):
    exporter = CapCutExporter(fps=24)
    shots = [
        {"duration": 3.0, "motion": "zoom_in", "speaker": "旁白", "dialogue": "第一幕"},
        {"duration": 4.5, "motion": "pan_left", "speaker": "主角", "dialogue": "第二幕"}
    ]
    out_dir = str(tmp_path)
    draft_folder = exporter.export_draft("测试短剧", shots, out_dir)

    assert os.path.exists(draft_folder)
    content_file = os.path.join(draft_folder, "draft_content.json")
    info_file = os.path.join(draft_folder, "draft_info.json")

    assert os.path.exists(content_file)
    assert os.path.exists(info_file)

    with open(content_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["version"] == "1.0.0"
        assert len(data["tracks"]) == 3  # video, audio, text
        assert data["duration"] == int((3.0 + 4.5) * 1_000_000)

    with open(info_file, "r", encoding="utf-8") as f:
        meta = json.load(f)
        assert meta["draft_name"] == "测试短剧"

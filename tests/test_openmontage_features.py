"""Automated verification suite for OpenMontage-inspired v1.8.0 features in OmniDrama."""

from __future__ import annotations

from pathlib import Path
from fastapi.testclient import TestClient

from core.quality_gate import (
    score_slideshow_risk,
    auto_optimize_storyboard,
    verify_rendered_video,
)
from core.cost_tracker import (
    CostTracker,
    DecisionLog,
    get_capability_envelope,
)
from core.reference_analyzer import ReferenceVideoAnalyzer
from providers.volcengine_seedance_provider import VolcengineSeedanceProvider
from providers.dashscope_provider import DashScopeProvider
from providers.kling_provider import KlingVideoProvider
from web.app import app


def test_quality_gate_slideshow_risk_and_auto_optimize():
    """Verify 6-dimension anti-slideshow scoring and automatic storyboard rhythm optimization."""
    bad_shots = [
        {"id": 1, "speaker": "叶辰", "dialogue": "第一镜平铺直叙", "motion": "PAN_LEFT", "scale": "MEDIUM_SHOT", "visual_prompt": "simple shot"},
        {"id": 2, "speaker": "林清雪", "dialogue": "第二镜同景别同运镜", "motion": "PAN_LEFT", "scale": "MEDIUM_SHOT", "visual_prompt": "simple shot"},
        {"id": 3, "speaker": "反派", "dialogue": "第三镜同景别同运镜，你们竟敢如此放肆！", "motion": "PAN_LEFT", "scale": "MEDIUM_SHOT", "visual_prompt": "simple shot"},
        {"id": 4, "speaker": "旁白", "dialogue": "第四镜依然单调重复", "motion": "PAN_LEFT", "scale": "MEDIUM_SHOT", "visual_prompt": "simple shot"},
    ]

    before = score_slideshow_risk(bad_shots)
    assert before["average"] >= 2.5
    assert len(before["critical_findings"]) >= 2

    optimized_shots, before_rep, after_rep, fixes = auto_optimize_storyboard(bad_shots, genre="都市战神")
    assert len(fixes) >= 3
    assert after_rep["average"] < before_rep["average"]
    assert after_rep["cinema_score_100"] > before_rep["cinema_score_100"]
    assert optimized_shots[0]["motion"] in ("ZOOM_IN", "SHAKE")
    assert optimized_shots[1]["motion"] != optimized_shots[0]["motion"]


def test_cost_tracker_and_decision_log(tmp_path: Path):
    """Verify CostTracker (estimate -> reserve -> reconcile -> budget warning) and DecisionLog."""
    cost_log = tmp_path / "cost_log.json"
    tracker = CostTracker(budget_total_usd=0.50, cost_log_path=cost_log)

    entry_id = tracker.estimate(tool="dashscope_image", operation="generate_shot_image", shot_id=1)
    reserved = tracker.reserve(entry_id)
    assert reserved["status"] == "reserved"
    assert reserved["reserved_usd"] > 0

    reconciled = tracker.reconcile(entry_id, succeeded=True)
    assert reconciled["status"] == "completed"
    assert reconciled["actual_usd"] > 0

    snap = tracker.cost_snapshot()
    assert snap["total_spent_usd"] > 0
    assert cost_log.exists()

    # Over-budget warning check
    big_id = tracker.estimate(tool="seedance_ark_video", operation="generate_video", estimated_usd=2.0, shot_id=2)
    big_res = tracker.reserve(big_id)
    assert big_res.get("budget_warning") is True

    # DecisionLog append-only JSON test
    dlog = DecisionLog(log_path=tmp_path / "decision_log.json")
    dlog.record(
        category="quality_gate",
        subject="storyboard_pacing",
        chosen="auto_optimize_storyboard",
        reason="Eliminated consecutive static shots",
        options_considered=["keep_original", "auto_optimize_storyboard"],
    )
    decisions = dlog.current_decisions()
    assert len(decisions) == 1
    assert decisions[0]["category"] == "quality_gate"

    envelope = get_capability_envelope()
    assert "ffmpeg_ready" in envelope
    assert "capabilities" in envelope
    assert len(envelope["capabilities"]) == 4


def test_reference_video_analyzer_and_adaptation(tmp_path: Path):
    """Verify ReferenceVideoAnalyzer on real MP4 or fallback template, plus 1:1 novel adaptation."""
    analyzer = ReferenceVideoAnalyzer(workspace_dir=tmp_path / "ref_out")

    existing_mp4s = list(Path("output").rglob("*.mp4"))
    source_arg = str(existing_mp4s[0]) if existing_mp4s else "https://www.douyin.com/video/demo"
    brief = analyzer.analyze_reference(source_arg, max_keyframes=5)

    assert "pacing_profile" in brief
    assert len(brief["scenes"]) >= 1
    assert "what_makes_it_work" in brief

    if existing_mp4s:
        v_check = verify_rendered_video(existing_mp4s[0])
        assert v_check["score"] >= 75
        assert v_check["metrics"]["width"] > 0

    novel = (
        "叶辰冷笑道：“区区林家，也敢退我的婚？”\n"
        "林清雪脸色铁青：“你不过是个寄人篱下的废物！”\n"
        "突然门外百架直升机轰鸣降落，首富跪地高呼：“恭迎龙王归位！”\n"
        "全场死寂，林家人吓得瘫软在地。"
    )
    adapted = analyzer.adapt_reference_to_novel(
        brief=brief,
        novel_text=novel,
        title="龙王退婚仿写测试",
        genre="都市战神",
    )
    assert adapted["title"] == "龙王退婚仿写测试"
    assert len(adapted["shots"]) >= 1
    assert "slideshow_risk_after" in adapted


def test_providers_job_resume_and_fastapi_endpoints(tmp_path: Path):
    """Verify job_path persistence and FastAPI OpenMontage endpoints."""
    seedance = VolcengineSeedanceProvider(api_key="test_key")
    assert seedance.is_available is True

    # Verify job_path resume short-circuit (never double-bills if task_id is already saved & active)
    fake_job = tmp_path / "shot_001_seedance_job.json"
    fake_job.write_text('{"task_id": "cgt-existing-12345", "status": "running"}', encoding="utf-8")
    resumed_id = seedance.create_generation_task(prompt="cinematic shot", job_path=fake_job)
    assert resumed_id == "cgt-existing-12345"

    dash = DashScopeProvider(api_key="")
    assert dash.is_available is False

    kling = KlingVideoProvider(access_key="test_kling_key")
    fake_kling_job = tmp_path / "shot_001_kling_job.json"
    fake_kling_job.write_text('{"task_id": "kling-existing-999", "status": "submitted"}', encoding="utf-8")
    assert kling.create_image_to_video_task("b64", "prompt", job_path=fake_kling_job) == "kling-existing-999"

    # Test FastAPI endpoints
    client = TestClient(app)

    cap_resp = client.get("/api/system/capabilities")
    assert cap_resp.status_code == 200
    cap_data = cap_resp.json()
    assert "capabilities" in cap_data

    qc_resp = client.post("/api/project/quality-check", json={"auto_fix": True, "budget_limit_usd": 5.0})
    assert qc_resp.status_code == 200
    qc_data = qc_resp.json()
    assert qc_data["status"] == "success"
    assert "after_quality" in qc_data
    assert "cost_estimate" in qc_data

    ref_resp = client.post(
        "/api/project/analyze-reference",
        json={
            "video_source": "https://www.douyin.com/video/viral_template",
            "title": "爆款仿写端到端测试剧",
            "novel_text": "叶辰一步踏出，身后十万战神齐声怒吼：恭迎尊上！林家众人瞬间面如死灰。",
            "adapt_and_save": False,
        },
    )
    assert ref_resp.status_code == 200
    ref_data = ref_resp.json()
    assert ref_data["status"] == "success"
    assert ref_data["adapted_storyboard"]["title"] == "爆款仿写端到端测试剧"
    assert len(ref_data["adapted_storyboard"]["shots"]) >= 1

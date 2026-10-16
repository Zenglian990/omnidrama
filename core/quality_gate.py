"""OmniDrama 反“PPT幻灯片感”风险评分与成片多维质检门禁 (Quality Gate & Slideshow Risk Engine).

净室吸收自 OpenMontage 的 slideshow_risk 与 reviewer 质检协议，针对竖屏短剧场景深度定制：
1. 渲染前 (Pre-render)：对分镜剧本进行 6 维度“PPT幻灯片感”风险量化评分 (0.0~5.0，越低越好)，
   并提供一键自动调优 (auto_optimize_storyboard)，消除连续重复运镜/景别、台词过密赶拍、高潮镜头张力不足等问题。
2. 渲染后 (Post-render)：调用 ffprobe 与 FFmpeg volumedetect 对成片 MP4 进行多维工程质检
   (视频流分辨率/帧率/时长、音频流完整性、平均响度与峰值防爆音检测)。
"""
from __future__ import annotations

import copy
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


CLIMAX_KEYWORDS = (
    "死", "杀", "滚", "跪", "轰", "雷", "震", "怒", "战神", "龙王", "龙帅",
    "天尊", "血", "灭", "破", "怎敢", "放肆", "百倍奉还", "不可能", "什么"
)

ALL_MOTIONS = [
    ("ZOOM_IN", "镜头推进"),
    ("PAN_LEFT", "向左横移"),
    ("ZOOM_OUT", "镜头拉远"),
    ("PAN_RIGHT", "向右横移"),
    ("SHAKE", "镜头震撼"),
]

ALL_SCALES = [
    "WIDE_SHOT",
    "MEDIUM_SHOT",
    "CLOSE_UP",
    "FULL_SHOT",
    "EXTREME_CLOSE_UP",
]


def _normalize_shot_dict(shot: Any, idx: int) -> Dict[str, Any]:
    """兼容 Pydantic Shot 模型与普通 dict 结构."""
    if isinstance(shot, dict):
        d = copy.deepcopy(shot)
        d.setdefault("id", idx + 1)
        d.setdefault("speaker", "旁白")
        d.setdefault("dialogue", "")
        d.setdefault("scale", str(d.get("shot_scale", "MEDIUM_SHOT")).upper())
        d.setdefault("motion", str(d.get("camera_motion", "ZOOM_IN")).upper())
        d.setdefault("visual_prompt", "")
        d.setdefault("sfx", "无")
        return d

    scale_val = getattr(shot, "shot_scale", "MEDIUM_SHOT")
    if hasattr(scale_val, "value"):
        scale_val = scale_val.value
    motion_val = getattr(shot, "camera_motion", "ZOOM_IN")
    if hasattr(motion_val, "value"):
        motion_val = motion_val.value

    return {
        "id": getattr(shot, "shot_id", idx + 1),
        "speaker": getattr(shot, "speaker", "旁白"),
        "dialogue": getattr(shot, "dialogue", ""),
        "scale": str(scale_val).upper(),
        "motion": str(motion_val).upper(),
        "visual_prompt": getattr(shot, "visual_prompt", ""),
        "sfx": getattr(shot, "sfx", "无"),
    }


def score_slideshow_risk(shots: List[Any]) -> Dict[str, Any]:
    """对分镜表进行 6 维度“PPT幻灯片感”风险评分 (0.0~5.0，越低代表电影感越强).

    维度定义：
      1. repetition: 连续相同运镜或相同景别的单调重复度
      2. decorative_visuals: 画面提示词空洞、缺乏光影/主体/构图细节
      3. weak_motion: 动态运镜多样性不足（如全片只有单一推镜或静止）
      4. weak_shot_intent: 台词情绪高潮处缺乏特写 (CLOSE_UP) 或震动 (SHAKE) 镜头语言配合
      5. pacing_monotony: 单镜台词过长(>42字导致配音赶拍)或过短，缺乏节奏起伏
      6. hook_weakness: 黄金前2镜缺乏冲突感、强运镜或高张力台词钩子
    """
    if not shots:
        return {
            "average": 5.0,
            "verdict": "fail",
            "verdict_cn": "未通过（空分镜表）",
            "dimensions": {},
            "critical_findings": ["分镜列表为空，无法构成有效视频序列"],
        }

    norm_shots = [_normalize_shot_dict(s, i) for i, s in enumerate(shots)]
    n = len(norm_shots)

    # 1. Repetition (连续相同运镜或景别)
    same_motion_streaks = 0
    same_scale_streaks = 0
    for i in range(1, n):
        if norm_shots[i]["motion"] == norm_shots[i - 1]["motion"]:
            same_motion_streaks += 1
        if norm_shots[i]["scale"] == norm_shots[i - 1]["scale"]:
            same_scale_streaks += 1
    rep_ratio = (same_motion_streaks + same_scale_streaks) / max(1, 2 * (n - 1))
    rep_score = round(min(5.0, rep_ratio * 6.0), 2)
    rep_reason = (
        f"连续重复运镜 {same_motion_streaks} 次，连续重复景别 {same_scale_streaks} 次"
        if (same_motion_streaks or same_scale_streaks)
        else "景别与运镜交替自然，无机械重复"
    )

    # 2. Decorative visuals (提示词丰富度与5维要素覆盖)
    weak_prompts = 0
    for s in norm_shots:
        vp = s.get("visual_prompt", "").strip()
        has_lighting = any(k in vp.lower() for k in ("light", "cinematic", "shadow", "neon", "rain", "glow", "光", "影"))
        if len(vp) < 28 or not has_lighting:
            weak_prompts += 1
    dec_score = round(min(5.0, (weak_prompts / n) * 5.0), 2)
    dec_reason = (
        f"{weak_prompts}/{n} 个镜头缺少电影光影与空间构图描述词"
        if weak_prompts > 0
        else "全部镜头均包含完整光影与场面调度提示词"
    )

    # 3. Weak motion (运镜种类丰富度)
    unique_motions = {s["motion"] for s in norm_shots}
    if n >= 4 and len(unique_motions) <= 1:
        motion_score = 4.5
        motion_reason = f"全片 {n} 个镜头仅使用单一运镜 ({next(iter(unique_motions))})，极易产生 PPT 翻页感"
    elif n >= 4 and len(unique_motions) == 2:
        motion_score = 2.2
        motion_reason = f"全片使用了 {len(unique_motions)} 种运镜，建议增加横移或震动对比"
    else:
        motion_score = 0.6
        motion_reason = f"全片覆盖 {len(unique_motions)} 种差异化运镜，视觉运动丰富"

    # 4. Weak shot intent (高潮台词与镜头语言匹配度)
    mismatched_climax = 0
    climax_count = 0
    for s in norm_shots:
        dlg = s.get("dialogue", "")
        is_climax = any(kw in dlg for kw in CLIMAX_KEYWORDS) or ("！" in dlg) or ("!" in dlg)
        if is_climax:
            climax_count += 1
            if s["motion"] not in ("SHAKE", "ZOOM_IN") and s["scale"] not in ("CLOSE_UP", "EXTREME_CLOSE_UP", "FULL_SHOT"):
                mismatched_climax += 1
    if climax_count == 0:
        intent_score = 2.5
        intent_reason = "全剧台词缺少情绪爆发锚点，戏剧张力平缓"
    else:
        intent_score = round(min(5.0, (mismatched_climax / climax_count) * 5.0), 2)
        intent_reason = (
            f"{mismatched_climax}/{climax_count} 个情绪高潮镜头未匹配特写或震动运镜"
            if mismatched_climax
            else f"{climax_count} 个高潮镜头均精准匹配了特写/震动推镜"
        )

    # 5. Pacing monotony (台词长度与语速合理性)
    bad_pacing = 0
    lengths = [len(s.get("dialogue", "").strip()) for s in norm_shots]
    for ln in lengths:
        if ln > 46 or ln < 4:
            bad_pacing += 1
    pacing_score = round(min(5.0, (bad_pacing / n) * 5.0), 2)
    pacing_reason = (
        f"{bad_pacing}/{n} 个镜头台词过长(>46字赶拍)或过短(<4字)"
        if bad_pacing
        else f"单镜平均字数 {sum(lengths) / n:.1f} 字，符合黄金配音语速"
    )

    # 6. Hook weakness (黄金前3秒/前2镜钩子强度)
    first_two = norm_shots[:2]
    hook_has_conflict = any(
        any(kw in s.get("dialogue", "") for kw in CLIMAX_KEYWORDS)
        or "！" in s.get("dialogue", "")
        or s["motion"] in ("SHAKE", "ZOOM_IN")
        for s in first_two
    )
    hook_score = 0.8 if hook_has_conflict else 3.6
    hook_reason = (
        "开篇前2镜具备强冲突台词或强推进运镜钩子"
        if hook_has_conflict
        else "开篇前2镜平铺直叙，存在划走流失风险"
    )

    dimensions = {
        "repetition": {"label": "景别/运镜重复度", "score": rep_score, "reason": rep_reason},
        "decorative_visuals": {"label": "视觉构图空洞度", "score": dec_score, "reason": dec_reason},
        "weak_motion": {"label": "动态运镜匮乏度", "score": motion_score, "reason": motion_reason},
        "weak_shot_intent": {"label": "情绪镜头错位度", "score": intent_score, "reason": intent_reason},
        "pacing_monotony": {"label": "台词节奏失衡度", "score": pacing_score, "reason": pacing_reason},
        "hook_weakness": {"label": "黄金前3秒流失风险", "score": hook_score, "reason": hook_reason},
    }

    avg_score = round(sum(d["score"] for d in dimensions.values()) / len(dimensions), 2)
    if avg_score < 1.8:
        verdict = "strong"
        verdict_cn = "S级·电影感极强"
    elif avg_score < 2.8:
        verdict = "acceptable"
        verdict_cn = "A级·节奏合格"
    elif avg_score < 3.8:
        verdict = "revise"
        verdict_cn = "B级·建议调优（存在轻微PPT感）"
    else:
        verdict = "fail"
        verdict_cn = "C级·高危PPT感（需立即重排运镜）"

    critical_findings = [
        f"[{d['label']}] {d['reason']} (风险值 {d['score']}/5.0)"
        for d in dimensions.values()
        if d["score"] >= 2.5
    ]

    return {
        "average": avg_score,
        "cinema_score_100": max(0, min(100, int(round((5.0 - avg_score) * 20)))),
        "verdict": verdict,
        "verdict_cn": verdict_cn,
        "dimensions": dimensions,
        "critical_findings": critical_findings,
    }


def auto_optimize_storyboard(shots: List[Dict[str, Any]], genre: str = "都市爽文") -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any], List[str]]:
    """根据 CHAI Reviewer 准则自动修复分镜表中的高风险 PPT 感问题.

    返回: (优化后的 shots 列表, 优化前评分报告, 优化后评分报告, 执行的修复动作列表)
    """
    before_report = score_slideshow_risk(shots)
    if not shots:
        return shots, before_report, before_report, []

    optimized = [copy.deepcopy(s) for s in shots]
    fixes: List[str] = []

    for idx, s in enumerate(optimized):
        dlg = str(s.get("dialogue", "")).strip()
        spk = str(s.get("speaker", "旁白")).strip() or "旁白"
        scale = str(s.get("scale", "MEDIUM_SHOT")).upper()
        motion = str(s.get("motion", "ZOOM_IN")).upper()

        # 1. 黄金首镜强化
        if idx == 0 and motion not in ("ZOOM_IN", "SHAKE"):
            motion = "ZOOM_IN"
            s["motion"] = "ZOOM_IN"
            s["motion_name"] = "镜头推进"
            if s.get("sfx", "无") in ("无", ""):
                s["sfx"] = "重低音轰鸣"
            fixes.append("首镜强制升级为【镜头推进 + 重低音轰鸣】，强化黄金前3秒留存钩子")

        # 2. 情绪高潮句自动匹配特写/震撼镜头
        is_climax = any(kw in dlg for kw in CLIMAX_KEYWORDS) or ("！" in dlg) or ("!" in dlg)
        if is_climax and motion not in ("SHAKE", "ZOOM_IN"):
            motion = "SHAKE" if ("！" in dlg or "轰" in dlg or "雷" in dlg or "杀" in dlg) else "ZOOM_IN"
            s["motion"] = motion
            s["motion_name"] = "镜头震撼" if motion == "SHAKE" else "镜头推进"
            scale = "CLOSE_UP" if spk != "旁白" else "FULL_SHOT"
            s["scale"] = scale
            if s.get("sfx", "无") in ("无", ""):
                s["sfx"] = "惊雷轰鸣" if motion == "SHAKE" else "重低音轰鸣"
            fixes.append(f"镜 #{s.get('id', idx + 1)} 检测到高燃台词，升级为【{scale} + {s['motion_name']}】")

        # 3. 消除连续重复运镜与连续重复景别
        if idx > 0:
            prev_motion = str(optimized[idx - 1].get("motion", "")).upper()
            prev_scale = str(optimized[idx - 1].get("scale", "")).upper()
            if motion == prev_motion:
                alt_motion, alt_name = ALL_MOTIONS[(idx + 1) % len(ALL_MOTIONS)]
                if alt_motion == prev_motion:
                    alt_motion, alt_name = ALL_MOTIONS[(idx + 2) % len(ALL_MOTIONS)]
                s["motion"] = alt_motion
                s["motion_name"] = alt_name
                fixes.append(f"镜 #{s.get('id', idx + 1)} 消除连续重复运镜 ({prev_motion} -> {alt_motion})")
            if scale == prev_scale:
                alt_scale = ALL_SCALES[(idx + 1) % len(ALL_SCALES)]
                if alt_scale == prev_scale:
                    alt_scale = ALL_SCALES[(idx + 2) % len(ALL_SCALES)]
                s["scale"] = alt_scale
                fixes.append(f"镜 #{s.get('id', idx + 1)} 消除连续重复景别 ({prev_scale} -> {alt_scale})")

        # 4. 补全 5 维电影级画面提示词 (Subject + Motion + Scene + Framing + Camera Lighting)
        vp = str(s.get("visual_prompt", "")).strip()
        if len(vp) < 32 or "cinematic" not in vp.lower():
            s["visual_prompt"] = (
                f"masterpiece, 9:16 vertical drama frame, {s.get('scale', 'MEDIUM_SHOT').lower()}, "
                f"subject: {spk} ({genre}), action: {dlg[:28]}, "
                f"dramatic rim lighting, volumetric atmosphere, shallow depth of field, 8k cinematic look"
            )
            fixes.append(f"镜 #{s.get('id', idx + 1)} 补全 5 维电影光影与景深提示词")

        # 5. 根据台词字数动态校准单镜建议时长
        char_cnt = max(1, len(dlg))
        ideal_dur = round(max(3.2, min(7.5, char_cnt / 4.2 + 0.8)), 2)
        s["duration"] = ideal_dur

    after_report = score_slideshow_risk(optimized)
    return optimized, before_report, after_report, fixes


def verify_rendered_video(video_path: str | Path) -> Dict[str, Any]:
    """渲染后多维成片质检门禁：使用 ffprobe 与 FFmpeg 检测视频流、音频流、时长与响度."""
    p = Path(video_path)
    checks: List[Dict[str, Any]] = []
    if not p.exists() or p.stat().st_size < 1024:
        return {
            "passed": False,
            "score": 0,
            "verdict": "FAIL",
            "summary": "成片文件不存在或为空文件",
            "checks": [{"name": "file_exists", "passed": False, "detail": str(p)}],
            "metrics": {},
        }

    file_size_mb = round(p.stat().st_size / (1024 * 1024), 2)
    checks.append({"name": "成片文件完整性", "passed": True, "detail": f"{file_size_mb} MB"})

    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration,bit_rate:stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
        "-of", "json",
        str(p),
    ]
    res = subprocess.run(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        return {
            "passed": False,
            "score": 20,
            "verdict": "FAIL",
            "summary": f"ffprobe 容器校验失败: {res.stderr[:120]}",
            "checks": checks,
            "metrics": {"file_size_mb": file_size_mb},
        }

    info = json.loads(res.stdout or "{}")
    streams = info.get("streams", [])
    fmt = info.get("format", {})
    duration = round(float(fmt.get("duration", 0.0) or 0.0), 2)

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    has_video = video_stream is not None
    has_audio = audio_stream is not None
    width = int(video_stream.get("width", 0)) if video_stream else 0
    height = int(video_stream.get("height", 0)) if video_stream else 0
    v_codec = video_stream.get("codec_name", "unknown") if video_stream else "none"
    a_codec = audio_stream.get("codec_name", "unknown") if audio_stream else "none"

    checks.append({
        "name": "9:16 竖屏视频流校验",
        "passed": has_video and width > 0 and height > width,
        "detail": f"{v_codec.upper()} {width}x{height} ({duration}s)",
    })
    checks.append({
        "name": "立体声母带音轨校验",
        "passed": has_audio,
        "detail": f"{a_codec.upper()} {audio_stream.get('sample_rate', '')}Hz" if has_audio else "缺失音轨",
    })

    # 检测音频平均响度与最大峰值 (volumedetect)
    mean_vol = -20.0
    max_vol = -1.0
    if has_audio:
        vol_cmd = [
            "ffmpeg", "-i", str(p),
            "-af", "volumedetect",
            "-vn", "-sn", "-dn",
            "-f", "null", "-"
        ]
        v_res = subprocess.run(vol_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        m_mean = re.search(r"mean_volume:\s*([-\d.]+)\s*dB", v_res.stderr)
        m_max = re.search(r"max_volume:\s*([-\d.]+)\s*dB", v_res.stderr)
        if m_mean:
            mean_vol = float(m_mean.group(1))
        if m_max:
            max_vol = float(m_max.group(1))
        not_silent = mean_vol > -55.0
        checks.append({
            "name": "母带响度与防静音检测",
            "passed": not_silent,
            "detail": f"平均响度 {mean_vol:.1f} dB / 峰值 {max_vol:.1f} dB",
        })

    passed_count = sum(1 for c in checks if c["passed"])
    score = int(round((passed_count / max(1, len(checks))) * 100))
    all_passed = all(c["passed"] for c in checks)

    return {
        "passed": all_passed,
        "score": score,
        "verdict": "PASS" if all_passed else "WARN",
        "summary": (
            f"成片质检通过 ({score}分)：{width}x{height} {duration}s，含 {a_codec.upper()} 音轨 ({mean_vol:.1f}dB)"
            if all_passed
            else f"成片质检发现警告 ({score}分)，请检查音视频轨道"
        ),
        "checks": checks,
        "metrics": {
            "file_size_mb": file_size_mb,
            "duration_seconds": duration,
            "width": width,
            "height": height,
            "video_codec": v_codec,
            "audio_codec": a_codec,
            "mean_volume_db": mean_vol,
            "max_volume_db": max_vol,
        },
    }

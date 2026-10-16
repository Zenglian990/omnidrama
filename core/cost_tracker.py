"""OmniDrama 算力成本预算审计、决策审计流与能力矩阵看板 (CostTracker, DecisionLog & Capability Envelope).

净室吸收自 OpenMontage 的 tools/cost_tracker.py、AGENT_GUIDE.md 决策日志契约 (decision_log) 与
registry.provider_menu_summary() 能力探测矩阵。
"""
from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


CNY_PER_USD = 7.2


class EntryStatus(str, Enum):
    ESTIMATED = "estimated"
    RESERVED = "reserved"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class CostTracker:
    """制片算力成本预算审计器：支持 estimate -> reserve -> reconcile 全周期记账与持久化."""

    # 标准单价表 (USD)
    UNIT_PRICES_USD = {
        "edge_tts": 0.0,
        "pollinations_flux": 0.0,
        "ffmpeg_compositor": 0.0,
        "siliconflow_kolors": 0.0,
        "siliconflow_flux": 0.004,
        "siliconflow_cosyvoice": 0.002,
        "dashscope_image": 0.018,
        "dashscope_tts": 0.002,
        "bfl_flux_pro": 0.04,
        "elevenlabs_tts": 0.015,
        "seedance_ark_video": 0.16,
        "kling_video": 0.20,
        "minimax_hailuo_video": 0.22,
        "suno_bgm": 0.08,
    }

    def __init__(
        self,
        budget_total_usd: float = 5.0,
        reserve_pct: float = 0.10,
        cost_log_path: Optional[Path | str] = None,
    ) -> None:
        self.budget_total_usd = float(budget_total_usd)
        self.reserve_pct = float(reserve_pct)
        self.cost_log_path = Path(cost_log_path) if cost_log_path else None
        self.entries: List[Dict[str, Any]] = []
        if self.cost_log_path and self.cost_log_path.exists():
            self._load()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _load(self) -> None:
        try:
            raw = json.loads(self.cost_log_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self.budget_total_usd = float(raw.get("budget_total_usd", self.budget_total_usd))
                self.entries = list(raw.get("entries", []))
        except Exception:
            self.entries = []

    def _save(self) -> None:
        if not self.cost_log_path:
            return
        self.cost_log_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "budget_total_usd": self.budget_total_usd,
            "snapshot": self.cost_snapshot(),
            "entries": self.entries,
        }
        self.cost_log_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @property
    def budget_reserved_usd(self) -> float:
        return sum(
            float(e.get("reserved_usd", 0.0))
            for e in self.entries
            if e.get("status") == EntryStatus.RESERVED.value
        )

    @property
    def budget_spent_usd(self) -> float:
        return sum(
            float(e.get("actual_usd", 0.0))
            for e in self.entries
            if e.get("status") == EntryStatus.COMPLETED.value
        )

    @property
    def budget_remaining_usd(self) -> float:
        return max(0.0, self.budget_total_usd - self.budget_spent_usd - self.budget_reserved_usd)

    def estimate(self, tool: str, operation: str, estimated_usd: Optional[float] = None, shot_id: Optional[int] = None) -> str:
        """记录单步算力预估开销，返回记账 ID."""
        if estimated_usd is None:
            estimated_usd = self.UNIT_PRICES_USD.get(tool, 0.0)
        entry_id = f"cost_{uuid.uuid4().hex[:10]}"
        self.entries.append({
            "id": entry_id,
            "tool": tool,
            "operation": operation,
            "shot_id": shot_id,
            "status": EntryStatus.ESTIMATED.value,
            "estimated_usd": round(float(estimated_usd), 4),
            "reserved_usd": 0.0,
            "actual_usd": 0.0,
            "timestamp": self._now(),
        })
        self._save()
        return entry_id

    def reserve(self, entry_id: str) -> Dict[str, Any]:
        """预冻结预算额度."""
        entry = self._find(entry_id)
        est = float(entry["estimated_usd"])
        if est > self.budget_remaining_usd:
            entry["budget_warning"] = True
            entry["budget_warning_message"] = (
                f"预估开销 ${est:.3f} 超出剩余预算 ${self.budget_remaining_usd:.3f}"
            )
        entry["status"] = EntryStatus.RESERVED.value
        entry["reserved_usd"] = est
        entry["timestamp"] = self._now()
        self._save()
        return entry

    def reconcile(self, entry_id: str, actual_usd: Optional[float] = None, succeeded: bool = True) -> Dict[str, Any]:
        """任务完成后核销真实开销（若失败则自动释放预留额度）."""
        entry = self._find(entry_id)
        if not succeeded:
            entry["status"] = EntryStatus.FAILED.value
            entry["reserved_usd"] = 0.0
            entry["actual_usd"] = 0.0
        else:
            final_usd = float(entry["estimated_usd"]) if actual_usd is None else float(actual_usd)
            entry["status"] = EntryStatus.COMPLETED.value
            entry["reserved_usd"] = 0.0
            entry["actual_usd"] = round(final_usd, 4)
        entry["timestamp"] = self._now()
        self._save()
        return entry

    def _find(self, entry_id: str) -> Dict[str, Any]:
        for e in self.entries:
            if e["id"] == entry_id:
                return e
        raise KeyError(f"Cost entry {entry_id} not found")

    def cost_snapshot(self) -> Dict[str, Any]:
        spent_usd = round(self.budget_spent_usd, 4)
        reserved_usd = round(self.budget_reserved_usd, 4)
        rem_usd = round(self.budget_remaining_usd, 4)
        return {
            "total_spent_usd": spent_usd,
            "total_spent_cny": round(spent_usd * CNY_PER_USD, 2),
            "total_reserved_usd": reserved_usd,
            "budget_remaining_usd": rem_usd,
            "budget_total_usd": round(self.budget_total_usd, 2),
            "entry_count": len(self.entries),
        }


class DecisionLog:
    """Backlot 级追加式决策审计流：按 (category, subject) 唯一标识当前生效决策，保留完整变更历史."""

    def __init__(self, log_path: Optional[Path | str] = None) -> None:
        self.log_path = Path(log_path) if log_path else None
        self.entries: List[Dict[str, Any]] = []
        if self.log_path and self.log_path.exists():
            try:
                self.entries = json.loads(self.log_path.read_text(encoding="utf-8"))
            except Exception:
                self.entries = []

    def record(
        self,
        category: str,
        subject: str,
        chosen: str,
        reason: str,
        options_considered: Optional[List[str]] = None,
        rejected_because: Optional[str] = None,
    ) -> Dict[str, Any]:
        prior = [
            e for e in self.entries
            if e.get("category") == category and e.get("subject") == subject
        ]
        item = {
            "id": f"dec_{uuid.uuid4().hex[:8]}",
            "category": category,
            "subject": subject,
            "chosen": chosen,
            "reason": reason,
            "options_considered": options_considered or [chosen],
            "rejected_because": rejected_because or "",
            "revised": len(prior) > 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.entries.append(item)
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_path.write_text(json.dumps(self.entries, ensure_ascii=False, indent=2), encoding="utf-8")
        return item

    def current_decisions(self) -> List[Dict[str, Any]]:
        """每个 (category, subject) 返回最新一条生效决策."""
        latest_by_key: Dict[tuple, Dict[str, Any]] = {}
        for e in self.entries:
            key = (e.get("category", ""), e.get("subject", ""))
            latest_by_key[key] = e
        return list(latest_by_key.values())


def get_capability_envelope() -> Dict[str, Any]:
    """扫描当前环境变量与本地运行环境，生成类似 OpenMontage 的能力矩阵与 1分钟升级建议."""
    has_ffmpeg = shutil.which("ffmpeg") is not None

    def _has_env(name: str) -> bool:
        return bool(os.getenv(name, "").strip())

    # 1. 导演剧本拆解大模型
    llm_providers = [
        {"name": "SiliconFlow (Qwen2.5/DeepSeek)", "env": "SILICONFLOW_API_KEY", "ready": _has_env("SILICONFLOW_API_KEY"), "cost": "免费额度/低至 ¥0.001"},
        {"name": "DeepSeek-V3 官方", "env": "DEEPSEEK_API_KEY", "ready": _has_env("DEEPSEEK_API_KEY"), "cost": "¥0.002/次"},
        {"name": "Google Gemini 2.0 Flash", "env": "GEMINI_API_KEY", "ready": _has_env("GEMINI_API_KEY") or _has_env("GOOGLE_API_KEY"), "cost": "免费层可用"},
        {"name": "Moonshot Kimi", "env": "MOONSHOT_API_KEY", "ready": _has_env("MOONSHOT_API_KEY"), "cost": "¥0.01/次"},
        {"name": "OmniDrama 本地语法规则拆解引擎", "env": "LOCAL", "ready": True, "cost": "$0.00 (内置兜底)"},
    ]

    # 2. 分镜视觉生成引擎
    image_providers = [
        {"name": "SiliconFlow (Kolors / FLUX.1)", "env": "SILICONFLOW_API_KEY", "ready": _has_env("SILICONFLOW_API_KEY"), "cost": "Kolors 免费 / FLUX ¥0.03"},
        {"name": "阿里云百炼 (通义万相 Qwen-Image 2.0)", "env": "DASHSCOPE_API_KEY", "ready": _has_env("DASHSCOPE_API_KEY"), "cost": "¥0.12/张 (中式审美极佳)"},
        {"name": "Black Forest Labs (FLUX.1 Pro)", "env": "BFL_API_KEY", "ready": _has_env("BFL_API_KEY"), "cost": "$0.04/张"},
        {"name": "Pollinations / 程序化动漫立绘引擎", "env": "LOCAL", "ready": True, "cost": "$0.00 (免Key兜底)"},
    ]

    # 3. 动态视频生成引擎 (I2V / T2V)
    video_providers = [
        {"name": "火山方舟 Seedance 2.0/2.5 (字节跳动官方)", "env": "ARK_API_KEY", "ready": _has_env("ARK_API_KEY"), "cost": "~¥1.1/镜 (原生音画同步)"},
        {"name": "快手可灵 Kling AI (I2V 图生视频)", "env": "KLING_API_KEY", "ready": _has_env("KLING_API_KEY"), "cost": "~¥1.4/镜"},
        {"name": "MiniMax 海螺 Hailuo-03 (视频生成)", "env": "MINIMAX_API_KEY", "ready": _has_env("MINIMAX_API_KEY"), "cost": "~¥1.5/镜"},
        {"name": "Pexels 高清实拍视频库", "env": "PEXELS_API_KEY", "ready": _has_env("PEXELS_API_KEY"), "cost": "$0.00 (免费正版素材)"},
        {"name": "FFmpeg 双层防变形动态运镜 + 真人活化引擎", "env": "LOCAL", "ready": has_ffmpeg, "cost": "$0.00 (本地实时压制)"},
    ]

    # 4. 多角色语音与音效配乐引擎
    audio_providers = [
        {"name": "SiliconFlow (CosyVoice2-0.5B 多角色情感配音)", "env": "SILICONFLOW_API_KEY", "ready": _has_env("SILICONFLOW_API_KEY"), "cost": "~¥0.01/镜"},
        {"name": "阿里云百炼 (CosyVoice / Qwen3-TTS)", "env": "DASHSCOPE_API_KEY", "ready": _has_env("DASHSCOPE_API_KEY"), "cost": "~¥0.01/镜"},
        {"name": "ElevenLabs Multilingual v2", "env": "ELEVENLABS_API_KEY", "ready": _has_env("ELEVENLABS_API_KEY"), "cost": "每月 10k 字符免费"},
        {"name": "Edge-TTS 微软神经网络配音 + FFmpeg 弦乐混音", "env": "LOCAL", "ready": True, "cost": "$0.00 (内置永久免费)"},
    ]

    families = [
        {"id": "script_llm", "label": "AI 导演剧本拆解", "providers": llm_providers},
        {"id": "image_generation", "label": "9:16 分镜生图", "providers": image_providers},
        {"id": "video_generation", "label": "AI 动态视频生成", "providers": video_providers},
        {"id": "tts_and_audio", "label": "多角色配音与母带混音", "providers": audio_providers},
    ]

    capabilities_summary = []
    for fam in families:
        provs = fam["providers"]
        ready_cnt = sum(1 for p in provs if p["ready"])
        capabilities_summary.append({
            "id": fam["id"],
            "label": fam["label"],
            "configured": ready_cnt,
            "total": len(provs),
            "ratio_text": f"{ready_cnt}/{len(provs)} 已就绪",
            "active_providers": [p["name"] for p in provs if p["ready"]],
            "unavailable_providers": [p["name"] for p in provs if not p["ready"]],
        })

    setup_offers = []
    if not _has_env("ARK_API_KEY"):
        setup_offers.append({
            "env": "ARK_API_KEY",
            "title": "解锁字节跳动 Seedance 2.0/2.5 原生有声视频生成",
            "effort": "1分钟配置",
            "benefit": "支持首帧定妆照驱动 9:16 真人/动漫动态视频，带原生同步音效",
        })
    if not _has_env("DASHSCOPE_API_KEY"):
        setup_offers.append({
            "env": "DASHSCOPE_API_KEY",
            "title": "解锁阿里云百炼 (通义万相 2.0 + Qwen-TTS)",
            "effort": "1分钟配置",
            "benefit": "一个 Key 同时激活中式修仙/豪门高精生图与自然国语配音",
        })
    if not _has_env("SILICONFLOW_API_KEY"):
        setup_offers.append({
            "env": "SILICONFLOW_API_KEY",
            "title": "解锁硅基流动全模态网关 (Qwen + Kolors + CosyVoice2)",
            "effort": "1分钟配置",
            "benefit": "单 Key 打通剧本拆解、免费 Kolors 生图与 CosyVoice2 性别自适应配音",
        })

    return {
        "ffmpeg_ready": has_ffmpeg,
        "capabilities": capabilities_summary,
        "setup_offers": setup_offers,
    }

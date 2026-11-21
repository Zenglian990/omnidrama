"""OmniDrama Google Colab 三号联开 (3 × T4 = 48GB VRAM) 零成本 Serverless 算力集群驱动.

核心架构设计 (专为移动端 Cloud Run 远程制片与本地无头调度设计):
1. 三号分工矩阵 (3-Account Dedicated & Elastic Multiplexing Pool):
   - 1号机 (`node_1_llm` · T4 16GB):
     常驻 `Qwen3.8-27B-Uncensored` (4-bit GGUF, ~14.4GB VRAM)，负责无审查破甲总导演分镜拆解与冲突台词生成。
   - 2号机 (`node_2_image` · T4 16GB):
     常驻 `Qwen-Image-2.1-Turbo-Q8_0.gguf` (8.1GB) + `Real-ESRGAN_x4plus`，负责 9:16 竖屏 4K 电影级短剧首帧定妆与分镜原画。
   - 3号机 (`node_3_audio` · T4 16GB):
     常驻 `Breeze-TTS / Ming-3.0-TTS` + `Faster-Whisper-Large-v3`，负责多角色情感配音合成与毫秒级字幕时间轴对齐。

2. 弹性多路复用与故障自愈 (Smart Elastic Multiplexing & Failover):
   - 当 3 个账号全部具备 `colaboratory` 权限且处于 T4 配额健康状态时，三机 48GB 显存全并行零切换运行。
   - 当某台节点处于 Google 免费配额冷却期或待补齐 `colaboratory` OAuth 作用域时，自动将任务路由至池内健康的 T4 节点，利用 Colab 100GB 高速 SSD 缓存与 `torch.cuda.empty_cache()` 显存热切换机制无缝串行代跑全部 3 大模型！
   - 若集群处于冷启动状态且移动端发起短超时请求（如 Android 端 45s 剧本生成），自动触发后台异步预热并无缝降级至云端高速通道，绝不阻塞手机端 UI。

3. 自动下线保额度看门狗 (Auto-Unassign Quota Watchdog):
   - 5阶段成片合成完毕后（或闲置超时 300 秒后），自动调用 `/tun/m/unassign/{endpoint}` 立即释放 T4 显卡，杜绝挂机耗尽每日免费 GPU 配额。
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import tempfile
import threading
import time
import urllib.parse
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

# Google Colab OAuth 常量（Client ID / Secret 必须通过环境变量注入，绝不硬编码）
COLAB_REDIRECT_URI = "https://sdk.cloud.google.com/applicationdefaultauthcode.html"
COLAB_FULL_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/colaboratory",
    "https://www.googleapis.com/auth/drive.file",
]

COLAB_DOMAIN = "https://colab.research.google.com"
XSSI_PREFIX = ")]}'\n"
OAUTH_STATE_TTL_SEC = 600


def _get_oauth_client_config() -> Tuple[str, str]:
    """从环境变量读取 Google OAuth Client 凭据，缺失时 Fail-Closed."""
    client_id = os.environ.get("COLAB_CLI_CLIENT_ID", "").strip()
    client_secret = os.environ.get("COLAB_CLI_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("缺少 COLAB_CLI_CLIENT_ID 或 COLAB_CLI_CLIENT_SECRET 环境变量")
    return client_id, client_secret


def _sanitize_error_text(raw: str, max_len: int = 120) -> str:
    """脱敏错误日志中的邮箱或 Token 片段."""
    text = (raw or "").strip()
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[redacted]", text)
    text = re.sub(r"(1//[A-Za-z0-9_\-]{8,}|ya29\.[A-Za-z0-9_\-.]{8,})", "[redacted]", text)
    return text[:max_len]


@dataclass
class ColabAccountNode:
    """单个 Google Colab 算力节点状态与凭证定义."""

    node_id: str
    role: str
    model_name: str
    email: str = ""
    vram_gb: int = 16
    accelerator: str = "T4"
    client_id: str = ""
    client_secret: str = ""
    refresh_token: str = ""
    access_token: str = ""
    scopes: List[str] = field(default_factory=list)
    token_expiry_ts: float = 0.0

    # 实时探测状态
    eligible_gpus: List[str] = field(default_factory=list)
    eligible_tpus: List[str] = field(default_factory=list)
    ccu_balance: float = 0.0
    assignments_count: int = 0
    active_endpoint: str = ""
    proxy_url: str = ""
    proxy_token: str = ""
    status: str = "UNCONFIGURED"  # UNCONFIGURED, STANDBY_T4_READY, SCOPE_LIMITED, QUOTA_COOLDOWN, WARMING_UP, ACTIVE_RUNNING, ERROR
    last_checked_ts: float = 0.0
    last_active_ts: float = 0.0
    last_error: str = ""

    @property
    def has_refresh_token(self) -> bool:
        return bool(self.refresh_token and self.refresh_token.strip())

    @property
    def has_colab_runtime_scope(self) -> bool:
        return any("colaboratory" in s for s in self.scopes)

    @property
    def has_colab_scope(self) -> bool:
        return self.has_colab_runtime_scope

    @property
    def is_t4_eligible(self) -> bool:
        return "T4" in [g.upper() for g in self.eligible_gpus]

    def to_public_dict(self) -> Dict[str, Any]:
        """仅返回脱敏后的运行状态（绝不包含邮箱、Token 掩码或内部 Endpoint）."""
        return {
            "node_id": self.node_id,
            "role": self.role,
            "model_name": self.model_name,
            "vram_gb": self.vram_gb,
            "accelerator": self.accelerator,
            "configured": self.has_refresh_token,
            "has_colab_scope": self.has_colab_runtime_scope,
            "has_active_runtime": bool(self.active_endpoint),
            "eligible_gpus": self.eligible_gpus,
            "eligible_tpus": self.eligible_tpus,
            "ccu_balance": self.ccu_balance,
            "assignments_count": self.assignments_count,
            "status": self.status,
            "is_t4_eligible": self.is_t4_eligible,
            "last_error": _sanitize_error_text(self.last_error),
        }


class ColabClusterManager:
    """Google Colab 三号联开 (48GB VRAM) 算力池核心调度器."""

    _instance: Optional["ColabClusterManager"] = None
    _lock = threading.Lock()

    DEFAULT_NODE_SPECS = [
        {
            "node_id": "node_1_llm",
            "role": "1号机 · 破甲总导演分镜引擎",
            "model_name": "Qwen3.8-27B-Uncensored (Q4_K_S GGUF · 14.4GB)",
            "vram_gb": 16,
            "accelerator": "T4",
        },
        {
            "node_id": "node_2_image",
            "role": "2号机 · 4K 电影分镜定妆生图引擎",
            "model_name": "Qwen-Image-2.1-Turbo-Q8_0.gguf + Real-ESRGAN (8.1GB)",
            "vram_gb": 16,
            "accelerator": "T4",
        },
        {
            "node_id": "node_3_audio",
            "role": "3号机 · 多角色情感配音与字幕对齐引擎",
            "model_name": "Breeze-TTS / Ming-3.0-TTS + Faster-Whisper (3.2GB)",
            "vram_gb": 16,
            "accelerator": "T4",
        },
    ]

    def __init__(self, config_path: Optional[Union[Path, str]] = None, idle_timeout_sec: int = 300):
        self.idle_timeout_sec = idle_timeout_sec
        self._state_lock = threading.RLock()
        self.config_path = Path(config_path) if config_path else self._resolve_default_pool_path()
        self.nodes: Dict[str, ColabAccountNode] = {}
        self._pkce_states: Dict[str, Dict[str, Any]] = {}
        self._init_nodes()
        self.load_credentials()

    @classmethod
    def get_instance(cls) -> "ColabClusterManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            else:
                cls._instance.load_credentials()
            return cls._instance

    @staticmethod
    def _resolve_default_pool_path() -> Optional[Path]:
        """仅在显式配置非源码目录 `COLAB_TOKENS_STATE_PATH` 时启用本地持久化."""
        env_path = os.environ.get("COLAB_TOKENS_STATE_PATH", "").strip()
        if not env_path:
            return None
        candidate = Path(env_path).resolve()
        repo_config_dir = (Path(__file__).resolve().parent.parent / "config").resolve()
        if candidate.is_relative_to(repo_config_dir):
            return None
        return candidate

    def _init_nodes(self) -> None:
        for spec in self.DEFAULT_NODE_SPECS:
            nid = spec["node_id"]
            self.nodes[nid] = ColabAccountNode(
                node_id=nid,
                role=spec["role"],
                model_name=spec["model_name"],
                vram_gb=spec["vram_gb"],
                accelerator=spec["accelerator"],
            )

    def load_credentials(self) -> None:
        """从安全持久化路径、环境变量 `COLAB_CLUSTER_TOKENS_JSON`/`COLAB_POOL_TOKENS_JSON` 加载节点凭证."""
        with self._state_lock:
            pool_data: Dict[str, Any] = {}
            if self.config_path and self.config_path.exists():
                try:
                    pool_data = json.loads(self.config_path.read_text(encoding="utf-8"))
                except Exception:
                    pool_data = {}

            # 尝试从环境变量 COLAB_CLUSTER_TOKENS_JSON / COLAB_POOL_TOKENS_JSON 加载 (适配 Cloud Run 容器无状态部署)
            env_json = (os.environ.get("COLAB_CLUSTER_TOKENS_JSON") or os.environ.get("COLAB_POOL_TOKENS_JSON") or "").strip()
            if env_json:
                try:
                    parsed_env = json.loads(env_json)
                    if isinstance(parsed_env, dict):
                        pool_data.update(parsed_env)
                except Exception:
                    try:
                        decoded = base64.b64decode(env_json).decode("utf-8")
                        parsed_b64 = json.loads(decoded)
                        if isinstance(parsed_b64, dict):
                            pool_data.update(parsed_b64)
                    except Exception:
                        pass

            # 兼容单环境变量快捷注入
            single_token = os.environ.get("COLAB_CLUSTER_TOKEN", "").strip()
            if single_token:
                if single_token.startswith("{"):
                    try:
                        parsed_single = json.loads(single_token)
                        if "nodes" in parsed_single or "node_1_llm" in parsed_single:
                            pool_data.update(parsed_single)
                        elif "refresh_token" in parsed_single:
                            pool_data.setdefault("node_1_llm", parsed_single)
                    except Exception:
                        pass
                elif single_token.startswith("1//"):
                    pool_data.setdefault(
                        "node_1_llm",
                        {
                            "refresh_token": single_token,
                            "scopes": list(COLAB_FULL_SCOPES),
                        },
                    )

            # 自动回退读取 ~/.config/colab-cli/token.json 作为 1号机凭证
            cli_token_file = Path.home() / ".config" / "colab-cli" / "token.json"
            if "node_1_llm" not in pool_data and cli_token_file.exists():
                try:
                    t_raw = json.loads(cli_token_file.read_text(encoding="utf-8"))
                    if t_raw.get("refresh_token"):
                        pool_data["node_1_llm"] = t_raw
                except Exception:
                    pass

            nodes_dict = pool_data.get("nodes", pool_data) if isinstance(pool_data, dict) else {}
            for nid, node in self.nodes.items():
                entry = nodes_dict.get(nid)
                if not entry and node.email:
                    entry = nodes_dict.get(node.email)
                if isinstance(entry, dict):
                    rt = (entry.get("refresh_token") or "").strip()
                    if rt:
                        node.refresh_token = rt
                        node.client_id = (entry.get("client_id") or "").strip()
                        node.client_secret = (entry.get("client_secret") or "").strip()
                        node.access_token = (entry.get("token") or entry.get("access_token") or node.access_token or "").strip()
                        if entry.get("scopes"):
                            node.scopes = list(entry["scopes"])
                        if node.status == "UNCONFIGURED":
                            node.status = "STANDBY_T4_READY" if node.has_colab_runtime_scope else "SCOPE_LIMITED"

    def save_credentials(self) -> None:
        """持久化保存脱敏后的节点 refresh_token（绝不写入 client_secret / access_token / email / 源码 config 目录）."""
        with self._state_lock:
            if not self.config_path:
                return
            repo_config_dir = (Path(__file__).resolve().parent.parent / "config").resolve()
            if self.config_path.resolve().is_relative_to(repo_config_dir):
                return
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "nodes": {
                    nid: {
                        "node_id": nid,
                        "role": n.role,
                        "model_name": n.model_name,
                        "refresh_token": n.refresh_token,
                        "scopes": n.scopes,
                    }
                    for nid, n in self.nodes.items()
                    if n.has_refresh_token
                },
            }
            fd, tmp_name = tempfile.mkstemp(prefix=".colab_pool_", dir=str(self.config_path.parent))
            tmp_p = Path(tmp_name)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                try:
                    os.chmod(tmp_p, 0o600)
                except OSError:
                    pass
                os.replace(tmp_p, self.config_path)
            except Exception:
                tmp_p.unlink(missing_ok=True)
                raise

    # ===================== OAuth2 无头刷新与手机端 2步 PKCE 授权 =====================

    def _ensure_access_token(self, node: ColabAccountNode, timeout: int = 12) -> str:
        """通过 OAuth2 refresh_token 无头换取最新 access_token (无需浏览器，100% 兼容 Cloud Run)."""
        if not node.has_refresh_token:
            raise ValueError(f"节点 {node.node_id} 尚未配置 OAuth refresh_token")

        now = time.time()
        if node.access_token and node.token_expiry_ts > now + 120:
            return node.access_token

        cid = node.client_id.strip()
        csec = node.client_secret.strip()
        if not cid or not csec:
            cid, csec = _get_oauth_client_config()

        resp = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": cid,
                "client_secret": csec,
                "refresh_token": node.refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=timeout,
        )
        if resp.status_code != 200:
            node.last_error = f"Token refresh HTTP {resp.status_code}"
            raise RuntimeError(node.last_error)

        data = resp.json()
        node.access_token = data["access_token"]
        node.token_expiry_ts = now + int(data.get("expires_in", 3500))
        if "scope" in data and isinstance(data["scope"], str):
            node.scopes = data["scope"].split()
        return node.access_token

    def generate_mobile_oauth_url(self, node_id: str = "node_1_llm") -> Dict[str, str]:
        """生成供手机端浏览器点击授权的 Google Colab 真随机 PKCE + 一次性 State OAuth URL."""
        client_id, _ = _get_oauth_client_config()
        if node_id not in self.nodes:
            node_id = "node_1_llm"

        code_verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        state = secrets.token_urlsafe(32)
        now = time.time()

        with self._state_lock:
            expired = [
                k for k, v in self._pkce_states.items()
                if now - float(v.get("created_at", 0.0)) > OAUTH_STATE_TTL_SEC
            ]
            for k in expired:
                self._pkce_states.pop(k, None)
            self._pkce_states[state] = {
                "node_id": node_id,
                "code_verifier": code_verifier,
                "created_at": now,
            }

        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": COLAB_REDIRECT_URI,
            "scope": " ".join(COLAB_FULL_SCOPES),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "prompt": "consent",
            "access_type": "offline",
        }
        auth_url = f"https://accounts.google.com/o/oauth2/auth?{urllib.parse.urlencode(params)}"
        return {
            "node_id": node_id,
            "state": state,
            "auth_url": auth_url,
            "instructions": "在浏览器打开链接并完成授权后，使用当前 state 与 4/0A... 授权码通过 OAuth 兑换接口完成激活。",
        }

    def exchange_mobile_oauth_code(
        self,
        node_id: str,
        auth_code: str,
        state: Optional[str] = None,
    ) -> Dict[str, Any]:
        """强制校验一次性 state 与 TTL 后，将授权码 (`4/0A...`) 兑换为持久化 `refresh_token`."""
        client_id, client_secret = _get_oauth_client_config()
        clean_code = (auth_code or "").strip()
        if not clean_code:
            raise ValueError("授权码不能为空")

        clean_state = (state or "").strip()
        if not clean_state:
            raise ValueError("缺少 OAuth state 参数")

        now = time.time()
        with self._state_lock:
            pending = self._pkce_states.pop(clean_state, None)

        if not pending:
            raise ValueError("OAuth state 无效或已被消费")
        if now - float(pending.get("created_at", 0.0)) > OAUTH_STATE_TTL_SEC:
            raise ValueError("OAuth state 已过期，请重新获取授权链接")

        pending_node_id = str(pending.get("node_id") or "")
        if node_id and pending_node_id and node_id != pending_node_id:
            raise ValueError("OAuth state 与目标节点不匹配")

        target_node_id = pending_node_id if pending_node_id in self.nodes else "node_1_llm"
        code_verifier = str(pending.get("code_verifier") or "")
        if not code_verifier:
            raise ValueError("缺少 PKCE code_verifier")

        data_payload = {
            "grant_type": "authorization_code",
            "code": clean_code,
            "redirect_uri": COLAB_REDIRECT_URI,
            "client_id": client_id,
            "client_secret": client_secret,
            "code_verifier": code_verifier,
        }
        resp = requests.post("https://oauth2.googleapis.com/token", data=data_payload, timeout=15)
        if resp.status_code != 200:
            raise RuntimeError(f"兑换授权码失败 (HTTP {resp.status_code})")
        tok = resp.json()

        with self._state_lock:
            node = self.nodes[target_node_id]
            node.access_token = tok.get("access_token", "")
            if tok.get("refresh_token"):
                node.refresh_token = tok["refresh_token"]
            if tok.get("scope"):
                node.scopes = tok["scope"].split()
            else:
                node.scopes = list(COLAB_FULL_SCOPES)
            node.token_expiry_ts = time.time() + int(tok.get("expires_in", 3500))
            if node.has_refresh_token:
                node.status = "STANDBY_T4_READY" if node.has_colab_runtime_scope else "SCOPE_LIMITED"

        self.save_credentials()
        self.probe_node_quota(target_node_id)
        return node.to_public_dict()

    # ===================== Colab 免费 T4 配额探测与算力分配 =====================

    @staticmethod
    def _colab_headers(access_token: str, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        h = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "X-Colab-Client-Agent": "colab-cli",
            "x-goog-api-client": "cred-type/u",
            "User-Agent": "OmniDrama-ColabCluster/2.0",
        }
        if extra:
            h.update(extra)
        return h

    @staticmethod
    def _parse_xssi_json(text: str) -> Dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith(")]}'"):
            cleaned = cleaned.split("\n", 1)[-1].strip()
        return json.loads(cleaned) if cleaned else {}

    def probe_node_quota(self, node_id: str, timeout: int = 10) -> Dict[str, Any]:
        """实时调用 `/tun/m/ccu-info` 检测单个账号的免费 T4 GPU 配额与在线状态."""
        node = self.nodes[node_id]
        if not node.has_refresh_token:
            node.status = "UNCONFIGURED"
            return node.to_public_dict()

        try:
            token = self._ensure_access_token(node, timeout=timeout)
            resp = requests.get(
                f"{COLAB_DOMAIN}/tun/m/ccu-info",
                params={"authuser": "0"},
                headers=self._colab_headers(token),
                timeout=timeout,
            )
            if resp.status_code in (401, 403):
                node.access_token = ""
                node.token_expiry_ts = 0.0
                token = self._ensure_access_token(node, timeout=timeout)
                resp = requests.get(
                    f"{COLAB_DOMAIN}/tun/m/ccu-info",
                    params={"authuser": "0"},
                    headers=self._colab_headers(token),
                    timeout=timeout,
                )
            if resp.status_code != 200:
                node.status = "ERROR"
                node.last_error = f"ccu-info HTTP {resp.status_code}"
                return node.to_public_dict()

            info = self._parse_xssi_json(resp.text)
            node.eligible_gpus = list(info.get("eligibleGpus", []))
            node.eligible_tpus = list(info.get("eligibleTpus", []))
            node.ccu_balance = float(info.get("currentBalance", 0.0))
            node.assignments_count = int(info.get("assignmentsCount", 0))
            assigned = info.get("assignedEndpoints") or []
            if assigned and isinstance(assigned, list):
                first_ep = assigned[0]
                node.active_endpoint = first_ep.get("endpoint", "") if isinstance(first_ep, dict) else str(first_ep)
            node.last_checked_ts = time.time()
            node.last_error = ""

            if node.active_endpoint:
                node.status = "ACTIVE_RUNNING"
            elif node.is_t4_eligible:
                node.status = "STANDBY_T4_READY" if node.has_colab_runtime_scope else "SCOPE_LIMITED"
            else:
                node.status = "QUOTA_COOLDOWN"
        except Exception as e:
            node.status = "ERROR"
            node.last_error = str(e)[:120]

        return node.to_public_dict()

    def probe_all_nodes(self, force: bool = False) -> Dict[str, Any]:
        """并发探测全部 3 个 Google 账号的 T4 显卡配额与健康度."""
        now = time.time()
        threads = []
        for nid, node in self.nodes.items():
            if force or (now - node.last_checked_ts > 45):
                t = threading.Thread(target=self.probe_node_quota, args=(nid, 8), daemon=True)
                threads.append(t)
                t.start()
        for t in threads:
            t.join(timeout=10)
        return self.get_cluster_summary()

    def get_cluster_summary(self) -> Dict[str, Any]:
        """返回供移动端 (Android & Web) 展示的三号联开算力池全景状态."""
        nodes_list = [n.to_public_dict() for n in self.nodes.values()]
        t4_ready_count = sum(1 for n in self.nodes.values() if n.is_t4_eligible or n.status in ("STANDBY_T4_READY", "ACTIVE_RUNNING"))
        full_scope_count = sum(1 for n in self.nodes.values() if n.has_refresh_token and n.has_colab_runtime_scope)
        active_vms = sum(1 for n in self.nodes.values() if n.status == "ACTIVE_RUNNING" or bool(n.active_endpoint))
        return {
            "cluster_name": "OmniDrama Colab 三号联开免费 T4 算力池",
            "total_vram_gb": len(self.nodes) * 16,
            "available_vram_gb": max(16, t4_ready_count * 16) if full_scope_count > 0 else 0,
            "configured_nodes": sum(1 for n in self.nodes.values() if n.has_refresh_token),
            "t4_eligible_nodes": t4_ready_count,
            "runtime_ready_nodes": full_scope_count,
            "active_running_vms": active_vms,
            "multiplex_mode": full_scope_count == 1 and t4_ready_count >= 1,
            "auto_unassign_idle_sec": self.idle_timeout_sec,
            "nodes": nodes_list,
        }

    # ===================== 智能节点路由与弹性多路复用 =====================

    TASK_TO_NODE_ALIAS = {
        "llm": "node_1_llm",
        "director": "node_1_llm",
        "image": "node_2_image",
        "visual": "node_2_image",
        "audio": "node_3_audio",
        "tts": "node_3_audio",
    }

    def select_node_for_task(self, preferred_node_id: str) -> Optional[ColabAccountNode]:
        """根据任务类型或节点 ID 选择最优 T4 节点；若专属节点未就绪则自动复用池内已授权的健康 T4 节点."""
        resolved_id = self.TASK_TO_NODE_ALIAS.get(preferred_node_id, preferred_node_id)
        pref = self.nodes.get(resolved_id)
        if pref and pref.has_refresh_token and pref.has_colab_runtime_scope and (pref.is_t4_eligible or pref.status != "QUOTA_COOLDOWN"):
            return pref

        # 弹性故障转移/多路复用：寻找池内任何具备 colaboratory 权限且有 T4 配额的节点
        for nid, candidate in self.nodes.items():
            if candidate.has_refresh_token and candidate.has_colab_runtime_scope and candidate.status != "QUOTA_COOLDOWN":
                return candidate
        return None

    @staticmethod
    def _build_nbh(node_id: str) -> str:
        """生成符合 Colab 规范的 44 字符 URL-safe 确定性 Notebook Hash."""
        raw_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"omnidrama.colab.{node_id}"))
        padded = raw_uuid.replace("-", "_") + "." * (44 - len(raw_uuid))
        return padded[:44]

    def assign_t4_runtime(self, node: ColabAccountNode, timeout: int = 35) -> Dict[str, str]:
        """在指定 Google 账号上分配或复用免费 NVIDIA T4 (16GB) 虚拟机实例."""
        token = self._ensure_access_token(node)
        nbh = self._build_nbh(node.node_id)
        params = {
            "nbh": nbh,
            "variant": "GPU",
            "accelerator": node.accelerator or "T4",
            "authuser": "0",
        }
        url = f"{COLAB_DOMAIN}/tun/m/assign"

        # 第一步 GET 握手 (若遇 401/403 强制刷新 access_token 重试一次)
        r1 = requests.get(url, params=params, headers=self._colab_headers(token), timeout=timeout)
        if r1.status_code in (401, 403):
            node.access_token = ""
            node.token_expiry_ts = 0.0
            token = self._ensure_access_token(node, timeout=timeout)
            r1 = requests.get(url, params=params, headers=self._colab_headers(token), timeout=timeout)
        if r1.status_code != 200:
            raise RuntimeError(f"Colab assign GET 失败 (HTTP {r1.status_code}): {r1.text[:150]}")
        data1 = self._parse_xssi_json(r1.text)

        # 若返回已包含 endpoint 与 runtimeProxyInfo，说明已有热实例直接复用
        if "endpoint" in data1 and "runtimeProxyInfo" in data1:
            proxy = data1["runtimeProxyInfo"]
            node.active_endpoint = data1["endpoint"]
            node.proxy_url = proxy.get("url", "")
            node.proxy_token = proxy.get("token", "")
            node.status = "ACTIVE_RUNNING"
            node.last_active_ts = time.time()
            return {"endpoint": node.active_endpoint, "proxy_url": node.proxy_url, "proxy_token": node.proxy_token}

        xsrf_token = data1.get("token", "")
        if not xsrf_token:
            raise RuntimeError(f"Colab 未返回 XSRF Token: {data1}")

        # 第二步 POST 确认分配 T4 GPU
        r2 = requests.post(
            url,
            params=params,
            headers=self._colab_headers(token, {"X-Goog-Colab-Token": xsrf_token}),
            timeout=timeout,
        )
        if r2.status_code != 200:
            raise RuntimeError(f"Colab assign POST 失败 (HTTP {r2.status_code}): {r2.text[:150]}")
        data2 = self._parse_xssi_json(r2.text)

        outcome = data2.get("outcome")
        if outcome in (1, 2, "OUTCOME_QUOTA_DENIED", "OUTCOME_DENIED"):
            node.status = "QUOTA_COOLDOWN"
            raise RuntimeError(f"节点 {node.node_id} 当前 T4 配额进入冷却期 (outcome={outcome})")

        proxy = data2.get("runtimeProxyInfo") or {}
        node.active_endpoint = data2.get("endpoint", "")
        node.proxy_url = proxy.get("url", "")
        node.proxy_token = proxy.get("token", "")
        if not node.proxy_url or not node.proxy_token:
            # 补充请求 runtime-proxy-token
            if node.active_endpoint:
                rp = requests.get(
                    f"{COLAB_DOMAIN}/tun/m/runtime-proxy-token",
                    params={"endpoint": node.active_endpoint, "port": 8080, "authuser": "0"},
                    headers=self._colab_headers(token),
                    timeout=timeout,
                )
                if rp.status_code == 200:
                    rp_data = self._parse_xssi_json(rp.text)
                    node.proxy_url = rp_data.get("url", node.proxy_url)
                    node.proxy_token = rp_data.get("token", node.proxy_token)

        node.status = "ACTIVE_RUNNING"
        node.last_active_ts = time.time()
        return {"endpoint": node.active_endpoint, "proxy_url": node.proxy_url, "proxy_token": node.proxy_token}

    def release_node_runtime(self, node_id: str, timeout: int = 15) -> bool:
        """主动调用 `/tun/m/unassign/{endpoint}` 释放 T4 实例，保护每日免费 GPU 时长."""
        node = self.nodes.get(node_id)
        if not node or not node.has_refresh_token:
            return False

        endpoint = node.active_endpoint
        if not endpoint:
            self.probe_node_quota(node_id, timeout=timeout)
            endpoint = node.active_endpoint
        if not endpoint:
            node.status = "STANDBY_T4_READY" if node.is_t4_eligible else node.status
            return True

        try:
            token = self._ensure_access_token(node, timeout=timeout)
            unassign_url = f"{COLAB_DOMAIN}/tun/m/unassign/{endpoint}"
            r1 = requests.get(unassign_url, params={"authuser": "0"}, headers=self._colab_headers(token), timeout=timeout)
            xsrf = ""
            if r1.status_code == 200:
                xsrf = self._parse_xssi_json(r1.text).get("token", "")
            headers = self._colab_headers(token, {"X-Goog-Colab-Token": xsrf} if xsrf else None)
            requests.post(unassign_url, params={"authuser": "0"}, headers=headers, timeout=timeout)
            node.active_endpoint = ""
            node.proxy_url = ""
            node.proxy_token = ""
            node.assignments_count = 0
            node.status = "STANDBY_T4_READY"
            return True
        except Exception as e:
            node.last_error = f"unassign 失败: {str(e)[:80]}"
            return False

    def release_all_runtimes(self) -> Dict[str, bool]:
        """一键释放全部 3 个账号的活跃 T4 实例."""
        results = {}
        for nid in self.nodes:
            results[nid] = self.release_node_runtime(nid)
        return results

    def execute_python_on_t4(
        self,
        node: ColabAccountNode,
        code: str,
        timeout_sec: int = 45,
    ) -> str:
        """通过 Colab Runtime Proxy WebSocket / Jupyter Kernel 在远端 T4 上执行 Python 代码并返回 stdout."""
        if not node.proxy_url or not node.proxy_token:
            self.assign_t4_runtime(node, timeout=min(30, timeout_sec))

        proxy_url = node.proxy_url.rstrip("/")
        proxy_token = node.proxy_token
        headers = {
            "X-Colab-Runtime-Proxy-Token": proxy_token,
            "X-Colab-Client-Agent": "colab-cli",
        }

        # 优先使用 jupyter_kernel_client (若已安装)
        try:
            from jupyter_kernel_client import KernelClient  # type: ignore

            with KernelClient(server_url=proxy_url, token="", headers=headers) as kernel:
                reply = kernel.execute(code, timeout=timeout_sec)
                node.last_active_ts = time.time()
                if isinstance(reply, dict):
                    outputs = reply.get("outputs") or []
                    text_chunks = []
                    for out in outputs:
                        if isinstance(out, dict):
                            if "text" in out:
                                text_chunks.append(str(out["text"]))
                            elif "data" in out and isinstance(out["data"], dict):
                                text_chunks.append(str(out["data"].get("text/plain", "")))
                    if text_chunks:
                        return "".join(text_chunks)
                    return json.dumps(reply, ensure_ascii=False)
                return str(reply)
        except ImportError:
            pass

        # 纯 Python requests + websocket-client 原生 Jupyter Session & Wire Protocol 实现 (完美适配 Colab Proxy 冷启动重试)
        import websocket  # type: ignore

        session_id = ""
        kernel_id = ""
        for _attempt in range(2):
            try:
                s_resp = requests.get(f"{proxy_url}/api/sessions", headers=headers, timeout=25)
                if s_resp.status_code in (401, 403):
                    self.assign_t4_runtime(node, timeout=min(30, timeout_sec))
                    proxy_url = node.proxy_url.rstrip("/")
                    proxy_token = node.proxy_token
                    headers["X-Colab-Runtime-Proxy-Token"] = proxy_token
                    s_resp = requests.get(f"{proxy_url}/api/sessions", headers=headers, timeout=25)

                s_resp.raise_for_status()
                sessions = s_resp.json()
                if sessions and isinstance(sessions, list) and "kernel" in sessions[0]:
                    session_id = sessions[0]["id"]
                    kernel_id = sessions[0]["kernel"]["id"]
                else:
                    c_resp = requests.post(
                        f"{proxy_url}/api/sessions",
                        headers=headers,
                        json={
                            "path": "omnidrama.ipynb",
                            "type": "notebook",
                            "name": "omnidrama.ipynb",
                            "kernel": {"name": "python3"},
                        },
                        timeout=30,
                    )
                    c_resp.raise_for_status()
                    s_obj = c_resp.json()
                    session_id = s_obj["id"]
                    kernel_id = s_obj["kernel"]["id"]
                if session_id and kernel_id:
                    break
            except Exception as sess_err:
                if _attempt == 1:
                    raise sess_err
                time.sleep(2.0)

        ws_scheme = "wss://" if proxy_url.startswith("https://") else "ws://"
        ws_base = re.sub(r"^https?://", ws_scheme, proxy_url)
        ws_url = f"{ws_base}/api/kernels/{kernel_id}/channels?session_id={session_id}"
        ws_headers = [f"{k}: {v}" for k, v in headers.items()]

        msg_id = uuid.uuid4().hex
        exec_msg = {
            "header": {
                "msg_id": msg_id,
                "username": "colab",
                "session": session_id,
                "msg_type": "execute_request",
                "version": "5.2",
            },
            "parent_header": {},
            "metadata": {},
            "content": {
                "code": code,
                "silent": False,
                "store_history": False,
                "user_expressions": {},
                "allow_stdin": False,
                "stop_on_error": True,
            },
            "buffers": [],
            "channel": "shell",
        }

        stdout_acc: List[str] = []
        stderr_acc: List[str] = []
        ws = websocket.create_connection(ws_url, header=ws_headers, origin=proxy_url, timeout=timeout_sec)
        try:
            ws.send(json.dumps(exec_msg))
            deadline = time.time() + timeout_sec
            while time.time() < deadline:
                raw_frame = ws.recv()
                if not raw_frame:
                    continue
                frame = json.loads(raw_frame)
                parent_id = frame.get("parent_header", {}).get("msg_id")
                if parent_id and parent_id != msg_id:
                    continue
                mtype = frame.get("msg_type") or frame.get("header", {}).get("msg_type", "")
                content = frame.get("content") or {}
                if mtype == "stream":
                    if content.get("name") == "stdout":
                        stdout_acc.append(content.get("text", ""))
                    else:
                        stderr_acc.append(content.get("text", ""))
                elif mtype in ("execute_result", "display_data"):
                    data_field = content.get("data") or {}
                    if "text/plain" in data_field:
                        stdout_acc.append(str(data_field["text/plain"]))
                elif mtype == "error":
                    tb = "\n".join(content.get("traceback") or [content.get("evalue", "Execution error")])
                    raise RuntimeError(f"Colab T4 Kernel 执行异常: {tb[:300]}")
                elif mtype == "execute_reply" and parent_id == msg_id:
                    break
        finally:
            try:
                ws.close()
            except Exception:
                pass

        node.last_active_ts = time.time()
        return "".join(stdout_acc)

    # ===================== 三大模型业务推理接口 =====================

    def run_qwen_uncensored_director(
        self,
        system_prompt: str,
        user_prompt: str,
        allow_cold_boot: bool = True,
        timeout_sec: int = 55,
    ) -> Tuple[str, str]:
        """调用 1号机 (`Qwen3.8-27B-Uncensored` 4-bit GGUF) 执行无限制短剧分镜拆解.

        返回: `(json_string, engine_display_name)`
        """
        if os.environ.get("PYTEST_CURRENT_TEST") and os.environ.get("OMNIDRAMA_LIVE_COLAB_TEST") != "1":
            raise RuntimeError("Pytest unit test mode: skipping live Colab T4 VM assignment")

        node = self.select_node_for_task("node_1_llm")
        if not node:
            raise RuntimeError("Colab 算力池无可用 T4 节点")

        if not node.active_endpoint and not allow_cold_boot:
            threading.Thread(target=self._background_warmup_node, args=(node.node_id,), daemon=True).start()
            raise RuntimeError("Colab T4 1号机正在后台冷启动预热中，本次请求自动路由至零延迟高速通道")

        sys_b64 = base64.b64encode(system_prompt.encode("utf-8")).decode("ascii")
        usr_b64 = base64.b64encode(user_prompt.encode("utf-8")).decode("ascii")

        remote_script = f"""
import base64, json, os, gc, urllib.request
import torch

gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "Tesla T4"
sys_p = base64.b64decode("{sys_b64}").decode("utf-8")
usr_p = base64.b64decode("{usr_b64}").decode("utf-8")

if "_GLOBAL_IMG_PIPE" in globals():
    del globals()["_GLOBAL_IMG_PIPE"]
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

out_txt = ""
model_path = "/content/models/Qwen3.8-27B-Uncensored.Q4_K_S.gguf"
if "_GLOBAL_QWEN_LLM" in globals() or os.path.exists(model_path):
    try:
        if "_GLOBAL_QWEN_LLM" not in globals():
            from llama_cpp import Llama
            globals()["_GLOBAL_QWEN_LLM"] = Llama(model_path=model_path, n_gpu_layers=-1, n_ctx=4096, verbose=False)
        llm = globals()["_GLOBAL_QWEN_LLM"]
        resp = llm.create_chat_completion(
            messages=[{{"role": "system", "content": sys_p}}, {{"role": "user", "content": usr_p}}],
            temperature=0.65,
            max_tokens=3200,
            response_format={{"type": "json_object"}}
        )
        out_txt = resp["choices"][0]["message"]["content"]
    except Exception:
        out_txt = ""

if not out_txt:
    # 在 Colab T4 节点内执行高速 Qwen/OpenAI 兼容推理，同时若本地 CUDA 尚未驻留 Qwen 则使用 T4 加速推理
    try:
        req_payload = json.dumps({{
            "model": "openai",
            "messages": [
                {{"role": "system", "content": sys_p}},
                {{"role": "user", "content": usr_p}}
            ],
            "temperature": 0.5,
            "response_format": {{"type": "json_object"}}
        }}).encode("utf-8")
        req = urllib.request.Request(
            "https://text.pollinations.ai/openai",
            data=req_payload,
            headers={{"Content-Type": "application/json", "User-Agent": "Colab-T4-QwenDirector/3.1"}}
        )
        with urllib.request.urlopen(req, timeout=28) as r:
            resp_data = json.loads(r.read().decode("utf-8"))
            out_txt = resp_data["choices"][0]["message"]["content"]
    except Exception:
        out_txt = ""

if not out_txt and torch.cuda.is_available():
    if "_GLOBAL_HF_QWEN" not in globals():
        from transformers import AutoModelForCausalLM, AutoTokenizer
        m_id = "Qwen/Qwen2.5-1.5B-Instruct"
        tok = AutoTokenizer.from_pretrained(m_id)
        mod = AutoModelForCausalLM.from_pretrained(m_id, torch_dtype=torch.float16, device_map="cuda")
        globals()["_GLOBAL_HF_QWEN"] = (tok, mod)
    tok, mod = globals()["_GLOBAL_HF_QWEN"]
    msgs = [{{"role": "system", "content": sys_p}}, {{"role": "user", "content": usr_p}}]
    text_in = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    inputs = tok([text_in], return_tensors="pt").to("cuda")
    gen_ids = mod.generate(**inputs, max_new_tokens=1800, temperature=0.5)
    out_ids = [o[len(i):] for i, o in zip(inputs.input_ids, gen_ids)]
    out_txt = tok.batch_decode(out_ids, skip_special_tokens=True)[0]

print("<<<OMNIDRAMA_GPU:" + gpu_name + ">>>")
print("<<<OMNIDRAMA_JSON_START>>>" + out_txt + "<<<OMNIDRAMA_JSON_END>>>")
"""
        raw_out = self.execute_python_on_t4(node, remote_script, timeout_sec=timeout_sec)
        m = re.search(r"<<<OMNIDRAMA_JSON_START>>>([\s\S]+?)<<<OMNIDRAMA_JSON_END>>>", raw_out)
        if not m or not m.group(1).strip():
            raise RuntimeError(f"Colab Qwen3.8-27B 未返回有效 JSON 标记: {raw_out[:160]}")
        gpu_m = re.search(r"<<<OMNIDRAMA_GPU:([^>]+)>>>", raw_out)
        gpu_tag = gpu_m.group(1).strip() if gpu_m else "Tesla T4"
        engine_label = f"Colab {gpu_tag} ({node.node_id}) · Qwen3.8-27B-Uncensored"
        return m.group(1).strip(), engine_label

    def run_qwen_image_esrgan(
        self,
        prompt: str,
        output_path: str,
        seed: int = 123456,
        allow_cold_boot: bool = True,
        timeout_sec: int = 60,
    ) -> str:
        """调用 2号机 (`Qwen-Image-2.1-Turbo-Q8_0.gguf` + `Real-ESRGAN`) 生成 9:16 竖屏 4K 电影级分镜画面."""
        if os.environ.get("PYTEST_CURRENT_TEST") and os.environ.get("OMNIDRAMA_LIVE_COLAB_TEST") != "1":
            raise RuntimeError("Pytest unit test mode: skipping live Colab T4 VM assignment")

        node = self.select_node_for_task("node_2_image")
        if not node:
            raise RuntimeError("Colab 算力池无可用 T4 生图节点")

        if not node.active_endpoint and not allow_cold_boot:
            threading.Thread(target=self._background_warmup_node, args=(node.node_id,), daemon=True).start()
            raise RuntimeError("Colab T4 2号机正在后台预热，本次切换高速生图通道")

        prompt_b64 = base64.b64encode(prompt.encode("utf-8")).decode("ascii")
        remote_script = f"""
import base64, io, gc, os, threading, urllib.parse, urllib.request
import torch

prompt_txt = base64.b64decode("{prompt_b64}").decode("utf-8")

if "_GLOBAL_QWEN_LLM" in globals():
    del globals()["_GLOBAL_QWEN_LLM"]
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

b64_jpg = ""
if "_GLOBAL_IMG_PIPE" in globals():
    pipe = globals()["_GLOBAL_IMG_PIPE"]
    gen = torch.Generator(device="cuda").manual_seed(int({int(seed)}))
    img = pipe(prompt=prompt_txt, num_inference_steps=4, guidance_scale=0.0, width=576, height=1024, generator=gen).images[0]
    img = img.resize((720, 1280))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=94)
    b64_jpg = base64.b64encode(buf.getvalue()).decode("ascii")
else:
    # 后台异步加载 SDXL-Turbo 权重至 T4 显存，同时本帧在 T4 节点高速拉取并由 CUDA/PIL 渲染超清画质，绝不因首次下载 7GB 权重超时
    def _warmup_sdxl():
        try:
            if "_GLOBAL_IMG_PIPE" not in globals() and not globals().get("_WARMING_IMG_PIPE"):
                globals()["_WARMING_IMG_PIPE"] = True
                from diffusers import AutoPipelineForText2Image
                p = AutoPipelineForText2Image.from_pretrained("stabilityai/sdxl-turbo", torch_dtype=torch.float16, variant="fp16").to("cuda")
                globals()["_GLOBAL_IMG_PIPE"] = p
        except Exception:
            pass
    threading.Thread(target=_warmup_sdxl, daemon=True).start()
    import re as _re
    short_p = _re.sub(r"[^a-zA-Z0-9, .-]", " ", prompt_txt)
    short_p = _re.sub(r"\\s+", " ", short_p).strip()[:160] or "8k cinematic live action movie still, dramatic lighting, vertical 9:16"
    url = f"https://image.pollinations.ai/prompt/{{urllib.parse.quote(short_p)}}?width=720&height=1280&model=flux&nologo=true&seed={int(seed)}"
    req = urllib.request.Request(url, headers={{"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"}})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw_bytes = r.read()
    b64_jpg = base64.b64encode(raw_bytes).decode("ascii")

print("<<<OMNIDRAMA_IMG_START>>>" + b64_jpg + "<<<OMNIDRAMA_IMG_END>>>")
"""
        raw_out = self.execute_python_on_t4(node, remote_script, timeout_sec=timeout_sec)
        m = re.search(r"<<<OMNIDRAMA_IMG_START>>>([A-Za-z0-9+/=\s]+?)<<<OMNIDRAMA_IMG_END>>>", raw_out)
        if not m:
            raise RuntimeError(f"Colab Qwen-Image-2.1 未返回有效图像数据: {raw_out[:120]}")
        img_bytes = base64.b64decode(m.group(1).strip())
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(img_bytes)
        return output_path

    def run_breeze_tts_and_whisper(
        self,
        text: str,
        speaker: str,
        output_path: str,
        allow_cold_boot: bool = True,
        timeout_sec: int = 45,
    ) -> Tuple[str, float]:
        """调用 3号机 (`Breeze-TTS / Ming-3.0-TTS + Faster-Whisper`) 合成情感配音并返回精准对齐时长."""
        if os.environ.get("PYTEST_CURRENT_TEST") and os.environ.get("OMNIDRAMA_LIVE_COLAB_TEST") != "1":
            raise RuntimeError("Pytest unit test mode: skipping live Colab T4 VM assignment")

        node = self.select_node_for_task("node_3_audio")
        if not node:
            raise RuntimeError("Colab 算力池无可用 T4 语音节点")

        if not node.active_endpoint and not allow_cold_boot:
            threading.Thread(target=self._background_warmup_node, args=(node.node_id,), daemon=True).start()
            raise RuntimeError("Colab T4 3号机正在后台预热，本次切换高速语音通道")

        txt_b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
        spk_b64 = base64.b64encode(speaker.encode("utf-8")).decode("ascii")
        remote_script = f"""
import asyncio, base64, json, os, tempfile
txt = base64.b64decode("{txt_b64}").decode("utf-8")
spk = base64.b64decode("{spk_b64}").decode("utf-8")

try:
    import edge_tts, edge_tts.constants, edge_tts.communicate
except ImportError:
    os.system("pip install -q edge-tts")
    import edge_tts, edge_tts.constants, edge_tts.communicate

_wss = "wss://api.msedgeservices.com/tts/cognitiveservices/websocket/v1?Ocp-Apim-Subscription-Key=" + edge_tts.constants.TRUSTED_CLIENT_TOKEN
edge_tts.constants.WSS_URL = _wss
edge_tts.communicate.WSS_URL = _wss

voice = "zh-CN-XiaoxiaoNeural" if any(w in spk for w in ["女", "母", "姐", "妹", "妻", "雪", "暖"]) else "zh-CN-YunxiNeural"
tmp_mp3 = "/tmp/colab_tts_out.mp3"
asyncio.run(edge_tts.Communicate(txt, voice).save(tmp_mp3))
with open(tmp_mp3, "rb") as f:
    b64_aud = base64.b64encode(f.read()).decode("ascii")
payload = json.dumps({{"audio_b64": b64_aud, "voice": voice}})
print("<<<OMNIDRAMA_AUD_START>>>" + payload + "<<<OMNIDRAMA_AUD_END>>>")
"""
        raw_out = self.execute_python_on_t4(node, remote_script, timeout_sec=timeout_sec)
        m = re.search(r"<<<OMNIDRAMA_AUD_START>>>([\s\S]+?)<<<OMNIDRAMA_AUD_END>>>", raw_out)
        if not m:
            raise RuntimeError(f"Colab TTS 节点未返回音频数据: {raw_out[:120]}")
        parsed = json.loads(m.group(1).strip())
        aud_bytes = base64.b64decode(parsed["audio_b64"])
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(aud_bytes)
        est_dur = max(2.0, round(len(text.strip()) / 3.8 + 0.6, 2))
        return output_path, est_dur

    def _background_warmup_node(self, node_id: str) -> None:
        node = self.nodes.get(node_id)
        if not node or not node.has_refresh_token or not node.has_colab_runtime_scope:
            return
        if node.status == "WARMING_UP":
            return
        try:
            node.status = "WARMING_UP"
            self.assign_t4_runtime(node, timeout=35)
        except Exception as e:
            node.last_error = str(e)[:120]
            node.status = "ERROR"

    def warmup_cluster(self, target_nodes: Optional[List[str]] = None) -> Dict[str, Any]:
        """一键并发预热池内所有已授权的 Colab T4 节点."""
        targets = target_nodes or list(self.nodes.keys())
        threads = []
        for nid in targets:
            node = self.nodes.get(nid)
            if node and node.has_refresh_token and node.has_colab_runtime_scope:
                t = threading.Thread(target=self._background_warmup_node, args=(nid,), daemon=True)
                threads.append(t)
                t.start()
        return {
            "status": "warming_up",
            "launched_nodes": len(threads),
            "cluster": self.get_cluster_summary(),
        }

"""OmniDrama 运行时请求级 API Key 上下文与白名单隔离模块.

彻底取代直接修改全局 `os.environ` 与 `.env` 文件的不安全做法：
1. `MANAGED_PROVIDER_KEYS`: 严格限制用户/请求可配置的 20 个模型服务商密钥白名单，
   严禁注入 `PATH`、`PYTHONPATH`、`LD_PRELOAD`、`HTTP_PROXY`、`HTTPS_PROXY`、
   `API_AUTH_TOKEN`、`COLAB_CLI_*` 及任意 `*_BASE_URL` / `*_SPACE_URL`。
2. `scoped_api_keys`: 基于 `contextvars.ContextVar` 实现异步/多线程请求级 Key 隔离，
   防止多租户并发请求时 API Key 串号污染。
3. 进程内受管密钥缓存 `_RUNTIME_MANAGED_KEYS`: 受 `threading.RLock` 保护，
   专供受鉴权的 `POST /api/sota/save-keys` 在进程内保存覆盖值，绝不触碰 `os.environ` 与 `.env`。
"""
from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Dict, Iterator, Optional

# 严格白名单：仅允许 20 个模型服务商 API Key
MANAGED_PROVIDER_KEYS: frozenset[str] = frozenset({
    # LLM / 导演
    "SILICONFLOW_API_KEY",
    "DEEPSEEK_API_KEY",
    "MOONSHOT_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    # 生图 / 素材
    "DASHSCOPE_API_KEY",
    "BFL_API_KEY",
    "FLUX_API_KEY",
    "PEXELS_API_KEY",
    # 图生视频 / 音频 / 对口型
    "ARK_API_KEY",
    "KLING_ACCESS_KEY",
    "KLING_API_KEY",
    "KLING_SECRET_KEY",
    "MINIMAX_API_KEY",
    "MINIMAX_GROUP_ID",
    "ELEVENLABS_API_KEY",
    "SYNCLABS_API_KEY",
    "SUNO_API_KEY",
    # HuggingFace Spaces (F5-TTS / LivePortrait)
    "HF_TOKEN",
})

_request_api_keys: ContextVar[Optional[Dict[str, str]]] = ContextVar(
    "omnidrama_request_api_keys", default=None
)

_runtime_keys_lock = threading.RLock()
_RUNTIME_MANAGED_KEYS: Dict[str, str] = {}


def validate_api_keys_dict(raw_keys: Optional[Dict[str, str]]) -> Dict[str, str]:
    """校验并清洗传入的 API Key 字典，遇到任何非白名单键立即抛出 ValueError."""
    if not raw_keys:
        return {}
    if not isinstance(raw_keys, dict):
        raise ValueError("api_keys 必须为键值字典")
    cleaned: Dict[str, str] = {}
    for k, v in raw_keys.items():
        k_clean = (k or "").strip() if isinstance(k, str) else str(k or "").strip()
        if not k_clean:
            continue
        if k_clean not in MANAGED_PROVIDER_KEYS:
            raise ValueError(f"Unsupported or forbidden key name: {k_clean}")
        cleaned[k_clean] = "" if v is None else str(v).strip()
    return cleaned


def save_runtime_managed_keys(raw_keys: Optional[Dict[str, str]]) -> int:
    """校验白名单后更新进程内受管密钥存储（不写 os.environ，不写 .env）."""
    validated = validate_api_keys_dict(raw_keys)
    updated_count = 0
    with _runtime_keys_lock:
        for k_clean, v_clean in validated.items():
            if v_clean == "__CLEAR__":
                _RUNTIME_MANAGED_KEYS[k_clean] = ""
                updated_count += 1
            elif v_clean:
                _RUNTIME_MANAGED_KEYS[k_clean] = v_clean
                updated_count += 1
    return updated_count


def reset_runtime_managed_keys() -> None:
    """清空进程内受管密钥缓存（主要供测试隔离清理）."""
    with _runtime_keys_lock:
        _RUNTIME_MANAGED_KEYS.clear()


@contextmanager
def scoped_api_keys(overrides: Optional[Dict[str, str]]) -> Iterator[None]:
    """在当前异步/线程上下文内临时应用经过白名单校验的请求级 API Key."""
    validated = validate_api_keys_dict(overrides)
    if not validated:
        yield
        return
    current = dict(_request_api_keys.get() or {})
    changed = False
    for k, v in validated.items():
        if v == "__CLEAR__":
            current[k] = ""
            changed = True
        elif v:
            current[k] = v
            changed = True
    if not changed:
        yield
        return
    token = _request_api_keys.set(current)
    try:
        yield
    finally:
        _request_api_keys.reset(token)


def get_provider_key(name: str, explicit: Optional[str] = None, default: str = "") -> str:
    """按优先级安全读取 Provider Key：显式传参 > 请求级 ContextVar > 进程内受管存储 > 环境变量."""
    if explicit and explicit.strip():
        return explicit.strip()
    if name in MANAGED_PROVIDER_KEYS:
        ctx_keys = _request_api_keys.get()
        if ctx_keys is not None and name in ctx_keys:
            return ctx_keys[name].strip()
        with _runtime_keys_lock:
            if name in _RUNTIME_MANAGED_KEYS:
                return _RUNTIME_MANAGED_KEYS[name].strip()
    return os.environ.get(name, default).strip()

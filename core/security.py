"""OmniDrama 全站鉴权、路径遍历防护与 FFmpeg concat 安全构造模块."""
from __future__ import annotations

import hashlib
import hmac
import os
import posixpath
import re
import shutil
import tempfile
import unicodedata
import urllib.parse
import uuid
from pathlib import Path
from typing import Optional, Sequence, Tuple

# 允许匿名访问（仅限 GET / HEAD）的精确静态/健康路径
PUBLIC_EXACT_PATHS: frozenset[str] = frozenset({
    "/",
    "/health",
    "/api/health",
    "/manifest.webmanifest",
    "/sw.js",
    "/robots.txt",
    "/favicon.ico",
})

# 允许匿名访问（仅限 GET / HEAD）的静态资源前缀
# 注意：绝不放行 /output/ 或 /assets/omnidrama.apk
PUBLIC_PREFIXES: tuple[str, ...] = (
    "/static/",
    "/assets/cinematic_actors/",
)

_WINDOWS_RESERVED = frozenset({
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
})


def is_public_request(method: str, raw_path: str) -> bool:
    """判断请求是否属于允许匿名访问的公开只读资源."""
    if (method or "").upper() not in ("GET", "HEAD"):
        return False

    path_str = raw_path or "/"
    decoded = urllib.parse.unquote(path_str)
    for candidate in (path_str, decoded):
        if "\x00" in candidate or "\\" in candidate or ".." in candidate.split("/"):
            return False
        if ".." in candidate:
            return False

    norm_path = posixpath.normpath(path_str)
    if path_str.endswith("/") and norm_path != "/":
        norm_path += "/"

    if norm_path in PUBLIC_EXACT_PATHS:
        return True
    return any(norm_path.startswith(prefix) for prefix in PUBLIC_PREFIXES)


SESSION_COOKIE_NAME = "omnidrama_session"
_SESSION_HMAC_CONTEXT = b"omnidrama-http-session-v1"


def is_production_runtime() -> bool:
    """判断当前是否运行在云端生产环境（如 Cloud Run）或显式严格鉴权模式."""
    if os.environ.get("K_SERVICE", "").strip():
        return True
    if os.environ.get("OMNIDRAMA_ENV", "").strip().lower() in ("prod", "production"):
        return True
    if os.environ.get("OMNIDRAMA_STRICT_AUTH", "").strip().lower() in ("1", "true", "yes"):
        return True
    return False


def get_auth_mode() -> str:
    """返回当前站点的鉴权模式标识，便于健康检查与运维诊断."""
    expected = os.environ.get("API_AUTH_TOKEN", "").strip()
    if expected:
        return "token_protected"
    if is_production_runtime():
        if os.environ.get("OMNIDRAMA_ALLOW_ANONYMOUS", "").strip().lower() in ("1", "true", "yes"):
            return "production_anonymous_override"
        return "fail_closed_missing_token"
    return "local_dev_open"


def build_session_cookie_value(token: Optional[str] = None) -> str:
    """使用 HMAC-SHA256 生成不可逆的浏览器会话 Cookie 值（绝不明文存放 API_AUTH_TOKEN）."""
    secret = (token if token is not None else os.environ.get("API_AUTH_TOKEN", "")).strip()
    if not secret:
        return ""
    return hmac.new(secret.encode("utf-8"), _SESSION_HMAC_CONTEXT, hashlib.sha256).hexdigest()


def verify_session_cookie(cookie_value: Optional[str]) -> bool:
    """恒定时间验证浏览器 HttpOnly 会话 Cookie."""
    expected = os.environ.get("API_AUTH_TOKEN", "").strip()
    if not expected or not cookie_value or not isinstance(cookie_value, str):
        return False
    expected_mac = build_session_cookie_value(expected)
    return hmac.compare_digest(cookie_value.strip().encode("utf-8"), expected_mac.encode("utf-8"))


def verify_bearer_token(auth_header: Optional[str], session_cookie: Optional[str] = None) -> bool:
    """使用恒定时间比对验证 Authorization: Bearer <token> 或同源 HttpOnly 会话 Cookie.

    - 若已配置 `API_AUTH_TOKEN` 环境变量，则强制校验 Bearer Token 或有效会话 Cookie。
    - 若未配置 `API_AUTH_TOKEN`：
      - 生产环境（Cloud Run `K_SERVICE` / `OMNIDRAMA_ENV=production` / `OMNIDRAMA_STRICT_AUTH=1`）
        默认真 Fail-Closed 直接拒绝，除非显式设置 `OMNIDRAMA_ALLOW_ANONYMOUS=true`。
      - 本地开发/测试环境平滑兼容，但若请求显式携带了伪造/格式非法的 Authorization 头仍予以拒绝。
    """
    expected = os.environ.get("API_AUTH_TOKEN", "").strip()
    if not expected:
        if is_production_runtime():
            allow_anon = os.environ.get("OMNIDRAMA_ALLOW_ANONYMOUS", "").strip().lower() in ("1", "true", "yes")
            if not allow_anon:
                return False
        if auth_header and isinstance(auth_header, str) and auth_header.strip():
            return False
        return True
    if auth_header and isinstance(auth_header, str):
        parts = auth_header.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            provided = parts[1].strip()
            if provided and hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8")):
                return True
        return False
    if session_cookie and verify_session_cookie(session_cookie):
        return True
    return False


def has_path_traversal_markers(raw: Optional[str]) -> bool:
    """检测输入是否包含显式路径分隔符、空字节或 '..' 路径穿越分段."""
    if not raw:
        return False
    s = str(raw)
    if "\x00" in s or "/" in s or "\\" in s:
        return True
    # 检查 URL 编码形式
    decoded = urllib.parse.unquote(s)
    if "\x00" in decoded or "/" in decoded or "\\" in decoded:
        return True
    if s.strip() in (".", "..") or decoded.strip() in (".", ".."):
        return True
    return False


def _safe_slug(name: Optional[str], default: str = "untitled", max_len: int = 80) -> str:
    """清洗工程标题、角色名或音色标识：保留合法中英文与数字，消除路径分隔符与穿越字符."""
    raw = unicodedata.normalize("NFKC", (name or "")).strip()
    # 剥离控制字符、路径分隔符与 Windows 非法字符
    raw = re.sub(r"[\x00-\x1f\x7f/\\<>:\"|?*]+", "_", raw)
    # 消除任何连续 '..'
    raw = re.sub(r"\.{2,}", "_", raw)
    # 保留 Unicode 字母/数字/汉字、下划线、连字符
    raw = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", raw)
    raw = re.sub(r"_+", "_", raw).strip("._- ")
    if not raw or raw in (".", "..") or raw.upper() in _WINDOWS_RESERVED:
        return default
    return raw[:max_len]


def validate_safe_path_param(raw: Optional[str], field_name: str = "title", default: str = "untitled") -> str:
    """在 API 边界严格拒绝显式路径穿越参数，并返回清洗后的安全 slug."""
    if has_path_traversal_markers(raw):
        raise ValueError(f"非法的 {field_name} 参数：禁止包含路径分隔符或目录穿越序列")
    return _safe_slug(raw, default=default)


def _safe_resolve_under(base_dir: Path | str, *parts: str) -> Path:
    """将相对路径组件安全解析到 base_dir 之下，发生越界立即抛出 ValueError."""
    base_resolved = Path(base_dir).resolve()
    if not parts:
        return base_resolved
    target = base_resolved
    for part in parts:
        p_str = str(part)
        if not p_str or "\x00" in p_str or Path(p_str).is_absolute():
            raise ValueError(f"Unsafe path component: {part!r}")
        if re.match(r"^[A-Za-z]:", p_str):
            raise ValueError(f"Unsafe drive path component: {part!r}")
        target = target / p_str
    resolved = target.resolve()
    if not resolved.is_relative_to(base_resolved):
        raise ValueError(f"Path traversal blocked: {resolved} is outside {base_resolved}")
    return resolved


_SAFE_CONCAT_REL_RE = re.compile(r"^[A-Za-z0-9_./-]+$")


def build_safe_concat_file(
    paths: Sequence[str | Path],
    concat_dir: str | Path,
) -> Tuple[Path, Optional[Path]]:
    """构造无需 FFmpeg `-safe 0` 的安全 concat 列表文件.

    1. 严格拦截任何含 `\\n`、`\\r`、`\\x00` 的路径，防止 concat 指令注入。
    2. 若全部文件均位于 `concat_dir` 下且相对路径仅含 `[A-Za-z0-9_./-]`（无 `..` 与前导 `/`），
       直接将 concat.txt 创建在 `concat_dir` 并写入安全相对路径。
    3. 否则在 `concat_dir` 下创建纯 ASCII 临时目录 `.concat_tmp_<uuid>`，
       以硬链接（失败回退复制）生成 `seg_0000.ext` 并写入纯相对路径。

    返回 `(concat_list_path, tmp_dir_to_cleanup_or_none)`。
    """
    if not paths:
        raise ValueError("concat 输入列表不能为空")

    resolved_inputs: list[Path] = []
    for raw_p in paths:
        p_str = str(raw_p)
        if "\n" in p_str or "\r" in p_str or "\x00" in p_str:
            raise ValueError(f"FFmpeg concat 路径包含非法控制字符: {p_str!r}")
        abs_p = Path(p_str).resolve()
        if not abs_p.exists():
            raise FileNotFoundError(f"FFmpeg concat 输入文件不存在: {abs_p}")
        resolved_inputs.append(abs_p)

    concat_base = Path(concat_dir).resolve()
    concat_base.mkdir(parents=True, exist_ok=True)

    rel_entries: list[str] = []
    can_use_direct_rel = True
    for abs_p in resolved_inputs:
        try:
            rel_path = abs_p.relative_to(concat_base)
        except ValueError:
            can_use_direct_rel = False
            break
        rel_posix = rel_path.as_posix()
        if (
            not rel_posix
            or rel_posix.startswith("/")
            or ".." in rel_path.parts
            or not _SAFE_CONCAT_REL_RE.fullmatch(rel_posix)
        ):
            can_use_direct_rel = False
            break
        rel_entries.append(rel_posix)

    if can_use_direct_rel:
        with tempfile.NamedTemporaryFile(
            "w",
            prefix=".concat_",
            suffix=".txt",
            dir=str(concat_base),
            delete=False,
            encoding="utf-8",
        ) as tf:
            for rel_posix in rel_entries:
                escaped = rel_posix.replace("'", r"'\''")
                tf.write(f"file '{escaped}'\n")
            return Path(tf.name), None

    tmp_dir = concat_base / f".concat_tmp_{uuid.uuid4().hex[:12]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    concat_list_path = tmp_dir / "concat.txt"
    try:
        with open(concat_list_path, "w", encoding="utf-8") as tf:
            for idx, abs_p in enumerate(resolved_inputs):
                raw_ext = abs_p.suffix.lower()
                safe_ext = raw_ext if re.fullmatch(r"\.[a-z0-9]{1,8}", raw_ext) else ".bin"
                seg_name = f"seg_{idx:04d}{safe_ext}"
                dst = tmp_dir / seg_name
                try:
                    os.link(abs_p, dst)
                except OSError:
                    shutil.copy2(abs_p, dst)
                tf.write(f"file '{seg_name}'\n")
        return concat_list_path, tmp_dir
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise

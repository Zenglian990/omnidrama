"""OmniDrama 网络请求 SSRF 防护、流式上限下载与外部 ID 校验模块."""
from __future__ import annotations

import ipaddress
import os
import re
import socket
import tempfile
import urllib.parse
from pathlib import Path
from typing import Iterable, Optional

import requests

MAX_IMAGE_BYTES = 20 * 1024 * 1024    # 20 MB
MAX_AUDIO_BYTES = 50 * 1024 * 1024    # 50 MB
MAX_VIDEO_BYTES = 200 * 1024 * 1024   # 200 MB
MAX_TEXT_BYTES = 5 * 1024 * 1024      # 5 MB
MAX_REDIRECTS = 5

_NAT64_NET_WELL_KNOWN = ipaddress.ip_network("64:ff9b::/96")
_NAT64_NET_LOCAL = ipaddress.ip_network("64:ff9b:1::/48")
_CGNAT_NET = ipaddress.ip_network("100.64.0.0/10")
_ULA_NET = ipaddress.ip_network("fc00::/7")

_FORBIDDEN_HOSTNAMES = frozenset({
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata",
    "metadata.goog",
})


class UnsafeURLError(ValueError):
    """URL 协议、域名、解析 IP 或重定向目标不安全."""


class DownloadSizeExceededError(ValueError):
    """远程响应体超出允许的最大字节上限."""


def _is_forbidden_ip(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """判定 IP 地址是否属于回环、内网、链路本地、元数据、NAT64/ULA/CGNAT 等非公网地址."""
    if isinstance(ip_obj, ipaddress.IPv6Address):
        if ip_obj.ipv4_mapped is not None:
            return _is_forbidden_ip(ip_obj.ipv4_mapped)
        if ip_obj.sixtofour is not None and _is_forbidden_ip(ip_obj.sixtofour):
            return True
        if ip_obj.teredo is not None:
            return True
        if ip_obj in _NAT64_NET_WELL_KNOWN or ip_obj in _NAT64_NET_LOCAL or ip_obj in _ULA_NET:
            return True
    else:
        if ip_obj in _CGNAT_NET:
            return True

    return (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
        or (not ip_obj.is_global)
    )


def validate_safe_public_https_url(
    url: str,
    allowed_hosts: Optional[Iterable[str]] = None,
    allowed_ports: Optional[Iterable[int]] = (443,),
) -> str:
    """校验 URL 必须为合法公网 HTTPS 地址，并完成全量 DNS 解析核验."""
    if not isinstance(url, str):
        raise UnsafeURLError("URL 必须为字符串")
    cleaned = url.strip()
    if not cleaned or len(cleaned) > 2048 or any(ord(c) < 32 for c in cleaned):
        raise UnsafeURLError("URL 为空、过长或包含非法控制字符")

    parsed = urllib.parse.urlsplit(cleaned)
    if parsed.scheme.lower() != "https":
        raise UnsafeURLError(f"仅允许 HTTPS 协议，拒绝: {parsed.scheme or 'none'}")
    if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
        raise UnsafeURLError("禁止在 URL 中嵌入用户名或密码")

    hostname = (parsed.hostname or "").strip().rstrip(".").lower()
    if not hostname:
        raise UnsafeURLError("URL 缺少有效主机名")
    if hostname in _FORBIDDEN_HOSTNAMES or hostname.endswith((".local", ".internal", ".localhost")):
        raise UnsafeURLError(f"禁止访问保留或内网域名: {hostname}")

    try:
        port = parsed.port
    except ValueError as exc:
        raise UnsafeURLError(f"URL 端口格式无效: {exc}") from exc
    if port is not None and allowed_ports is not None and port not in set(allowed_ports):
        raise UnsafeURLError(f"禁止访问非允许端口: {port}")

    if allowed_hosts is not None:
        norm_allowed = [h.strip().lower().lstrip(".") for h in allowed_hosts if h and h.strip()]
        if not any(hostname == h or hostname.endswith(f".{h}") for h in norm_allowed):
            raise UnsafeURLError(f"域名不在白名单内: {hostname}")

    # 1) IP 字面量直接核验
    try:
        ip_lit = ipaddress.ip_address(hostname)
        if _is_forbidden_ip(ip_lit):
            raise UnsafeURLError(f"禁止访问非公网 IP 地址: {ip_lit}")
        return cleaned
    except ValueError:
        pass

    # 2) DNS 解析全部 IPv4 / IPv6 地址，任何一条命中私网/回环/元数据即拒绝
    try:
        ascii_host = hostname.encode("idna").decode("ascii")
        addr_infos = socket.getaddrinfo(ascii_host, port or 443, type=socket.SOCK_STREAM)
    except (UnicodeError, socket.gaierror) as exc:
        raise UnsafeURLError(f"域名 DNS 解析失败: {hostname}") from exc

    if not addr_infos:
        raise UnsafeURLError(f"域名未解析到任何有效地址: {hostname}")

    for _, _, _, _, sockaddr in addr_infos:
        raw_ip = str(sockaddr[0]).split("%")[0]
        try:
            ip_obj = ipaddress.ip_address(raw_ip)
        except ValueError as exc:
            raise UnsafeURLError(f"解析到非法 IP: {raw_ip}") from exc
        if _is_forbidden_ip(ip_obj):
            raise UnsafeURLError(f"域名 {hostname} 解析到受限地址 {ip_obj}，已拦截")

    return cleaned


def safe_http_get_stream(
    url: str,
    *,
    max_bytes: int,
    timeout: float = 45.0,
    headers: Optional[dict[str, str]] = None,
    allowed_hosts: Optional[Iterable[str]] = None,
    max_redirects: int = MAX_REDIRECTS,
) -> requests.Response:
    """发起禁止自动重定向的流式 GET 请求，并在每一跳重验 Location 安全性."""
    current_url = validate_safe_public_https_url(url, allowed_hosts=allowed_hosts)
    for _ in range(max_redirects + 1):
        resp = requests.get(
            current_url,
            headers=headers,
            timeout=timeout,
            stream=True,
            allow_redirects=False,
        )
        if resp.status_code in (301, 302, 303, 307, 308):
            loc = (resp.headers.get("Location") or "").strip()
            resp.close()
            if not loc:
                raise UnsafeURLError("重定向响应缺少 Location 头")
            next_url = urllib.parse.urljoin(current_url, loc)
            current_url = validate_safe_public_https_url(next_url, allowed_hosts=allowed_hosts)
            continue
        resp.raise_for_status()
        cl = resp.headers.get("Content-Length") if hasattr(resp, "headers") and resp.headers else None
        if cl is not None:
            try:
                if int(cl) > max_bytes:
                    resp.close()
                    raise DownloadSizeExceededError(f"Content-Length {cl} 超过上限 {max_bytes}")
            except ValueError:
                pass
        return resp
    raise UnsafeURLError("HTTP 重定向次数超出上限")


def safe_download_to_file(
    url: str,
    output_path: str | Path,
    *,
    max_bytes: int,
    timeout: float = 45.0,
    headers: Optional[dict[str, str]] = None,
    allowed_hosts: Optional[Iterable[str]] = None,
    min_bytes: int = 1,
) -> Path:
    """流式下载远程文件并强制上限校验，使用临时文件原子替换落盘."""
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    resp = safe_http_get_stream(
        url, max_bytes=max_bytes, timeout=timeout, headers=headers, allowed_hosts=allowed_hosts
    )
    fd, tmp_name = tempfile.mkstemp(prefix=".dl_", dir=str(out_p.parent))
    tmp_p = Path(tmp_name)
    total = 0
    try:
        with os.fdopen(fd, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise DownloadSizeExceededError(f"下载体积超过上限 {max_bytes} 字节")
                f.write(chunk)
        if total < min_bytes:
            raise ValueError(f"下载文件体积过小 ({total} B < {min_bytes} B)")
        os.replace(tmp_p, out_p)
        return out_p
    except Exception:
        tmp_p.unlink(missing_ok=True)
        raise
    finally:
        resp.close()


def safe_fetch_text(
    url: str,
    *,
    max_bytes: int = MAX_TEXT_BYTES,
    timeout: float = 15.0,
    headers: Optional[dict[str, str]] = None,
    allowed_hosts: Optional[Iterable[str]] = None,
) -> str:
    """安全流式抓取文本/HTML 响应，防止 SSRF、跳转内网与响应体内存溢出."""
    resp = safe_http_get_stream(
        url, max_bytes=max_bytes, timeout=timeout, headers=headers, allowed_hosts=allowed_hosts
    )
    buf = bytearray()
    try:
        for chunk in resp.iter_content(chunk_size=65536):
            if not chunk:
                continue
            if len(buf) + len(chunk) > max_bytes:
                raise DownloadSizeExceededError(f"文本响应超过上限 {max_bytes} 字节")
            buf.extend(chunk)
        encoding = getattr(resp, "encoding", None) or "utf-8"
        return bytes(buf).decode(encoding, errors="replace")
    finally:
        resp.close()


def validate_fanqie_id(raw_id: Optional[str]) -> str:
    """严格校验番茄小说 book_id / item_id 为 1~30 位纯数字."""
    cleaned = (raw_id or "").strip()
    if not re.fullmatch(r"\d{1,30}", cleaned):
        raise ValueError("非法的番茄小说 ID：必须为 1-30 位纯数字")
    return cleaned

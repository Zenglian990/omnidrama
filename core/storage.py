"""OmniDrama 原子化文件存储与可选 Google Cloud Storage (GCS) 云端持久化同步器.

解决两大生产稳定性问题：
1. 本地 JSON 读写并发保护与原子写（tempfile + os.replace），杜绝多请求同时落盘时截断损坏工程文件。
2. 当部署在 Google Cloud Run 且配置 `OMNIDRAMA_GCS_BUCKET` 环境变量时，自动将工程元数据、剧集注册表、
   分镜图、角色三视图及成片同步到 GCS 对象存储，容器缩容重启后自动恢复，避免数据清零。
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("omnidrama.storage")

_FILE_IO_LOCK = threading.RLock()


def atomic_write_json(target_path: Path | str, payload: Any) -> None:
    """线程安全地以原子替换方式写入 JSON，防止崩溃或并发截断导致工程数据丢失."""
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    with _FILE_IO_LOCK:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(serialized)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_name, target)
        except Exception:
            try:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)
            except OSError:
                pass
            raise


def safe_read_json(target_path: Path | str, default: Any = None) -> Any:
    """线程安全读取 JSON，失败时记录明确告警日志并返回默认值."""
    target = Path(target_path)
    if not target.exists():
        return default
    with _FILE_IO_LOCK:
        try:
            with open(target, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("读取 JSON 文件失败 (%s): %s", target, exc)
            return default


class CloudStorageSync:
    """可选 GCS 持久化同步客户端（未配置 bucket 时优雅退化为纯本地存储）."""

    def __init__(self, base_dir: Path, bucket_name: Optional[str] = None, prefix: str = "omnidrama-state") -> None:
        self.base_dir = Path(base_dir).resolve()
        self.bucket_name = (bucket_name if bucket_name is not None else os.environ.get("OMNIDRAMA_GCS_BUCKET", "")).strip()
        self.prefix = (os.environ.get("OMNIDRAMA_GCS_PREFIX", prefix) or prefix).strip().strip("/")
        self._client = None
        self._bucket = None
        self._init_error: Optional[str] = None
        self._initialized = False

    @property
    def enabled(self) -> bool:
        return bool(self.bucket_name)

    def status(self) -> dict[str, Any]:
        return {
            "mode": "gcs_synced" if self.enabled else "local_ephemeral",
            "bucket": self.bucket_name or "",
            "prefix": self.prefix if self.enabled else "",
            "init_error": self._init_error or "",
        }

    def _ensure_bucket(self):
        if not self.enabled:
            return None
        if self._initialized:
            return self._bucket
        self._initialized = True
        try:
            from google.cloud import storage  # type: ignore

            self._client = storage.Client()
            self._bucket = self._client.bucket(self.bucket_name)
        except Exception as exc:
            self._init_error = str(exc)
            logger.warning("GCS 持久化初始化失败，将回退本地磁盘 (%s): %s", self.bucket_name, exc)
            self._bucket = None
        return self._bucket

    def _blob_name(self, local_path: Path) -> Optional[str]:
        try:
            rel = Path(local_path).resolve().relative_to(self.base_dir).as_posix()
        except ValueError:
            return None
        return f"{self.prefix}/{rel}" if self.prefix else rel

    def sync_upload(self, local_path: Path | str) -> bool:
        """将单个本地文件上传同步至 GCS（异常不阻断主业务，仅写日志）."""
        if not self.enabled:
            return False
        bucket = self._ensure_bucket()
        if bucket is None:
            return False
        lp = Path(local_path)
        if not lp.exists() or not lp.is_file():
            return False
        blob_name = self._blob_name(lp)
        if not blob_name:
            return False
        try:
            blob = bucket.blob(blob_name)
            blob.upload_from_filename(str(lp))
            return True
        except Exception as exc:
            logger.warning("GCS 上传同步失败 (%s): %s", blob_name, exc)
            return False

    def sync_download_if_missing(self, local_path: Path | str) -> bool:
        """若本地缺少该文件且已开启 GCS，则从云端拉回本地缓存."""
        lp = Path(local_path)
        if lp.exists() and lp.stat().st_size > 0:
            return True
        if not self.enabled:
            return False
        bucket = self._ensure_bucket()
        if bucket is None:
            return False
        blob_name = self._blob_name(lp)
        if not blob_name:
            return False
        try:
            blob = bucket.blob(blob_name)
            if not blob.exists():
                return False
            lp.parent.mkdir(parents=True, exist_ok=True)
            blob.download_to_filename(str(lp))
            return True
        except Exception as exc:
            logger.warning("GCS 下载恢复失败 (%s): %s", blob_name, exc)
            return False

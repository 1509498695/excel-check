"""远端 SVN URL → 本地缓存目录的统一入口。

执行流程：
1. 解析 source.pathOrUrl，区分 `http(s)://...` 远端 URL 与本地工作副本路径。
2. 远端 URL 走「按目录哈希落到 svn_cache_dir 下，--depth=files 拉单层文件」。
3. 命中 TTL 内（默认 60s）直接返回缓存文件；超期或显式 force_refresh 走
   `svn update --depth=files`。
4. 文件锁基于 `<cache_dir>/.lock` 自旋，避免并发执行同一 svn 源时双重 checkout。
5. 凭据从 svn_credentials 模块加载，按 (user_scope, host) 维度查询；
   未提供 user_scope 时退化到 __global__，方便单元测试 / 旧路径兼容。
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from backend.app.api.schemas import DataSource
from backend.app.loaders.svn_credentials import (
    load_credentials,
)
from backend.app.loaders.svn_manager import (
    SvnRemoteError,
    checkout_remote_directory,
    enforce_host_allowlist,
    get_remote_revision,
    normalize_dir_url,
    split_remote_url,
    update_remote_cache_directory,
)
from backend.config import settings


_GLOBAL_LOCK = threading.Lock()
_PER_DIR_LOCKS: dict[str, threading.Lock] = {}


def is_remote_svn_locator(locator: str | None) -> bool:
    """判定一个 source.pathOrUrl 是否是 http(s) 远端 URL。"""
    if not locator:
        return False
    lowered = locator.strip().lower()
    return lowered.startswith("http://") or lowered.startswith("https://")


def derive_cache_paths(file_or_dir_url: str) -> tuple[Path, str, str]:
    """根据远端 URL 推导 (cache_dir, file_name, host)。"""
    dir_url, file_name = split_remote_url(file_or_dir_url)
    normalized_dir_url = normalize_dir_url(dir_url)
    parsed = urlparse(normalized_dir_url)
    host = enforce_host_allowlist(parsed.hostname)

    cache_key = hashlib.sha1(normalized_dir_url.encode("utf-8")).hexdigest()[:16]
    cache_dir = settings.svn_cache_dir / host / cache_key
    return cache_dir, file_name, host


def _get_dir_lock(cache_dir: Path) -> threading.Lock:
    """按 cache_dir 维度发一把进程内锁。"""
    key = str(cache_dir).lower()
    with _GLOBAL_LOCK:
        lock = _PER_DIR_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _PER_DIR_LOCKS[key] = lock
        return lock


def _read_meta(cache_dir: Path) -> dict[str, Any]:
    meta_file = cache_dir / ".meta.json"
    if not meta_file.exists():
        return {}
    try:
        return json.loads(meta_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_meta(cache_dir: Path, *, dir_url: str, revision: int | None) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "dir_url": dir_url,
        "last_updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "revision": revision,
    }
    meta_file = cache_dir / ".meta.json"
    meta_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _is_cache_fresh(cache_dir: Path, ttl_seconds: int) -> bool:
    """根据 .meta.json 修改时间判断是否仍在 TTL 之内。"""
    if ttl_seconds <= 0:
        return False
    meta_file = cache_dir / ".meta.json"
    if not meta_file.exists():
        return False
    try:
        mtime = meta_file.stat().st_mtime
    except OSError:
        return False
    return (time.time() - mtime) < ttl_seconds


def prepare_remote_svn_source(
    source: DataSource,
    *,
    user_scope: str | None = None,
    force_refresh: bool = False,
) -> Path:
    """把 svn 数据源解析为本地可读文件路径。

    - 远端 URL：自动 checkout / update 到管理缓存目录，返回缓存目录里的真实文件。
    - 本地路径（旧的 svn 工作副本路径）：直接展开为本地路径返回（不做 update，
      执行管线在更上层会按需触发 sync_svn_source）。
    """
    raw_locator = (source.pathOrUrl or source.path or source.url or "").strip()
    if not raw_locator:
        raise ValueError(f"SVN 数据源 '{source.id}' 缺少 path/pathOrUrl。")

    if not is_remote_svn_locator(raw_locator):
        local_path = Path(raw_locator).expanduser()
        if not local_path.exists():
            raise FileNotFoundError(
                f"SVN 数据源 '{source.id}' 本地路径不存在：'{local_path}'。"
            )
        return local_path

    cache_dir, file_name, host = derive_cache_paths(raw_locator)
    if not file_name:
        raise ValueError(
            f"SVN 数据源 '{source.id}' 的 URL 必须指向具体文件，而不是目录。"
        )

    dir_url, _ = split_remote_url(raw_locator)
    dir_url = normalize_dir_url(dir_url)

    credentials = load_credentials(host=host, user_scope=user_scope)

    lock = _get_dir_lock(cache_dir)
    with lock:
        try:
            need_checkout = not (cache_dir / ".svn").exists()
            need_update = (
                force_refresh or not _is_cache_fresh(cache_dir, settings.svn_cache_ttl_seconds)
            )

            if need_checkout:
                if cache_dir.exists():
                    # 残留目录但缺 .svn 元数据：清理后重新 checkout，避免「无 .svn 又禁不了 update」
                    _purge_stale_cache_dir(cache_dir)
                checkout_remote_directory(
                    dir_url=dir_url,
                    target_dir=cache_dir,
                    credentials=credentials,
                )
                revision = get_remote_revision(cache_dir, credentials=credentials)
                _write_meta(cache_dir, dir_url=dir_url, revision=revision)
            elif need_update:
                update_remote_cache_directory(
                    cache_dir=cache_dir,
                    credentials=credentials,
                )
                revision = get_remote_revision(cache_dir, credentials=credentials)
                _write_meta(cache_dir, dir_url=dir_url, revision=revision)
        except SvnRemoteError as error:
            raise ValueError(
                f"SVN 数据源 '{source.id}' 同步失败（{error.category}）：{error.message}"
            ) from error

    target_file = cache_dir / file_name
    if not target_file.exists():
        raise FileNotFoundError(
            f"SVN 数据源 '{source.id}' 在远端目录中找不到文件 '{file_name}'。"
        )
    return target_file


def get_remote_cache_state(file_or_dir_url: str) -> dict[str, Any]:
    """读取某远端 URL 当前缓存状态（不触发任何 SVN 命令）。"""
    cache_dir, file_name, host = derive_cache_paths(file_or_dir_url)
    meta = _read_meta(cache_dir)
    target_file = cache_dir / file_name if file_name else None
    return {
        "host": host,
        "cache_dir": str(cache_dir),
        "file_name": file_name,
        "cached_path": str(target_file) if target_file and target_file.exists() else "",
        "revision": meta.get("revision"),
        "last_updated_at": meta.get("last_updated_at"),
    }


def _purge_stale_cache_dir(cache_dir: Path) -> None:
    """清理残留但无 .svn 的目录，让首次 checkout 不会被 SVN 拒绝。"""
    import shutil

    if not cache_dir.exists():
        return
    try:
        shutil.rmtree(cache_dir)
    except OSError:
        # 如果删不掉就让 svn checkout 自己去抛错，不在这里掩盖。
        pass

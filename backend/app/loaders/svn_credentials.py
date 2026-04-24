"""SVN 远端访问凭据持久化（按登录用户隔离 + Fernet 加密落盘）。

设计要点：
- 文件结构按 `{ "<user_scope>": { "<host>": { "username", "password_cipher", "test_dir_url?" } } }`
  组织；user_scope = 登录用户名，避免不同登录用户之间共享 SVN 账号。
- 密码使用 `cryptography.fernet` 对称加密；密钥首次生成后写到
  `<runtime>/.svn-key` 并做 0600 权限收紧（Windows 下尽力而为，不抛异常）。
- 模块只暴露纯函数，不做缓存；每次调用都重新读盘，避免多 worker 进程不一致。
"""

from __future__ import annotations

import json
import os
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from backend.config import settings


_FILE_LOCK = threading.Lock()


@dataclass(frozen=True)
class SvnCredential:
    """单个 host 维度的 SVN 凭据。"""

    host: str
    username: str
    password: str
    updated_at: str | None = None
    test_dir_url: str | None = None


def _get_or_create_fernet() -> Fernet:
    """读取或首次生成对称密钥。"""
    key_path = settings.svn_credentials_key_path
    key_path.parent.mkdir(parents=True, exist_ok=True)

    if key_path.exists():
        key_bytes = key_path.read_bytes().strip()
        if key_bytes:
            return Fernet(key_bytes)

    new_key = Fernet.generate_key()
    key_path.write_bytes(new_key)
    _harden_file_permission(key_path)
    return Fernet(new_key)


def _harden_file_permission(path: Path) -> None:
    """尽力把文件权限收紧到 0600。"""
    if sys.platform == "win32":
        return
    try:  # pragma: no cover - 仅在类 Unix 环境生效
        os.chmod(path, 0o600)
    except OSError:
        return


def _read_store() -> dict[str, dict[str, dict[str, str]]]:
    """读取整份凭据存储。"""
    store_path = settings.svn_credentials_path
    if not store_path.exists():
        return {}

    try:
        raw = store_path.read_text(encoding="utf-8")
        if not raw.strip():
            return {}
        loaded = json.loads(raw)
        if not isinstance(loaded, dict):
            return {}
        return loaded
    except (OSError, json.JSONDecodeError):
        return {}


def _write_store(store: dict[str, dict[str, dict[str, str]]]) -> None:
    """整份覆盖写回凭据存储。"""
    store_path = settings.svn_credentials_path
    store_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(store, ensure_ascii=False, indent=2)
    store_path.write_text(payload, encoding="utf-8")
    _harden_file_permission(store_path)


def _normalize_scope(user_scope: str | None) -> str:
    """user_scope 为空时归一化为 `__global__`，便于单测与未授权的旧调用。"""
    return (user_scope or "").strip() or "__global__"


def _normalize_host(host: str) -> str:
    """统一 host 大小写，避免 SAMOSVN / samosvn 同时存在两份凭据。"""
    return host.strip().lower()


def save_credentials(
    *,
    host: str,
    username: str,
    password: str,
    user_scope: str | None,
    test_dir_url: str | None = None,
) -> SvnCredential:
    """保存或更新某 host 的凭据，返回脱敏后的快照。"""
    normalized_host = _normalize_host(host)
    if not normalized_host:
        raise ValueError("host 不能为空。")
    if not username.strip():
        raise ValueError("username 不能为空。")
    if not password:
        raise ValueError("password 不能为空。")

    fernet = _get_or_create_fernet()
    cipher = fernet.encrypt(password.encode("utf-8")).decode("ascii")
    scope = _normalize_scope(user_scope)
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with _FILE_LOCK:
        store = _read_store()
        scope_bucket = store.setdefault(scope, {})
        scope_bucket[normalized_host] = {
            "username": username.strip(),
            "password_cipher": cipher,
            "updated_at": timestamp,
            "test_dir_url": (test_dir_url or "").strip() or None,
        }
        _write_store(store)

    return SvnCredential(
        host=normalized_host,
        username=username.strip(),
        password=password,
        updated_at=timestamp,
        test_dir_url=(test_dir_url or "").strip() or None,
    )


def load_credentials(
    *,
    host: str,
    user_scope: str | None,
) -> SvnCredential | None:
    """按 (user_scope, host) 读取凭据，找不到返回 None。"""
    normalized_host = _normalize_host(host)
    if not normalized_host:
        return None

    scope = _normalize_scope(user_scope)

    with _FILE_LOCK:
        store = _read_store()
        entry = store.get(scope, {}).get(normalized_host)

    if not entry:
        return None

    cipher = entry.get("password_cipher", "")
    if not cipher:
        return None

    try:
        password = _get_or_create_fernet().decrypt(cipher.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None

    return SvnCredential(
        host=normalized_host,
        username=str(entry.get("username", "")),
        password=password,
        updated_at=entry.get("updated_at"),
        test_dir_url=(str(entry.get("test_dir_url", "")).strip() or None),
    )


def list_hosts(*, user_scope: str | None) -> list[dict[str, str]]:
    """列出当前 user_scope 下已保存的 host（不含密码）。"""
    scope = _normalize_scope(user_scope)
    with _FILE_LOCK:
        store = _read_store()
        bucket = store.get(scope, {})

    items: list[dict[str, str]] = []
    for host, entry in sorted(bucket.items()):
        items.append(
            {
                "host": host,
                "username": str(entry.get("username", "")),
                "updated_at": str(entry.get("updated_at") or ""),
                "test_dir_url": (str(entry.get("test_dir_url", "")).strip() or None),
            }
        )
    return items


def delete_credentials(*, host: str, user_scope: str | None) -> bool:
    """删除某 (user_scope, host) 凭据，返回是否真的删除了。"""
    normalized_host = _normalize_host(host)
    if not normalized_host:
        return False

    scope = _normalize_scope(user_scope)
    with _FILE_LOCK:
        store = _read_store()
        bucket = store.get(scope, {})
        if normalized_host not in bucket:
            return False
        del bucket[normalized_host]
        if not bucket:
            store.pop(scope, None)
        _write_store(store)
    return True

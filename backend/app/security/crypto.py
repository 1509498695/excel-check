"""应用级对称加密 helper：基于 Fernet，复用 SVN 凭据使用的密钥文件。

设计要点：
- 复用 ``settings.svn_credentials_key_path`` 作为统一的 Fernet 密钥文件，保证一台部署只
  需要维护一把对称密钥；首次访问时自动生成。
- 仅暴露纯函数 ``encrypt_secret`` / ``decrypt_secret`` 给业务层使用，避免业务层直接
  接触 Fernet 实例。
- 输入空串视为“空配置”，加解密都返回空串，不抛异常；解密失败统一抛 ``ValueError``，
  方便上层翻译为 400 错误码。
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from backend.config import settings


_KEY_LOCK = threading.Lock()


def _harden_file_permission(path: Path) -> None:
    """尽力把密钥文件权限收紧到 0600（与 SVN 凭据 helper 行为一致）。"""
    if sys.platform == "win32":
        return
    try:  # pragma: no cover - 仅在类 Unix 环境生效
        os.chmod(path, 0o600)
    except OSError:
        return


def _resolve_key_path() -> Path:
    """返回当前应用使用的 Fernet 密钥文件路径。"""
    return settings.svn_credentials_key_path


def get_or_create_app_fernet() -> Fernet:
    """读取或首次生成 Fernet 实例；密钥文件不存在时自动写入新密钥。"""
    key_path = _resolve_key_path()
    with _KEY_LOCK:
        key_path.parent.mkdir(parents=True, exist_ok=True)
        if key_path.exists():
            key_bytes = key_path.read_bytes().strip()
            if key_bytes:
                return Fernet(key_bytes)
        new_key = Fernet.generate_key()
        key_path.write_bytes(new_key)
        _harden_file_permission(key_path)
        return Fernet(new_key)


def encrypt_secret(plain: str) -> str:
    """加密任意明文字符串，返回 ASCII 密文；空串原样返回。"""
    if not plain:
        return ""
    fernet = get_or_create_app_fernet()
    return fernet.encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_secret(cipher: str) -> str:
    """解密 ``encrypt_secret`` 输出的密文；空串原样返回，无法解密时抛 ``ValueError``。"""
    if not cipher:
        return ""
    fernet = get_or_create_app_fernet()
    try:
        return fernet.decrypt(cipher.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise ValueError("密文无法解密，可能是密钥文件已变更或数据被篡改。") from exc

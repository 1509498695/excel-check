"""SVN 数据同步与能力探测。"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from backend.app.api.schemas import DataSource
from backend.config import settings


def resolve_svn_executable() -> str | None:
    """解析当前环境中可用的 SVN 可执行文件。"""
    configured = _normalize_executable_token(settings.svn_executable)
    resolved = _resolve_configured_executable(configured)
    if resolved is not None:
        return resolved

    if not _is_windows_environment():
        return None

    for candidate in _iter_windows_svn_executables():
        if candidate.is_file():
            return str(candidate.resolve(strict=False))

    return None


def update_svn_working_copy(working_copy: Path) -> dict[str, Any]:
    """对指定目录执行一次 SVN update。"""
    executable = resolve_svn_executable()
    if executable is None:
        raise NotImplementedError(
            "当前环境未检测到 svn 命令，请先安装 SVN CLI，或在后端配置中指定 svn 可执行文件路径。"
        )

    if not working_copy.exists():
        raise FileNotFoundError(f"SVN 工作目录不存在：'{working_copy}'。")
    if not working_copy.is_dir():
        raise ValueError(f"SVN 更新目标不是目录：'{working_copy}'。")

    completed = subprocess.run(
        [executable, "update"],
        cwd=str(working_copy),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=False,
    )

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    combined_output = "\n".join(part for part in (stdout, stderr) if part).strip()
    lower_output = combined_output.lower()

    if completed.returncode != 0:
        if "not a working copy" in lower_output:
            raise ValueError(f"目标目录不是 SVN 工作副本：'{working_copy}'。")
        raise ValueError(
            f"SVN 更新失败：{combined_output or '命令返回非零退出码。'}"
        )

    return {
        "output": combined_output,
        "used_executable": executable,
    }


def sync_svn_source(source: DataSource) -> None:
    """按数据源配置执行一次 SVN update。"""
    raw_path = source.path or source.pathOrUrl
    if not raw_path:
        raise ValueError(f"SVN source '{source.id}' 缺少 path 或 pathOrUrl。")

    source_path = Path(raw_path).expanduser()
    working_copy = source_path if source_path.is_dir() else source_path.parent
    update_svn_working_copy(working_copy)


def _normalize_executable_token(raw_value: str) -> str:
    """规整配置中的 SVN 命令或路径。"""
    return raw_value.strip().strip('"').strip("'")


def _resolve_configured_executable(configured: str) -> str | None:
    """先按显式配置和 PATH 解析 SVN 可执行文件。"""
    if not configured:
        return None

    configured_path = Path(configured).expanduser()
    if configured_path.is_file():
        return str(configured_path.resolve(strict=False))

    discovered = shutil.which(configured)
    if discovered:
        return discovered

    return None


def _is_windows_environment() -> bool:
    """返回当前是否处于 Windows 运行环境。"""
    return os.name == "nt"


def _iter_windows_svn_executables() -> list[Path]:
    """在 Windows 上按常见安装位置枚举可用的 SVN CLI。"""
    candidates: list[Path] = []

    for raw_value in _read_tortoisesvn_registry_values():
        candidates.extend(_expand_windows_install_value(raw_value))

    for env_name in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
        root = os.environ.get(env_name, "").strip()
        if not root:
            continue
        candidates.append(Path(root) / "TortoiseSVN" / "bin" / "svn.exe")

    candidates.extend(
        [
            Path(r"C:\Program Files\TortoiseSVN\bin\svn.exe"),
            Path(r"C:\Program Files (x86)\TortoiseSVN\bin\svn.exe"),
        ]
    )

    unique_candidates: list[Path] = []
    seen_keys: set[str] = set()
    for candidate in candidates:
        normalized = str(candidate).strip()
        if not normalized:
            continue
        candidate_path = Path(normalized)
        key = str(candidate_path).lower()
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique_candidates.append(candidate_path)

    return unique_candidates


def _read_tortoisesvn_registry_values() -> list[str]:
    """从注册表读取 TortoiseSVN 安装信息。"""
    try:
        import winreg
    except ImportError:
        return []

    values: list[str] = []
    registry_keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\TortoiseSVN"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\TortoiseSVN"),
    ]
    value_names = ("Directory", "ProcPath", "CachePath", "TMergePath")

    for hive, subkey in registry_keys:
        try:
            with winreg.OpenKey(hive, subkey) as registry_key:
                for value_name in value_names:
                    try:
                        value, _ = winreg.QueryValueEx(registry_key, value_name)
                    except OSError:
                        continue
                    if isinstance(value, str) and value.strip():
                        values.append(_normalize_executable_token(value))
        except OSError:
            continue

    return values


def _expand_windows_install_value(raw_value: str) -> list[Path]:
    """把注册表中的目录或可执行文件路径展开为 SVN 候选路径。"""
    normalized = _normalize_executable_token(raw_value)
    if not normalized:
        return []

    value_path = Path(normalized)
    lower_name = value_path.name.lower()

    if lower_name == "svn.exe":
        return [value_path]
    if lower_name.endswith(".exe"):
        return [value_path.parent / "svn.exe"]
    return [value_path / "svn.exe", value_path / "bin" / "svn.exe"]

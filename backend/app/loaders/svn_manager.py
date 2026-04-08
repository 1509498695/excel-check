"""SVN 数据同步与能力探测。"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from backend.app.api.schemas import DataSource
from backend.config import settings


def resolve_svn_executable() -> str | None:
    """解析当前环境中可用的 SVN 可执行文件。"""
    configured = settings.svn_executable.strip()
    configured_path = Path(configured)
    if configured_path.exists():
        return str(configured_path)
    return shutil.which(configured)


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

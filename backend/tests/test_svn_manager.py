"""SVN 可执行文件发现与工作副本更新测试。"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from backend.app.loaders import svn_manager
from backend.config import Settings


def test_resolve_svn_executable_prefers_configured_absolute_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """显式配置为绝对路径时，应优先直接命中。"""
    executable_path = tmp_path / "svn.exe"
    executable_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        svn_manager,
        "settings",
        Settings(svn_executable=str(executable_path)),
    )
    monkeypatch.setattr(svn_manager.shutil, "which", lambda _: None)

    resolved = svn_manager.resolve_svn_executable()

    assert resolved == str(executable_path.resolve())


def test_resolve_svn_executable_falls_back_to_path_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """显式配置未命中时，应继续尝试 PATH。"""
    discovered_path = r"C:\tools\svn.exe"
    monkeypatch.setattr(
        svn_manager,
        "settings",
        Settings(svn_executable="svn"),
    )
    monkeypatch.setattr(svn_manager.shutil, "which", lambda _: discovered_path)

    resolved = svn_manager.resolve_svn_executable()

    assert resolved == discovered_path


def test_resolve_svn_executable_uses_windows_auto_detection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """当 PATH 未命中时，应能继续走 Windows 自动探测。"""
    executable_path = tmp_path / "svn.exe"
    executable_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        svn_manager,
        "settings",
        Settings(svn_executable="svn"),
    )
    monkeypatch.setattr(svn_manager.shutil, "which", lambda _: None)
    monkeypatch.setattr(svn_manager, "_is_windows_environment", lambda: True)
    monkeypatch.setattr(
        svn_manager,
        "_iter_windows_svn_executables",
        lambda: [executable_path],
    )

    resolved = svn_manager.resolve_svn_executable()

    assert resolved == str(executable_path.resolve())


def test_update_svn_working_copy_returns_output_and_used_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """更新成功时，应返回输出和实际使用的可执行文件。"""
    executable_path = tmp_path / "svn.exe"
    working_copy = tmp_path / "working-copy"
    executable_path.write_text("", encoding="utf-8")
    working_copy.mkdir()
    monkeypatch.setattr(
        svn_manager,
        "resolve_svn_executable",
        lambda: str(executable_path.resolve()),
    )
    monkeypatch.setattr(
        svn_manager.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="At revision 449834.\n",
            stderr="",
        ),
    )

    result = svn_manager.update_svn_working_copy(working_copy)

    assert result["used_executable"] == str(executable_path.resolve())
    assert "449834" in result["output"]


def test_update_svn_working_copy_raises_clear_error_when_cli_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """当前环境无法发现 svn CLI 时，应返回明确中文提示。"""
    working_copy = tmp_path / "working-copy"
    working_copy.mkdir()
    monkeypatch.setattr(svn_manager, "resolve_svn_executable", lambda: None)

    with pytest.raises(NotImplementedError, match="svn 命令"):
        svn_manager.update_svn_working_copy(working_copy)

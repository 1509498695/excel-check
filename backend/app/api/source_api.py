"""数据源相关接口。"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.app.api.schemas import DataSource
from backend.app.loaders.local_reader import (
    preview_composite_variable,
    preview_source_column,
    read_source_metadata,
)
from backend.config import settings


router = APIRouter(prefix="/sources", tags=["sources"])

LOCAL_PICK_SUFFIXES: dict[str, tuple[str, ...]] = {
    "local_excel": (".xlsx", ".xls"),
    "local_csv": (".csv",),
}


class LocalPickRequest(BaseModel):
    """本地文件选择请求。"""

    model_config = ConfigDict(extra="forbid")

    source_type: Literal["local_excel", "local_csv"]


class ColumnPreviewRequest(BaseModel):
    """单列预览请求。"""

    model_config = ConfigDict(extra="forbid")

    source: DataSource
    sheet: str
    column: str
    limit: int | None = Field(default=None, ge=1, le=20000)


class CompositePreviewRequest(BaseModel):
    """组合变量预览请求。"""

    model_config = ConfigDict(extra="forbid")

    source: DataSource
    sheet: str
    columns: list[str] = Field(default_factory=list)
    key_column: str
    append_index_to_key: bool = False


def _get_pick_filetypes(source_type: str) -> list[tuple[str, str]]:
    """返回 tkinter 文件对话框需要的文件类型。"""
    if source_type == "local_excel":
        return [("Excel 文件", "*.xlsx *.xls")]
    if source_type == "local_csv":
        return [("CSV 文件", "*.csv")]
    raise ValueError(f"暂不支持 {source_type} 的本地文件选择。")


# 以独立子进程运行 tkinter 文件选择框，避免在长生命周期的 FastAPI/uvicorn
# 主进程里残留 Tcl 解释器与窗口焦点资源；子进程退出后所有 GUI 资源会被
# 操作系统一并回收，前后端事件循环也不会被阻塞或挂起。
_PICKER_SUBPROCESS_SCRIPT = textwrap.dedent(
    """
    import json
    import sys
    import tkinter as tk
    from tkinter import filedialog

    config = json.loads(sys.argv[1])
    filetypes = [tuple(item) for item in config.get("filetypes", [])]

    root = tk.Tk()
    try:
        root.withdraw()
        root.attributes("-topmost", True)
        root.update()
        selected_path = filedialog.askopenfilename(
            title=config.get("title", "选择文件"),
            filetypes=filetypes,
        )
    finally:
        try:
            root.destroy()
        except Exception:
            pass

    sys.stdout.write(selected_path or "")
    """
).strip()

_PICKER_SUBPROCESS_TIMEOUT_SECONDS = 600


def _validate_selected_path(source_type: str, selected_path: str) -> str:
    """校验系统文件框返回的真实路径。"""
    if not selected_path:
        return ""

    path = Path(selected_path).expanduser()
    suffix = path.suffix.lower()
    allowed_suffixes = LOCAL_PICK_SUFFIXES[source_type]

    if suffix not in allowed_suffixes:
        allowed_text = "、".join(sorted(allowed_suffixes))
        raise HTTPException(
            status_code=400,
            detail=(
                f"{source_type} 仅支持 {allowed_text} 文件，当前选择为 "
                f"{suffix or '无后缀文件'}。"
            ),
        )

    if not path.exists():
        raise HTTPException(status_code=400, detail=f"所选文件不存在：{path}")
    if not path.is_file():
        raise HTTPException(status_code=400, detail=f"所选路径不是文件：{path}")

    return str(path.resolve())


def _show_local_file_dialog(source_type: str) -> str:
    """在独立子进程中弹出系统文件选择框并返回真实路径。

    采用子进程隔离的原因：
    - tkinter 在长期运行的 uvicorn 主进程里反复创建/销毁 Tk 根窗口，
      容易在 Windows 上残留焦点抢占与 Tcl 资源，进而引发后续请求被卡住。
    - 子进程方案让每次选择都在干净环境里创建并销毁 GUI，事件循环不会被
      阻塞，前端连续选择文件也不会越用越慢。
    """

    config = {
        "title": "选择本地配置文件",
        "filetypes": _get_pick_filetypes(source_type),
    }

    try:
        completed = subprocess.run(
            [sys.executable, "-c", _PICKER_SUBPROCESS_SCRIPT, json.dumps(config)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=_PICKER_SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as error:  # pragma: no cover - 缺少 Python 解释器
        raise RuntimeError(
            "当前环境无法启动本机文件选择子进程，请手动输入本地文件路径。"
        ) from error
    except subprocess.TimeoutExpired as error:  # pragma: no cover - 用户长时间未操作
        raise RuntimeError("系统文件选择框等待超时，请重试。") from error

    if completed.returncode != 0:  # pragma: no cover - 真实桌面环境问题
        stderr_text = (completed.stderr or "").strip() or "未知错误"
        raise RuntimeError(f"系统文件选择框打开失败：{stderr_text}")

    return (completed.stdout or "").strip()


@router.get("/capabilities")
def get_source_capabilities() -> dict[str, Any]:
    """返回当前后端声明支持的数据源能力。"""
    return {
        "code": 200,
        "msg": "ok",
        "data": {
            "source_types": list(settings.supported_source_types),
            "implemented": False,
        },
    }


@router.post("/local-pick")
async def pick_local_source_file(payload: LocalPickRequest) -> dict[str, Any]:
    """在本机弹出系统文件选择框，并返回真实本地路径。"""
    try:
        selected_path = _show_local_file_dialog(payload.source_type)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    if not selected_path:
        return {
            "code": 204,
            "msg": "cancelled",
            "data": {
                "selected_path": "",
                "source_type": payload.source_type,
            },
        }

    resolved_path = _validate_selected_path(payload.source_type, selected_path)
    return {
        "code": 200,
        "msg": "ok",
        "data": {
            "selected_path": resolved_path,
            "source_type": payload.source_type,
        },
    }


@router.post("/metadata")
async def get_source_metadata(source: DataSource) -> dict[str, Any]:
    """返回变量池构建所需的 Sheet 与列结构。"""
    try:
        metadata = read_source_metadata(source)
    except (FileNotFoundError, ValueError, ImportError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {
        "code": 200,
        "msg": "ok",
        "data": metadata,
    }


@router.post("/column-preview")
async def get_source_column_preview(payload: ColumnPreviewRequest) -> dict[str, Any]:
    """返回单个变量详情弹窗所需的列预览数据。"""
    try:
        preview = preview_source_column(
            payload.source,
            sheet_name=payload.sheet,
            column_name=payload.column,
            limit=payload.limit,
        )
    except (FileNotFoundError, ValueError, ImportError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {
        "code": 200,
        "msg": "ok",
        "data": preview,
    }


@router.post("/composite-preview")
async def get_composite_variable_preview(payload: CompositePreviewRequest) -> dict[str, Any]:
    """返回组合变量所需的 JSON 映射预览。"""
    try:
        preview = preview_composite_variable(
            payload.source,
            sheet_name=payload.sheet,
            columns=payload.columns,
            key_column=payload.key_column,
            append_index_to_key=payload.append_index_to_key,
        )
    except (FileNotFoundError, ValueError, ImportError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {
        "code": 200,
        "msg": "ok",
        "data": preview,
    }

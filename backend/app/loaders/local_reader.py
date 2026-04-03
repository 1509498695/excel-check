"""本地 Excel/CSV 数据读取工具。"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any, TypeVar

import pandas as pd

from backend.app.api.schemas import DataSource, VariableTag


LOCAL_SOURCE_TYPES = {"local_excel", "local_csv"}
ItemT = TypeVar("ItemT")


def load_local_variables(
    sources: list[DataSource], variables: list[VariableTag]
) -> dict[str, pd.DataFrame]:
    """按变量标签聚合读取本地 Excel/CSV 数据切片。"""
    if not variables:
        return {}

    # 先校验 tag 全局唯一，避免后续结果字典被覆盖。
    _ensure_unique_tags(variables)

    source_map = {source.id: source for source in sources}
    grouped_variables: dict[str, list[VariableTag]] = defaultdict(list)

    for variable in variables:
        source = source_map.get(variable.source_id)
        if source is None:
            raise ValueError(
                f"Variable tag '{variable.tag}' references unknown source_id "
                f"'{variable.source_id}'."
            )
        if source.type not in LOCAL_SOURCE_TYPES:
            continue
        # 仅按 source_id 聚合同一数据源的变量，后续再按 source.type 分发。
        grouped_variables[variable.source_id].append(variable)

    loaded_variables: dict[str, pd.DataFrame] = {}

    for source_id, variables_for_source in grouped_variables.items():
        source = source_map[source_id]
        # 统一走分发函数，后面接入 feishu/svn 时可保持同样调用方式。
        source_frames = load_variables_by_source(source, variables_for_source)
        overlap_tags = set(loaded_variables).intersection(source_frames)
        if overlap_tags:
            raise ValueError(
                f"Duplicate variable tags produced while loading source "
                f"'{source.id}': {sorted(overlap_tags)}."
            )
        loaded_variables.update(source_frames)

    return loaded_variables


def read_source_metadata(source: DataSource) -> dict[str, Any]:
    """读取 Excel 数据源的 Sheet 与列结构，用于变量池下拉构建。"""
    _ensure_excel_metadata_source(source)
    source_path = _resolve_local_path(source)

    try:
        workbook = pd.ExcelFile(
            source_path,
            engine=_get_excel_engine(source_path),
        )
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Excel 数据源 '{source.id}' 文件不存在：'{source_path}'。"
        ) from exc
    except ImportError as exc:
        raise ImportError(_build_excel_dependency_error(source_path)) from exc
    except ValueError as exc:
        raise ValueError(
            f"读取 Excel 数据源 '{source.id}' 失败：{exc}"
        ) from exc

    sheets: list[dict[str, Any]] = []
    for sheet_name in workbook.sheet_names:
        try:
            sheet_frame = workbook.parse(sheet_name=sheet_name, nrows=0)
        except ValueError as exc:
            raise ValueError(
                f"读取 Excel 数据源 '{source.id}' 的 Sheet '{sheet_name}' 失败：{exc}"
            ) from exc

        sheets.append(
            {
                "name": sheet_name,
                "columns": [str(column) for column in sheet_frame.columns.tolist()],
            }
        )

    return {
        "source_id": source.id,
        "source_type": source.type,
        "sheets": sheets,
    }


def preview_source_column(
    source: DataSource,
    *,
    sheet_name: str,
    column_name: str,
    limit: int | None = None,
) -> dict[str, Any]:
    """返回指定列的预览数据，供变量详情弹窗展示。"""
    _ensure_excel_metadata_source(source)
    source_path = _resolve_local_path(source)

    cleaned_sheet = sheet_name.strip()
    cleaned_column = column_name.strip()
    if not cleaned_sheet:
        raise ValueError("变量详情预览缺少 Sheet 名称。")
    if not cleaned_column:
        raise ValueError("变量详情预览缺少列名。")

    try:
        dataframe = pd.read_excel(
            source_path,
            sheet_name=cleaned_sheet,
            usecols=[cleaned_column],
            engine=_get_excel_engine(source_path),
        )
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Excel 数据源 '{source.id}' 文件不存在：'{source_path}'。"
        ) from exc
    except ImportError as exc:
        raise ImportError(_build_excel_dependency_error(source_path)) from exc
    except ValueError as exc:
        raise ValueError(
            f"读取 Excel 数据源 '{source.id}' 的 Sheet '{cleaned_sheet}' 列 "
            f"'{cleaned_column}' 失败：{exc}"
        ) from exc

    total_rows = int(len(dataframe))
    preview_limit = max(1, limit) if limit is not None else total_rows
    preview_frame = dataframe if limit is None else dataframe.head(preview_limit)
    preview_rows = [
        {
            "row_index": int(row_index),
            "value": _normalize_preview_value(value),
        }
        for row_index, value in zip(
            preview_frame.index + 2,
            preview_frame[cleaned_column].tolist(),
        )
    ]

    return {
        "source_id": source.id,
        "source_type": source.type,
        "source_path": str(source_path),
        "sheet": cleaned_sheet,
        "column": cleaned_column,
        "preview_rows": preview_rows,
        "total_rows": total_rows,
        "loaded_rows": len(preview_rows),
        "loaded_all_rows": len(preview_rows) == total_rows,
        "preview_limit": preview_limit,
    }


def load_variables_by_source(
    source: DataSource, variables_for_source: list[VariableTag]
) -> dict[str, pd.DataFrame]:
    """按数据源类型分发到具体的本地读取实现。"""
    if source.type == "local_excel":
        return read_local_excel(source, variables_for_source)
    if source.type == "local_csv":
        return read_local_csv(source, variables_for_source)
    raise ValueError(
        f"Source '{source.id}' has unsupported local loader type '{source.type}'."
    )


def read_local_excel(
    source: DataSource, variables_for_source: list[VariableTag]
) -> dict[str, pd.DataFrame]:
    """读取 Excel 中指定 sheet 的指定列，并按 tag 返回结果。"""
    if not variables_for_source:
        return {}

    source_path = _resolve_local_path(source)
    variables_by_sheet: dict[str, list[VariableTag]] = defaultdict(list)

    for variable in variables_for_source:
        # Excel 必须显式指定 sheet；空字符串通常意味着前端配置不完整。
        if not variable.sheet.strip():
            raise ValueError(
                f"Excel source '{source.id}' requires a non-empty sheet for "
                f"variable tag '{variable.tag}'."
            )
        variables_by_sheet[variable.sheet].append(variable)

    loaded_variables: dict[str, pd.DataFrame] = {}

    for sheet_name, sheet_variables in variables_by_sheet.items():
        # 同一 sheet 的多个列一次性读取，避免重复打开工作表并降低内存消耗。
        requested_columns = _unique_preserve_order(
            variable.column for variable in sheet_variables
        )
        try:
            dataframe = pd.read_excel(
                source_path,
                sheet_name=sheet_name,
                usecols=requested_columns,
                engine=_get_excel_engine(source_path),
            )
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"Excel source '{source.id}' file not found: '{source_path}'."
            ) from exc
        except ImportError as exc:
            raise ImportError(_build_excel_dependency_error(source_path)) from exc
        except ValueError as exc:
            raise ValueError(
                f"Failed to read Excel source '{source.id}', sheet '{sheet_name}', "
                f"columns {requested_columns}: {exc}"
            ) from exc

        _merge_loaded_columns(
            loaded_variables,
            dataframe=dataframe,
            variables_for_group=sheet_variables,
            source_id=source.id,
            group_label=f"sheet '{sheet_name}'",
        )

    return loaded_variables


def read_local_csv(
    source: DataSource, variables_for_source: list[VariableTag]
) -> dict[str, pd.DataFrame]:
    """读取 CSV 中指定列，并按 tag 返回结果。"""
    if not variables_for_source:
        return {}

    source_path = _resolve_local_path(source)
    # CSV 没有 sheet 概念，因此直接合并当前 source 下的所有目标列。
    requested_columns = _unique_preserve_order(
        variable.column for variable in variables_for_source
    )

    try:
        dataframe = pd.read_csv(source_path, usecols=requested_columns)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"CSV source '{source.id}' file not found: '{source_path}'."
        ) from exc
    except ValueError as exc:
        raise ValueError(
            f"Failed to read CSV source '{source.id}', columns "
            f"{requested_columns}: {exc}"
        ) from exc

    loaded_variables: dict[str, pd.DataFrame] = {}
    _merge_loaded_columns(
        loaded_variables,
        dataframe=dataframe,
        variables_for_group=variables_for_source,
        source_id=source.id,
        group_label="csv",
    )
    return loaded_variables


def _ensure_excel_metadata_source(source: DataSource) -> None:
    """限制变量池元数据读取仅支持 Excel 数据源。"""
    if source.type != "local_excel":
        raise ValueError("变量池下拉提取第一版仅支持 Excel 数据源。")


def _ensure_unique_tags(variables: list[VariableTag]) -> None:
    # tag 是变量池中的全局唯一键，重复时会导致结果覆盖，因此提前拦截。
    seen_tags: set[str] = set()
    duplicate_tags: set[str] = set()

    for variable in variables:
        if variable.tag in seen_tags:
            duplicate_tags.add(variable.tag)
        seen_tags.add(variable.tag)

    if duplicate_tags:
        raise ValueError(
            f"Duplicate variable tags are not allowed: {sorted(duplicate_tags)}."
        )


def _resolve_local_path(source: DataSource) -> Path:
    # 本地路径优先使用 path，pathOrUrl 作为兼容字段回退。
    raw_path = source.path or source.pathOrUrl
    if not raw_path:
        raise ValueError(
            f"Local source '{source.id}' must provide 'path' or 'pathOrUrl'."
        )

    source_path = Path(raw_path).expanduser()
    # 这里同时校验“存在”与“是文件”，避免把目录误当成数据源。
    if not source_path.exists():
        raise FileNotFoundError(
            f"Local source '{source.id}' file not found: '{source_path}'."
        )
    if not source_path.is_file():
        raise ValueError(
            f"Local source '{source.id}' path is not a file: '{source_path}'."
        )
    return source_path


def _merge_loaded_columns(
    target: dict[str, pd.DataFrame],
    *,
    dataframe: pd.DataFrame,
    variables_for_group: list[VariableTag],
    source_id: str,
    group_label: str,
) -> None:
    # 将一次批量读取的 DataFrame 再拆成按 tag 索引的单列结果。
    for variable in variables_for_group:
        if variable.column not in dataframe.columns:
            raise ValueError(
                f"Source '{source_id}' {group_label} does not contain column "
                f"'{variable.column}' for variable tag '{variable.tag}'."
            )
        if variable.tag in target:
            raise ValueError(
                f"Duplicate variable tag '{variable.tag}' encountered while "
                f"loading source '{source_id}'."
            )
        target[variable.tag] = _build_variable_frame(dataframe, variable.column)


def _build_variable_frame(dataframe: pd.DataFrame, column_name: str) -> pd.DataFrame:
    # 返回单列 DataFrame 而不是 Series，方便后续统一追加元数据。
    variable_frame = dataframe[[column_name]].copy()
    # 表格首行为表头，因此第一条真实数据对应 Excel/CSV 的第 2 行。
    variable_frame["_row_index"] = variable_frame.index + 2
    return variable_frame


def _get_excel_engine(source_path: Path) -> str:
    """按扩展名显式选择 Excel 引擎，保证 xls 与 xlsx 行为清晰。"""
    if source_path.suffix.lower() == ".xls":
        return "xlrd"
    return "openpyxl"


def _build_excel_dependency_error(source_path: Path) -> str:
    """生成 Excel 依赖缺失时的统一提示。"""
    if source_path.suffix.lower() == ".xls":
        return (
            "读取 .xls 文件需要安装 xlrd 依赖，请执行 "
            "`pip install -r backend/requirements.txt` 或单独安装 `xlrd`。"
        )

    return (
        "读取 .xlsx 文件需要安装 openpyxl 依赖，请执行 "
        "`pip install -r backend/requirements.txt` 或单独安装 `openpyxl`。"
    )


def _normalize_preview_value(value: Any) -> Any:
    """把 Pandas/Numpy 值转换为可直接返回给前端的 JSON 兼容结构。"""
    if pd.isna(value):
        return None

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError):
            return value

    return value


def _unique_preserve_order(items: Iterable[ItemT]) -> list[ItemT]:
    # 去重但保持原有顺序，避免 usecols 顺序被打乱。
    return list(dict.fromkeys(items))

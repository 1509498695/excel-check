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
        grouped_variables[variable.source_id].append(variable)

    loaded_variables: dict[str, pd.DataFrame] = {}

    for source_id, variables_for_source in grouped_variables.items():
        source_frames = load_variables_by_source(source_map[source_id], variables_for_source)
        overlap_tags = set(loaded_variables).intersection(source_frames)
        if overlap_tags:
            raise ValueError(
                "Duplicate variable tags produced while loading source "
                f"'{source_id}': {sorted(overlap_tags)}."
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
        raise ValueError(f"读取 Excel 数据源 '{source.id}' 失败：{exc}") from exc

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
        "variable_kind": "single",
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


def preview_composite_variable(
    source: DataSource,
    *,
    sheet_name: str,
    columns: list[str],
    key_column: str,
) -> dict[str, Any]:
    """返回同一数据源同一 Sheet 内多列组合后的 JSON 映射预览。"""
    _ensure_excel_metadata_source(source)
    source_path = _resolve_local_path(source)

    cleaned_sheet = sheet_name.strip()
    cleaned_columns = [column.strip() for column in columns if column and column.strip()]
    cleaned_columns = _unique_preserve_order(cleaned_columns)
    cleaned_key_column = key_column.strip()

    if not cleaned_sheet:
        raise ValueError("组合变量预览缺少 Sheet 名称。")
    if len(cleaned_columns) < 2:
        raise ValueError("组合变量至少需要选择 2 列。")
    if not cleaned_key_column:
        raise ValueError("组合变量缺少 key 列。")
    if cleaned_key_column not in cleaned_columns:
        raise ValueError("组合变量的 key 列必须包含在关联列中。")

    try:
        dataframe = pd.read_excel(
            source_path,
            sheet_name=cleaned_sheet,
            usecols=cleaned_columns,
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
            f"读取 Excel 数据源 '{source.id}' 的 Sheet '{cleaned_sheet}' 组合列 "
            f"{cleaned_columns} 失败：{exc}"
        ) from exc

    mapping, loaded_rows = _build_composite_mapping(
        dataframe,
        columns=cleaned_columns,
        key_column=cleaned_key_column,
    )

    return {
        "variable_kind": "composite",
        "source_id": source.id,
        "source_type": source.type,
        "source_path": str(source_path),
        "sheet": cleaned_sheet,
        "columns": cleaned_columns,
        "key_column": cleaned_key_column,
        "mapping": mapping,
        "total_rows": int(len(dataframe)),
        "loaded_rows": loaded_rows,
        "loaded_all_rows": loaded_rows == int(len(dataframe)),
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
        if not variable.sheet.strip():
            raise ValueError(
                f"Excel source '{source.id}' requires a non-empty sheet for "
                f"variable tag '{variable.tag}'."
            )
        variables_by_sheet[variable.sheet].append(variable)

    loaded_variables: dict[str, pd.DataFrame] = {}

    for sheet_name, sheet_variables in variables_by_sheet.items():
        requested_columns = _collect_requested_columns(sheet_variables)
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

        _merge_loaded_variables(
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

    if any(_get_variable_kind(variable) == "composite" for variable in variables_for_source):
        raise ValueError("组合变量当前仅支持本地 Excel 数据源。")

    source_path = _resolve_local_path(source)
    requested_columns = _collect_requested_columns(variables_for_source)

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
    _merge_loaded_variables(
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
    """保证 tag 在整次请求中全局唯一。"""
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
    """解析本地文件路径，优先使用 path，其次回退到 pathOrUrl。"""
    raw_path = source.path or source.pathOrUrl
    if not raw_path:
        raise ValueError(
            f"Local source '{source.id}' must provide 'path' or 'pathOrUrl'."
        )

    source_path = Path(raw_path).expanduser()
    if not source_path.exists():
        raise FileNotFoundError(
            f"Local source '{source.id}' file not found: '{source_path}'."
        )
    if not source_path.is_file():
        raise ValueError(
            f"Local source '{source.id}' path is not a file: '{source_path}'."
        )
    return source_path


def _get_variable_kind(variable: VariableTag) -> str:
    """读取变量类型，兼容旧请求默认视为单个变量。"""
    return variable.variable_kind or "single"


def _collect_requested_columns(variables: list[VariableTag]) -> list[str]:
    """聚合一组变量真正依赖的列名。"""
    requested_columns: list[str] = []

    for variable in variables:
        if _get_variable_kind(variable) == "composite":
            columns = [
                column.strip()
                for column in (variable.columns or [])
                if column and column.strip()
            ]
            if len(columns) < 2:
                raise ValueError(
                    f"Composite variable '{variable.tag}' must provide at least two columns."
                )
            requested_columns.extend(columns)
            continue

        column_name = (variable.column or "").strip()
        if not column_name:
            raise ValueError(f"Variable '{variable.tag}' is missing column.")
        requested_columns.append(column_name)

    return _unique_preserve_order(requested_columns)


def _merge_loaded_variables(
    target: dict[str, pd.DataFrame],
    *,
    dataframe: pd.DataFrame,
    variables_for_group: list[VariableTag],
    source_id: str,
    group_label: str,
) -> None:
    """将批量读取结果拆成按 tag 索引的单变量或组合变量结果。"""
    for variable in variables_for_group:
        if variable.tag in target:
            raise ValueError(
                f"Duplicate variable tag '{variable.tag}' encountered while "
                f"loading source '{source_id}'."
            )

        if _get_variable_kind(variable) == "composite":
            columns = [column.strip() for column in (variable.columns or []) if column and column.strip()]
            key_column = (variable.key_column or "").strip()

            if len(columns) < 2:
                raise ValueError(
                    f"Composite variable '{variable.tag}' must provide at least two columns."
                )
            if not key_column:
                raise ValueError(
                    f"Composite variable '{variable.tag}' must provide key_column."
                )
            if key_column not in columns:
                raise ValueError(
                    f"Composite variable '{variable.tag}' requires key_column '{key_column}' "
                    "to be included in columns."
                )
            missing_columns = [column for column in columns if column not in dataframe.columns]
            if missing_columns:
                raise ValueError(
                    f"Source '{source_id}' {group_label} does not contain columns "
                    f"{missing_columns} for composite variable '{variable.tag}'."
                )

            target[variable.tag] = _build_composite_variable_frame(
                dataframe,
                columns=columns,
                key_column=key_column,
            )
            continue

        column_name = (variable.column or "").strip()
        if column_name not in dataframe.columns:
            raise ValueError(
                f"Source '{source_id}' {group_label} does not contain column "
                f"'{column_name}' for variable tag '{variable.tag}'."
            )
        target[variable.tag] = _build_variable_frame(dataframe, column_name)


def _build_variable_frame(dataframe: pd.DataFrame, column_name: str) -> pd.DataFrame:
    """返回单列 DataFrame，并统一附带真实表格行号。"""
    variable_frame = dataframe[[column_name]].copy()
    variable_frame["_row_index"] = variable_frame.index + 2
    return variable_frame


def _build_composite_variable_frame(
    dataframe: pd.DataFrame,
    *,
    columns: list[str],
    key_column: str,
) -> pd.DataFrame:
    """把组合变量展开为可执行的行集，并注入内部 `__key__` 字段。"""
    frame = dataframe[columns].copy()
    frame["__key__"] = frame[key_column].apply(_normalize_preview_value)
    frame = frame.loc[~frame["__key__"].apply(_is_empty_preview_value)].copy()
    frame["__key__"] = frame["__key__"].astype(str)
    frame = frame.drop(columns=[key_column])
    frame["_row_index"] = frame.index + 2
    ordered_columns = [
        "__key__",
        *[column for column in columns if column != key_column],
        "_row_index",
    ]
    return frame[ordered_columns].reset_index(drop=True)


def _build_composite_mapping(
    dataframe: pd.DataFrame,
    *,
    columns: list[str],
    key_column: str,
) -> tuple[dict[str, dict[str, Any]], int]:
    """基于 key 列把多列聚合成字典结构，并排除 key 列本身。"""
    mapping: dict[str, dict[str, Any]] = {}
    loaded_rows = 0

    for _, row in dataframe[columns].iterrows():
        raw_key = row[key_column]
        normalized_key = _normalize_preview_value(raw_key)
        if _is_empty_preview_value(normalized_key):
            continue

        key = str(normalized_key)
        if key in mapping:
            raise ValueError(
                f"组合变量的 key 列 '{key_column}' 存在重复值 '{key}'，无法生成唯一映射。"
            )

        mapping[key] = {
            column: _normalize_preview_value(row[column])
            for column in columns
            if column != key_column
        }
        loaded_rows += 1

    return mapping, loaded_rows


def _get_excel_engine(source_path: Path) -> str:
    """按扩展名显式选择 Excel 引擎。"""
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


def _is_empty_preview_value(value: Any) -> bool:
    """判断预览值是否为空，用于组合变量过滤空 key。"""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


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
    """去重但保持原有顺序，避免 usecols 顺序被打乱。"""
    return list(dict.fromkeys(items))

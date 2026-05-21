"""固定规则配置归一化时的元数据读取。"""

from __future__ import annotations

from backend.app.api.fixed_rules_schemas import FixedRulesConfigIssue
from backend.app.api.schemas import DataSource
from backend.app.fixed_rules.config_common import _append_config_issue, _resolve_identifier_against_available
from backend.app.loaders.local_reader import read_source_metadata


def _load_sheet_columns(
    *,
    source: DataSource,
    sheet_name: str,
    metadata_cache: dict[str, dict[str, object]],
    variable_tag: str | None = None,
    config_issues: list[FixedRulesConfigIssue] | None = None,
    issue_keys: set[tuple[str, str | None, str | None, str | None, str]] | None = None,
) -> tuple[str, list[str]] | None:
    """????????? Sheet ???????????"""
    metadata = metadata_cache.get(source.id)
    if metadata is None:
        try:
            metadata = read_source_metadata(source)
        except FileNotFoundError:
            if config_issues is None:
                raise
            _append_config_issue(
                config_issues,
                issue_keys,
                source_id=source.id,
                variable_tag=variable_tag,
                message=(
                    f"数据源“{source.id}”的本地路径已失效：{source.pathOrUrl or source.path or ''}。"
                    "请到“数据源接入管理”中修复路径后再保存或执行。"
                ),
            )
            metadata_cache[source.id] = {"sheets": [], "__missing__": True}
            return None
        metadata_cache[source.id] = metadata
    elif metadata.get("__missing__") or metadata.get("__unsupported_csv__"):
        return None

    try:
        resolved_sheet_name = _resolve_identifier_against_available(
            sheet_name,
            [str(sheet["name"]) for sheet in metadata["sheets"]],
            identifier_label="Sheet",
            context=f"数据源“{source.id}”",
        )
    except ValueError as exc:
        if config_issues is not None:
            _append_config_issue(
                config_issues,
                issue_keys,
                source_id=source.id,
                variable_tag=variable_tag,
                message=f"{exc}请到“数据源接入管理”或变量配置中修复后再保存或执行。",
            )
            return None
        raise

    for sheet in metadata["sheets"]:
        if sheet["name"] == resolved_sheet_name:
            return resolved_sheet_name, list(sheet["columns"])

    if config_issues is not None:
        _append_config_issue(
            config_issues,
            issue_keys,
            source_id=source.id,
            variable_tag=variable_tag,
            message=(
                f"变量“{variable_tag or sheet_name}”引用的 Sheet “{sheet_name}”已不存在。"
                "请到“变量池构建”中重新选择 Sheet 后再保存或执行。"
            ),
        )
        return None

    raise ValueError(f"固定规则变量引用的 Sheet '{sheet_name}' 不存在。")

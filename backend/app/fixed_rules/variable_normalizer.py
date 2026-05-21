"""固定规则变量归一化。"""

from __future__ import annotations

from backend.app.api.fixed_rules_schemas import FixedRulesConfigIssue
from backend.app.api.schemas import DataSource, VariableTag
from backend.app.fixed_rules.config_common import (
    _append_config_issue,
    _normalize_columns,
    _resolve_identifier_against_available,
    _resolve_identifiers_against_available,
)
from backend.app.fixed_rules.metadata_loader import _load_sheet_columns


def _normalize_variables(
    variables: list[VariableTag],
    *,
    source_map: dict[str, DataSource],
    metadata_cache: dict[str, dict[str, object]],
    config_issues: list[FixedRulesConfigIssue] | None = None,
    issue_keys: set[tuple[str, str | None, str | None, str | None, str]] | None = None,
) -> list[VariableTag]:
    """?????????????????"""
    normalized_variables: list[VariableTag] = []
    seen_tags: set[str] = set()

    for variable in variables:
        tag = variable.tag.strip()
        source_id = variable.source_id.strip()
        sheet = variable.sheet or ""
        variable_kind = (variable.variable_kind or "single").strip()

        if not tag:
            raise ValueError("???????? tag?")
        if tag in seen_tags:
            raise ValueError(f"???????????'{tag}'?")
        if source_id not in source_map:
            raise ValueError(f"?????? '{tag}' ?????????? '{source_id}'?")
        if not sheet.strip():
            raise ValueError(f"?????? '{tag}' ?? Sheet?")

        source = source_map[source_id]
        source_supports_variables = source.type in {"local_excel", "svn"}
        if not source_supports_variables:
            message = (
                f"项目校验变量仅支持 Excel 数据源，变量“{tag}”引用的数据源类型为“{source.type}”。"
            )
            if config_issues is None:
                raise ValueError(message)
            _append_config_issue(
                config_issues,
                issue_keys,
                source_id=source_id,
                variable_tag=tag,
                message=message,
            )

        resolved_sheet = sheet
        available_columns: list[str] | None = None
        sheet_details = (
            _load_sheet_columns(
                source=source,
                sheet_name=sheet,
                metadata_cache=metadata_cache,
                variable_tag=tag,
                config_issues=config_issues,
                issue_keys=issue_keys,
            )
            if source_supports_variables
            else None
        )
        if sheet_details is not None:
            resolved_sheet, available_columns = sheet_details

        if variable_kind == "composite":
            columns = _normalize_columns(variable.columns or [])
            key_column = variable.key_column or ""

            if len(columns) < 2:
                raise ValueError(f"???? '{tag}' ?????? 2 ??")
            if not key_column.strip():
                raise ValueError(f"???? '{tag}' ?? key_column?")
            resolved_columns = columns
            resolved_key_column = key_column

            if available_columns is not None:
                try:
                    resolved_columns = _resolve_identifiers_against_available(
                        columns,
                        available_columns,
                        identifier_label="列名",
                        context=f"变量“{tag}”",
                    )
                    resolved_key_column = _resolve_identifier_against_available(
                        key_column,
                        available_columns,
                        identifier_label="key 列",
                        context=f"变量“{tag}”",
                    )
                except ValueError as exc:
                    if config_issues is None:
                        raise
                    _append_config_issue(
                        config_issues,
                        issue_keys,
                        source_id=source_id,
                        variable_tag=tag,
                        message=f"{exc}???????????????????????",
                    )
                if resolved_key_column not in resolved_columns:
                    if config_issues is None:
                        raise ValueError(f"???? '{tag}' ? key_column ??????????")
                    _append_config_issue(
                        config_issues,
                        issue_keys,
                        source_id=source_id,
                        variable_tag=tag,
                        message=(
                            f"变量“{tag}”的 key 列“{resolved_key_column}”未包含在关联列中。"
                            "请到变量配置中修复后再保存或执行。"
                        ),
                    )

            normalized_variables.append(
                VariableTag(
                    tag=tag,
                    source_id=source_id,
                    sheet=resolved_sheet,
                    variable_kind="composite",
                    columns=resolved_columns,
                    key_column=resolved_key_column,
                    append_index_to_key=variable.append_index_to_key,
                    expected_type="json",
                )
            )
        elif variable_kind == "single":
            column = variable.column or ""
            if not column.strip():
                raise ValueError(f"??? '{tag}' ?? column?")
            resolved_column = column
            if available_columns is not None:
                try:
                    resolved_column = _resolve_identifier_against_available(
                        column,
                        available_columns,
                        identifier_label="列名",
                        context=f"变量“{tag}”",
                    )
                except ValueError as exc:
                    if config_issues is None:
                        raise
                    _append_config_issue(
                        config_issues,
                        issue_keys,
                        source_id=source_id,
                        variable_tag=tag,
                        message=f"{exc}???????????????????????",
                    )

            normalized_variables.append(
                VariableTag(
                    tag=tag,
                    source_id=source_id,
                    sheet=resolved_sheet,
                    variable_kind="single",
                    column=resolved_column,
                    expected_type=variable.expected_type or "str",
                )
            )
        else:
            raise ValueError(
                f"?????? '{tag}' ??????? variable_kind '{variable_kind}'?"
            )

        seen_tags.add(tag)

    return normalized_variables

"""Shared compiler helper functions independent from agent service orchestration."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.app.ai import field_resolver
from backend.app.ai.workflow_hints import AiRuleFilterHint, AiRuleWorkflowHints, coerce_filter_hint
from backend.app.api.schemas import VariableTag


def build_hint_composite_config(
    *,
    target_field: str,
    regex_pattern: str | None,
    filter_field: str | None,
    filter_operator: str | None,
    filter_value: str | None,
    filters: list[AiRuleFilterHint] | None = None,
    assertion_field: str | None,
    assertion_operator: str | None,
    assertion_value: str | None,
    assertion_value_source: str | None = None,
    assertion_expected_field: str | None = None,
) -> Any | None:
    """Build a composite condition config from normalized workflow hints."""
    final_assertion_field = (
        assertion_field if isinstance(assertion_field, str) and assertion_field.strip() else target_field
    )
    final_assertion_operator = assertion_operator or ("regex" if regex_pattern else None)
    final_assertion_value = _first_text(assertion_value, regex_pattern)
    final_value_source = "field" if assertion_value_source == "field" and assertion_expected_field else "literal"
    if not final_assertion_field or not final_assertion_operator:
        return None
    no_value_assertion_operators = {"not_null", "unique", "duplicate_required"}
    if (
        final_value_source == "literal"
        and final_assertion_operator not in no_value_assertion_operators
        and not final_assertion_value
    ):
        return None
    config = {
        "global_filters": [],
        "branches": [
            {
                "branch_id": f"ai-branch-{uuid4().hex[:8]}",
                "filters": [],
                "assertions": [
                    condition(
                        field=final_assertion_field,
                        operator=final_assertion_operator,
                        expected_value=final_assertion_value,
                        value_source=final_value_source,
                        expected_field=assertion_expected_field,
                    )
                ],
            }
        ],
    }
    for raw_item in filters or []:
        item = coerce_filter_hint(raw_item)
        if item is None:
            continue
        config["global_filters"].append(
            condition(
                field=item.field,
                operator=item.operator or "eq",
                expected_value=item.value,
            )
        )
    if filter_field and (filter_value or filter_operator == "not_null") and not any(
        item.get("field") == filter_field and item.get("expected_value") == filter_value
        for item in config["global_filters"]
    ):
        config["global_filters"].append(
            condition(
                field=filter_field,
                operator=filter_operator or "not_contains",
                expected_value=filter_value or "",
            )
        )
    return config


def condition(
    *,
    field: str,
    operator: str,
    expected_value: str | None = None,
    value_source: str = "literal",
    expected_field: str | None = None,
) -> dict[str, Any]:
    """Build one composite condition/assertion payload."""
    normalized_expected_value = (expected_value or "").strip()
    normalized_value_source = "field" if value_source == "field" and expected_field else "literal"
    item: dict[str, Any] = {
        "condition_id": f"ai-condition-{uuid4().hex[:8]}",
        "field": field,
        "operator": operator,
    }
    if operator in {"not_null", "unique", "duplicate_required"}:
        return item
    if operator == "regex":
        item["expected_value"] = normalized_expected_value
        return item
    item["value_source"] = normalized_value_source
    if normalized_value_source == "field":
        item["expected_field"] = str(expected_field).strip()
    else:
        item["expected_value"] = normalized_expected_value
    if (
        normalized_value_source == "literal"
        and operator in {"eq", "ne"}
        and _looks_like_expected_value_set(normalized_expected_value)
    ):
        item["expected_value_mode"] = "set"
    return item


def infer_metadata_key_column(
    context: dict[str, Any] | None,
    *,
    source_id: str | None,
    sheet: str | None,
) -> str | None:
    """Infer the common key column from source metadata."""
    if not context or not source_id or not sheet:
        return None
    metadata_by_source = context.get("source_metadata", {})
    source_metadata = metadata_by_source.get(source_id, {}) if isinstance(metadata_by_source, dict) else {}
    raw_sheets = source_metadata.get("sheets") if isinstance(source_metadata, dict) else None
    if not isinstance(raw_sheets, list):
        return None
    sheet_candidates = [
        str(raw_sheet.get("name", ""))
        for raw_sheet in raw_sheets
        if isinstance(raw_sheet, dict)
    ]
    resolved_sheet, _issue = field_resolver.resolve_identifier_exact_or_trim(sheet, sheet_candidates)
    if resolved_sheet is None:
        return None
    matched_sheet = next(
        (
            raw_sheet
            for raw_sheet in raw_sheets
            if isinstance(raw_sheet, dict) and str(raw_sheet.get("name", "")) == resolved_sheet
        ),
        None,
    )
    raw_columns = matched_sheet.get("columns") if isinstance(matched_sheet, dict) else None
    if not isinstance(raw_columns, list):
        return None
    columns = [str(column) for column in raw_columns]
    for key_candidate in ("INT_ID", "INT_Id", "ID"):
        resolved_key, _issue = field_resolver.resolve_identifier_exact_or_trim(key_candidate, columns)
        if resolved_key:
            return resolved_key
    return None


def resolve_hint_composite_columns(
    workflow_hints: AiRuleWorkflowHints,
    *,
    variable: VariableTag | None = None,
    target_field: str,
    display_field: str | None,
    filter_field: str | None,
) -> tuple[str | None, list[str]]:
    """Resolve key and columns for a hinted composite variable."""
    columns = _unique_texts(
        [
            *(variable.columns if variable is not None else []),
            *(column for column in workflow_hints.composite_columns if not field_resolver.is_placeholder_key_column(column)),
            _clean_key_column(workflow_hints.key_column),
            variable.key_column if variable is not None else None,
            display_field,
            target_field,
            filter_field,
            *(
                item.field
                for item in (coerce_filter_hint(raw_item) for raw_item in workflow_hints.filters)
                if item is not None
            ),
        ]
    )
    key_column = _first_text(
        _clean_key_column(workflow_hints.key_column),
        variable.key_column if variable is not None else None,
    )
    if not key_column and columns:
        key_column = next(
            (
                column
                for column in columns
                if column.strip().lower() in {"int_id", "id"}
            ),
            None,
        )
    return key_column, columns


def _clean_key_column(value: Any) -> str | None:
    if field_resolver.is_placeholder_key_column(value):
        return None
    if isinstance(value, str):
        return value.strip() or None
    return None


def _first_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _unique_texts(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        if isinstance(value, str) and value.strip() and value.strip() not in result:
            result.append(value.strip())
    return result


def _looks_like_expected_value_set(value: str) -> bool:
    return "," in value

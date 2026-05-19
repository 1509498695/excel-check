"""Field name resolution and workflow hint canonicalization."""

from __future__ import annotations

from collections.abc import Callable
from difflib import SequenceMatcher
from typing import Any
import re

from backend.app.ai.workflow_hints import AiRuleFilterHint, AiRuleWorkflowHints
from backend.app.api.schemas import VariableTag


FieldResolver = Callable[[str | None], tuple[str | None, str | None, str | None]]

SCALAR_HINT_FIELDS = (
    "target_field",
    "display_field",
    "filter_field",
    "assertion_field",
    "assertion_expected_field",
    "key_column",
    "left_filter_field",
    "right_filter_field",
    "left_key_field",
    "right_key_field",
)
LIST_HINT_FIELDS = ("compare_fields", "composite_columns")


def resolve_identifier_exact_or_trim(
    requested: str | None,
    candidates: list[str],
) -> tuple[str | None, str | None]:
    """Resolve an identifier by exact match, then unique trimmed match."""
    if not isinstance(requested, str) or not requested.strip():
        return None, "missing"
    normalized = requested.strip()
    exact_matches = [candidate for candidate in candidates if candidate == requested]
    if len(exact_matches) == 1:
        return exact_matches[0], None
    trim_matches = [candidate for candidate in candidates if candidate.strip() == normalized]
    if len(trim_matches) == 1:
        return trim_matches[0], None
    if len(trim_matches) > 1:
        return None, "ambiguous"
    return None, "missing"


def unique_fuzzy_field_match(field: str, candidates: list[str]) -> str | None:
    """Return a conservative unique fuzzy field match."""
    if not candidates:
        return None
    normalized = field.lower()
    trailing_number = re.search(r"(\d+)$", field)
    candidate_pool = candidates
    if trailing_number:
        suffix = trailing_number.group(1)
        candidate_pool = [candidate for candidate in candidates if candidate.strip().endswith(suffix)]
        if not candidate_pool:
            return None

    scored = sorted(
        (
            (SequenceMatcher(None, normalized, candidate.strip().lower()).ratio(), candidate)
            for candidate in candidate_pool
        ),
        reverse=True,
    )
    if not scored:
        return None
    best_score, best_candidate = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0.0
    threshold = 0.80 if trailing_number else 0.92
    if best_score >= threshold and best_score - second_score >= 0.03:
        return best_candidate
    return None


def canonical_variable_field(variable: VariableTag | None, field: str | None) -> str | None:
    """Resolve a field against a variable while preserving the real stored spelling."""
    if not field:
        return field
    normalized = field.strip()
    if variable is None:
        return normalized
    for candidate in [variable.column, variable.key_column, *(variable.columns or [])]:
        if isinstance(candidate, str) and candidate.strip() == normalized:
            return candidate
    return normalized


def variable_field_candidates(variable: VariableTag) -> list[str]:
    """Return all field names that can belong to a variable."""
    result: list[str] = []
    for candidate in [variable.column, variable.key_column, *(variable.columns or [])]:
        if isinstance(candidate, str) and candidate.strip() and candidate not in result:
            result.append(candidate)
    return result


def metadata_sheet_columns(
    context: dict[str, Any] | None,
    *,
    source_id: str | None,
    sheet: str | None,
) -> list[str]:
    """Return columns for one source/sheet from AI-safe metadata context."""
    if not context or not source_id or not sheet:
        return []
    metadata_by_source = context.get("source_metadata", {})
    source_metadata = metadata_by_source.get(source_id, {}) if isinstance(metadata_by_source, dict) else {}
    raw_sheets = source_metadata.get("sheets") if isinstance(source_metadata, dict) else None
    if not isinstance(raw_sheets, list):
        return []

    sheet_candidates = [
        str(raw_sheet.get("name", ""))
        for raw_sheet in raw_sheets
        if isinstance(raw_sheet, dict)
    ]
    resolved_sheet, _issue = resolve_identifier_exact_or_trim(sheet, sheet_candidates)
    if resolved_sheet is None:
        return []
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
        return []
    return [str(column) for column in raw_columns]


def resolve_metadata_field_for_hint(
    field: str | None,
    columns: list[str],
) -> tuple[str | None, str | None, str | None]:
    """Resolve one hint field against sheet metadata columns."""
    if not field:
        return field, None, None
    normalized = field.strip()
    if not normalized or normalized == "__key__":
        return normalized, None, None
    if is_placeholder_key_column(normalized):
        return None, None, None

    exact_or_trim, issue = resolve_identifier_exact_or_trim(normalized, columns)
    if exact_or_trim:
        return exact_or_trim, None, None
    if issue == "ambiguous":
        return normalized, None, f"{normalized}(不唯一)"

    fuzzy_match = unique_fuzzy_field_match(normalized, columns)
    if fuzzy_match:
        return (
            fuzzy_match,
            f"已根据目标 Sheet 表头将 {normalized} 修正为 {fuzzy_match}，请确认。",
            None,
        )
    return normalized, None, normalized


def resolve_variable_field_for_hint(
    variable: VariableTag,
    field: str | None,
) -> tuple[str | None, str | None, str | None]:
    """Resolve one hint field against an existing variable."""
    if not field:
        return field, None, None
    normalized = field.strip()
    if not normalized or normalized == "__key__":
        return normalized, None, None
    if is_placeholder_key_column(normalized):
        return None, None, None

    candidates = variable_field_candidates(variable)
    for candidate in candidates:
        if candidate.strip() == normalized:
            return candidate, None, None

    fuzzy_match = unique_fuzzy_field_match(normalized, candidates)
    if fuzzy_match:
        return (
            fuzzy_match,
            f"已根据变量池字段将 {normalized} 修正为 {fuzzy_match}，请确认。",
            None,
        )
    return normalized, None, normalized


def canonicalize_workflow_hints_fields(
    workflow_hints: AiRuleWorkflowHints,
    *,
    resolve: FieldResolver,
) -> tuple[AiRuleWorkflowHints, list[str], list[str]]:
    """Canonicalize every field-carrying hint with a supplied resolver."""
    updates: dict[str, Any] = {}
    warnings: list[str] = []
    unresolved: list[str] = []

    def take(value: str | None) -> str | None:
        resolved, warning, missing = resolve(value)
        if warning and warning not in warnings:
            warnings.append(warning)
        if missing and missing not in unresolved:
            unresolved.append(missing)
        return resolved

    for attr in SCALAR_HINT_FIELDS:
        value = getattr(workflow_hints, attr)
        resolved = take(value)
        if resolved != value:
            updates[attr] = resolved

    for attr in LIST_HINT_FIELDS:
        resolved_list: list[str] = []
        for field in getattr(workflow_hints, attr):
            resolved = take(field)
            if resolved and resolved not in resolved_list:
                resolved_list.append(resolved)
        if resolved_list != getattr(workflow_hints, attr):
            updates[attr] = resolved_list

    filters: list[AiRuleFilterHint] = []
    for item in workflow_hints.filters:
        resolved = take(item.field)
        if resolved:
            filters.append(item.model_copy(update={"field": resolved}))
    if filters != workflow_hints.filters:
        updates["filters"] = filters

    if not updates:
        return workflow_hints, warnings, unresolved
    return workflow_hints.model_copy(update=updates), warnings, unresolved


def canonicalize_with_variable(
    workflow_hints: AiRuleWorkflowHints,
    variable: VariableTag | None,
) -> tuple[AiRuleWorkflowHints, list[str], list[str]]:
    """Canonicalize workflow hints against an existing variable."""
    if variable is None:
        return workflow_hints, [], []
    return canonicalize_workflow_hints_fields(
        workflow_hints,
        resolve=lambda value: resolve_variable_field_for_hint(variable, value),
    )


def canonicalize_with_metadata(
    workflow_hints: AiRuleWorkflowHints,
    context: dict[str, Any] | None,
    *,
    source_id: str | None,
    sheet: str | None,
) -> tuple[AiRuleWorkflowHints, list[str], list[str]]:
    """Canonicalize workflow hints against source metadata."""
    columns = metadata_sheet_columns(context, source_id=source_id, sheet=sheet)
    if not columns:
        return workflow_hints, [], []
    return canonicalize_workflow_hints_fields(
        workflow_hints,
        resolve=lambda value: resolve_metadata_field_for_hint(value, columns),
    )


def canonicalize_filter_hints(
    variable: VariableTag | None,
    filters: list[AiRuleFilterHint],
) -> list[AiRuleFilterHint]:
    """Canonicalize filter hint fields against one variable."""
    result: list[AiRuleFilterHint] = []
    for item in filters:
        resolved_field = canonical_variable_field(variable, item.field)
        if not resolved_field:
            continue
        next_item = item.model_copy(update={"field": resolved_field})
        if next_item not in result:
            result.append(next_item)
    return result


def canonicalize_composite_config_fields(
    config: Any | None,
    variable: VariableTag | None,
) -> Any | None:
    """Canonicalize every field reference inside a composite config."""
    if config is None or variable is None:
        return config
    payload = config.model_dump() if hasattr(config, "model_dump") else dict(config)

    def map_condition(condition: dict[str, Any]) -> None:
        condition["field"] = canonical_variable_field(variable, condition.get("field")) or ""
        if condition.get("expected_field"):
            condition["expected_field"] = canonical_variable_field(
                variable,
                condition.get("expected_field"),
            )

    for condition in payload.get("global_filters", []):
        if isinstance(condition, dict):
            map_condition(condition)
    for branch in payload.get("branches", []):
        if not isinstance(branch, dict):
            continue
        for condition in branch.get("filters", []):
            if isinstance(condition, dict):
                map_condition(condition)
        for condition in branch.get("assertions", []):
            if isinstance(condition, dict):
                map_condition(condition)
    return config.__class__.model_validate(payload) if hasattr(config.__class__, "model_validate") else payload


def append_field_correction_summary(summary: str, warnings: list[str]) -> str:
    """Append field correction warnings to a reasoning summary."""
    if not warnings:
        return summary
    correction_text = "；".join(warnings)
    if correction_text in summary:
        return summary
    return f"{summary}；{correction_text}"


def is_placeholder_key_column(value: object | None) -> bool:
    """Return whether a key field is merely a prompt placeholder."""
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text:
        return False
    if "未识别" in text or "需要用户确认" in text:
        return True
    compact = re.sub(r"[\s:：=为是列字段、，。；;]+", "", text).lower()
    return compact in {
        "key",
        "关联key",
        "业务key",
        "比对key",
        "对齐key",
        "主键",
        "唯一键",
        "索引",
    }


def clean_key_column(value: str | None) -> str | None:
    """Drop placeholder key names and normalize real key text."""
    return None if is_placeholder_key_column(value) else _first_text(value)


def _first_text(*values: str | None) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None

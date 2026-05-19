"""Workflow hint models and normalization helpers."""

from __future__ import annotations

import re
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.api.fixed_rules_schemas import (
    ExpectedValueMode,
    FixedRuleOperator,
    FixedRuleType,
    SequenceDirection,
    SequenceStartMode,
)


MissingKind = Literal["source", "variable", "rule", "parameter", "ability"]
MissingAction = Literal[
    "open_source_dialog",
    "open_single_variable_dialog",
    "open_composite_variable_dialog",
    "edit_description",
    "none",
]
AiFilterOperator = Literal["eq", "ne", "gt", "lt", "not_null", "contains", "not_contains"]
AiDualCompareOperator = Literal["eq", "ne", "gt", "lt", "not_null"]


class AiRuleFilterHint(BaseModel):
    """AI 工作流中一条可编译的筛选线索。"""

    model_config = ConfigDict(extra="forbid")

    field: str
    operator: AiFilterOperator = "eq"
    value: str = ""

    @field_validator("field", "operator", "value", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class AiRuleWorkflowHints(BaseModel):
    """前端工作流提供的结构化线索，用于后端确定性补齐草稿。"""

    model_config = ConfigDict(extra="forbid")

    rule_type_hint: FixedRuleType | None = None
    target_variable_tag: str | None = None
    reference_variable_tag: str | None = None
    left_variable_tag: str | None = None
    right_variable_tag: str | None = None
    source_id: str | None = None
    source_type: Literal["local_excel", "svn"] | None = None
    source_url: str | None = None
    sheet: str | None = None
    target_field: str | None = None
    display_field: str | None = None
    filter_field: str | None = None
    filter_operator: AiFilterOperator | None = None
    filter_value: str | None = None
    filters: list[AiRuleFilterHint] = Field(default_factory=list)
    assertion_field: str | None = None
    assertion_operator: Literal["eq", "ne", "gt", "lt", "not_null", "regex", "unique", "duplicate_required"] | None = None
    assertion_value_source: Literal["literal", "field"] | None = None
    assertion_expected_field: str | None = None
    assertion_value: str | None = None
    operator: FixedRuleOperator | None = None
    expected_value: str | None = None
    expected_value_mode: ExpectedValueMode | None = None
    regex_pattern: str | None = None
    sequence_direction: SequenceDirection | None = None
    sequence_step: str | None = None
    sequence_start_mode: SequenceStartMode | None = None
    sequence_start_value: str | None = None
    key_column: str | None = None
    composite_columns: list[str] = Field(default_factory=list)
    reference_source_id: str | None = None
    reference_source_type: Literal["local_excel", "svn"] | None = None
    reference_source_url: str | None = None
    reference_sheet: str | None = None
    reference_field: str | None = None
    reference_key_column: str | None = None
    reference_composite_columns: list[str] = Field(default_factory=list)
    left_filter_field: str | None = None
    left_filter_operator: AiFilterOperator | None = None
    left_filter_value: str | None = None
    right_filter_field: str | None = None
    right_filter_operator: AiFilterOperator | None = None
    right_filter_value: str | None = None
    left_key_field: str | None = None
    right_key_field: str | None = None
    compare_operator: AiDualCompareOperator | None = None
    key_check_mode: Literal["baseline_only", "bidirectional"] | None = None
    compare_fields: list[str] = Field(default_factory=list)
    pipeline_nodes: list[dict[str, Any]] = Field(default_factory=list)
    mapping_nodes: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator(
        "rule_type_hint",
        "target_variable_tag",
        "reference_variable_tag",
        "left_variable_tag",
        "right_variable_tag",
        "source_id",
        "source_type",
        "source_url",
        "sheet",
        "target_field",
        "display_field",
        "filter_field",
        "filter_operator",
        "filter_value",
        "assertion_field",
        "assertion_operator",
        "assertion_value_source",
        "assertion_expected_field",
        "assertion_value",
        "operator",
        "expected_value",
        "expected_value_mode",
        "regex_pattern",
        "sequence_direction",
        "sequence_step",
        "sequence_start_mode",
        "sequence_start_value",
        "key_column",
        "reference_source_id",
        "reference_source_type",
        "reference_source_url",
        "reference_sheet",
        "reference_field",
        "reference_key_column",
        "left_filter_field",
        "left_filter_operator",
        "left_filter_value",
        "right_filter_field",
        "right_filter_operator",
        "right_filter_value",
        "left_key_field",
        "right_key_field",
        "compare_operator",
        "key_check_mode",
        mode="before",
    )
    @classmethod
    def _strip_optional_string(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator(
        "composite_columns",
        "reference_composite_columns",
        "compare_fields",
        mode="before",
    )
    @classmethod
    def _normalize_text_list(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]
        return value

    @field_validator("composite_columns", "reference_composite_columns", "compare_fields")
    @classmethod
    def _strip_text_list(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


class MissingItem(BaseModel):
    """展示给用户的缺口说明。"""

    model_config = ConfigDict(extra="forbid")

    kind: MissingKind
    message: str
    suggested_action: MissingAction = "none"
    prefill: dict[str, Any] = Field(default_factory=dict)


def coerce_filter_hint(value: Any) -> AiRuleFilterHint | None:
    """Best-effort conversion for one filter hint."""
    if isinstance(value, AiRuleFilterHint):
        return value
    if isinstance(value, dict):
        try:
            return AiRuleFilterHint.model_validate(value)
        except Exception:  # noqa: BLE001 - invalid model output is ignored.
            return None
    return None


def drop_placeholder_keys(workflow_hints: AiRuleWorkflowHints) -> AiRuleWorkflowHints:
    """Drop prompt placeholder key fields from workflow hints."""
    updates: dict[str, Any] = {}
    for attr in ("key_column", "left_key_field", "right_key_field", "reference_key_column"):
        if _is_placeholder_key_column(getattr(workflow_hints, attr)):
            updates[attr] = None
    if not updates:
        return workflow_hints
    return workflow_hints.model_copy(update=updates)


def dedupe_list_fields(workflow_hints: AiRuleWorkflowHints) -> AiRuleWorkflowHints:
    """Dedupe list-like workflow hint fields."""
    updates: dict[str, Any] = {}
    for attr in ("composite_columns", "reference_composite_columns", "compare_fields"):
        current = getattr(workflow_hints, attr)
        deduped = _dedupe_text_list(current)
        if deduped != current:
            updates[attr] = deduped

    cleaned_filters: list[AiRuleFilterHint] = []
    for raw_item in workflow_hints.filters:
        item = coerce_filter_hint(raw_item)
        if item is not None and item not in cleaned_filters:
            cleaned_filters.append(item)
    if cleaned_filters != workflow_hints.filters:
        updates["filters"] = cleaned_filters

    if not updates:
        return workflow_hints
    return workflow_hints.model_copy(update=updates)


def sanitize_workflow_hints(workflow_hints: AiRuleWorkflowHints) -> AiRuleWorkflowHints:
    """Normalize workflow hints after extraction or merge."""
    return dedupe_list_fields(drop_placeholder_keys(workflow_hints))


def has_workflow_hints(workflow_hints: AiRuleWorkflowHints) -> bool:
    """Return whether any user-meaningful hint is present."""
    payload = workflow_hints.model_dump(exclude_none=True)
    return any(value not in ("", [], {}, None) for value in payload.values())


def workflow_hints_have_minimum_auto_complete_template(
    workflow_hints: AiRuleWorkflowHints,
    *,
    description: str,
    infer_rule_type: Callable[[AiRuleWorkflowHints, str], str | None] | None = None,
) -> bool:
    """Check whether hints are complete enough to try deterministic auto-complete."""
    has_source = bool(workflow_hints.source_id or workflow_hints.source_url)
    has_sheet = bool(workflow_hints.sheet)
    has_fields = bool(
        workflow_hints.target_field
        or workflow_hints.assertion_field
        or workflow_hints.filters
        or workflow_hints.composite_columns
        or workflow_hints.compare_fields
    )
    has_rule = bool(
        infer_rule_type(workflow_hints, description)
        if infer_rule_type is not None
        else (
            workflow_hints.rule_type_hint
            or workflow_hints.target_field
            or workflow_hints.assertion_field
            or workflow_hints.regex_pattern
            or description.strip()
        )
    )
    return has_source and has_sheet and has_fields and has_rule


def has_complete_dual_hints(hints: AiRuleWorkflowHints) -> bool:
    """Return whether hints fully describe a dual-composite compare shape."""
    return bool(
        (hints.left_filter_field or hints.filter_field)
        and (hints.left_filter_value or hints.filter_value)
        and (hints.right_filter_field or hints.filter_field)
        and hints.right_filter_value
        and (hints.key_column or hints.left_key_field or hints.right_key_field)
        and hints.compare_fields
    )


def _dedupe_text_list(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = value.strip() if isinstance(value, str) else ""
        if normalized and normalized not in result and not _is_placeholder_key_column(normalized):
            result.append(normalized)
    return result


def _is_placeholder_key_column(value: object | None) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text:
        return False
    if "未识别" in text or "需要用户确认" in text:
        return True
    compact = re.sub(r"[\s:：=为是列字段、，。；;]+", "", text).lower()
    return compact in {"key", "关联key", "业务key", "比对key", "对齐key", "主键", "唯一键", "索引"}

"""顺序校验 handler。"""

from __future__ import annotations

from typing import Any

from backend.app.api.schemas import ValidationRule
from backend.app.rules.domain.result import build_fixed_result
from backend.app.rules.domain.value import is_empty_value, to_number
from backend.app.rules.engine_core import RuleExecutionContext, register_rule
from backend.app.rules.handlers.fixed.common import (
    _get_display_field_param,
    _get_fixed_rule_param,
    _get_row_display_value,
    _get_single_variable_frame,
)
from backend.app.rules.infrastructure.tag_extractor import by_target_tag


def _parse_sequence_number(
    value: Any,
    *,
    field_name: str,
    rule_type: str,
    positive_only: bool = False,
) -> float:
    """解析顺序校验的数值参数。"""
    if isinstance(value, str):
        normalized = value.strip()
    else:
        normalized = str(value).strip() if value is not None else ""
    if not normalized:
        raise ValueError(f"Rule '{rule_type}' requires params.{field_name}.")

    number = to_number(normalized)
    if number is None:
        raise ValueError(f"Rule '{rule_type}' requires numeric params.{field_name}.")
    if positive_only and number <= 0:
        raise ValueError(f"Rule '{rule_type}' requires positive params.{field_name}.")
    return float(number)


def _format_sequence_display(value: float) -> str:
    """把顺序校验中的数值渲染成更适合提示语的文本。"""
    if float(value).is_integer():
        return str(int(value))
    return format(value, "g")


@register_rule("sequence_order_check", dependent_tags=by_target_tag)
def check_sequence_order(
    rule: ValidationRule,
    context: RuleExecutionContext,
) -> list[dict[str, Any]]:
    """按原始行序检查单列数值是否连续递增或递减。"""
    target_tag = _get_fixed_rule_param(rule, "target_tag")
    direction = _get_fixed_rule_param(rule, "direction")
    start_mode = _get_fixed_rule_param(rule, "start_mode")
    rule_name = _get_fixed_rule_param(rule, "rule_name")
    step = _parse_sequence_number(
        rule.params.get("step"),
        field_name="step",
        rule_type=rule.rule_type,
        positive_only=True,
    )

    if direction not in {"asc", "desc"}:
        raise ValueError(f"Rule '{rule.rule_type}' requires params.direction to be 'asc' or 'desc'.")
    if start_mode not in {"auto", "manual"}:
        raise ValueError(f"Rule '{rule.rule_type}' requires params.start_mode to be 'auto' or 'manual'.")

    variable, frame, column_name = _get_single_variable_frame(context, target_tag, rule.rule_type)
    ordered_frame = frame.sort_values("_row_index", kind="stable")
    location = f"{variable.sheet} -> {column_name}"
    abnormal_results: list[dict[str, Any]] = []
    delta = step if direction == "asc" else -step
    direction_label = "升序" if direction == "asc" else "降序"
    display_field = _get_display_field_param(rule)

    expected_value: float | None = None
    if start_mode == "manual":
        expected_value = _parse_sequence_number(
            rule.params.get("start_value"),
            field_name="start_value",
            rule_type=rule.rule_type,
        )

    for _, row in ordered_frame[[column_name, "_row_index"]].iterrows():
        raw_value = row[column_name]
        row_index = int(row["_row_index"])

        if is_empty_value(raw_value):
            expected_display = (
                _format_sequence_display(expected_value) if expected_value is not None else "首行实际值"
            )
            abnormal_results.append(
                build_fixed_result(
                    row_index=row_index,
                    raw_value=raw_value,
                    display_value=_get_row_display_value(row, display_field),
                    rule_name=rule_name,
                    location=location,
                    message=(
                        f"顺序校验失败：当前值为空，期望值 {expected_display}"
                        f"（{direction_label}，步长 {_format_sequence_display(step)}）。"
                    ),
                )
            )
            if expected_value is not None:
                expected_value += delta
            continue

        numeric_value = to_number(raw_value)
        if numeric_value is None:
            expected_display = (
                _format_sequence_display(expected_value) if expected_value is not None else "首行实际值"
            )
            abnormal_results.append(
                build_fixed_result(
                    row_index=row_index,
                    raw_value=raw_value,
                    display_value=_get_row_display_value(row, display_field),
                    rule_name=rule_name,
                    location=location,
                    message=(
                        f"顺序校验失败：当前值 {raw_value} 不是合法数字，期望值 {expected_display}"
                        f"（{direction_label}，步长 {_format_sequence_display(step)}）。"
                    ),
                )
            )
            if expected_value is not None:
                expected_value += delta
            continue

        if expected_value is None:
            expected_value = numeric_value
        elif numeric_value != expected_value:
            abnormal_results.append(
                build_fixed_result(
                    row_index=row_index,
                    raw_value=raw_value,
                    display_value=_get_row_display_value(row, display_field),
                    rule_name=rule_name,
                    location=location,
                    message=(
                        f"顺序校验失败：当前值 {_format_sequence_display(numeric_value)}，"
                        f"期望值 {_format_sequence_display(expected_value)}"
                        f"（{direction_label}，步长 {_format_sequence_display(step)}）。"
                    ),
                )
            )

        expected_value += delta

    return abnormal_results

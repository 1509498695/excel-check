"""固定规则模块的单列常量比较规则。"""

from __future__ import annotations

from typing import Any

import pandas as pd

from backend.app.api.schemas import ValidationRule
from backend.app.rules.engine_core import RuleExecutionContext, register_rule
from backend.app.rules.rule_basics import (
    _get_business_column_name,
    _get_variable_frame,
)


def _get_fixed_rule_param(rule: ValidationRule, param_name: str) -> str:
    """读取固定规则所需的单值参数。"""
    value = rule.params.get(param_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Rule '{rule.rule_type}' requires params.{param_name}.")
    return value.strip()


def _normalize_fixed_text(value: Any) -> str | None:
    """把单元格内容标准化为可比较的文本。"""
    if pd.isna(value):
        return None
    if isinstance(value, str):
        return value.strip()
    return str(value)


def _to_number(value: Any) -> float | None:
    """尝试把单元格内容转成数值，空值返回 None。"""
    normalized = _normalize_fixed_text(value)
    if normalized in {None, ""}:
        return None
    try:
        return float(normalized)
    except ValueError:
        return None


def _build_fixed_rule_result(
    *,
    row_index: int,
    raw_value: Any,
    rule_name: str,
    sheet_name: str,
    column_name: str,
    message: str,
) -> dict[str, Any]:
    """构建固定规则模块的统一异常结构。"""
    if hasattr(raw_value, "item"):
        raw_value = raw_value.item()
    return {
        "level": "error",
        "rule_name": rule_name,
        "location": f"{sheet_name} -> {column_name}",
        "row_index": int(row_index),
        "raw_value": raw_value,
        "message": message,
    }


@register_rule("fixed_value_compare")
def check_fixed_value_compare(
    rule: ValidationRule,
    context: RuleExecutionContext,
) -> list[dict[str, Any]]:
    """执行固定规则模块的单列常量比较。"""
    target_tag = _get_fixed_rule_param(rule, "target_tag")
    operator = _get_fixed_rule_param(rule, "operator")
    expected_value = _get_fixed_rule_param(rule, "expected_value")
    rule_name = _get_fixed_rule_param(rule, "rule_name")

    variable = next(
        (item for item in context.task_tree.variables if item.tag == target_tag),
        None,
    )
    if variable is None or not variable.column:
        raise ValueError(f"Rule '{rule.rule_type}' references unknown tag '{target_tag}'.")

    frame = _get_variable_frame(context, target_tag, rule.rule_type)
    column_name = _get_business_column_name(frame, target_tag)
    abnormal_results: list[dict[str, Any]] = []

    if operator in {"eq", "ne"}:
        expected_text = expected_value.strip()
        for _, row in frame[[column_name, "_row_index"]].iterrows():
            current_text = _normalize_fixed_text(row[column_name])
            is_match = current_text == expected_text
            should_report = is_match if operator == "ne" else not is_match
            if not should_report:
                continue

            message = (
                f"该值不应等于 {expected_text}。"
                if operator == "ne"
                else f"该值应等于 {expected_text}。"
            )
            abnormal_results.append(
                _build_fixed_rule_result(
                    row_index=row["_row_index"],
                    raw_value=row[column_name],
                    rule_name=rule_name,
                    sheet_name=variable.sheet,
                    column_name=column_name,
                    message=message,
                )
            )
        return abnormal_results

    threshold = float(expected_value)
    for _, row in frame[[column_name, "_row_index"]].iterrows():
        raw_value = row[column_name]
        numeric_value = _to_number(raw_value)
        if numeric_value is None:
            if _normalize_fixed_text(raw_value) in {None, ""}:
                continue
            abnormal_results.append(
                _build_fixed_rule_result(
                    row_index=row["_row_index"],
                    raw_value=raw_value,
                    rule_name=rule_name,
                    sheet_name=variable.sheet,
                    column_name=column_name,
                    message="该值无法按数值参与比较。",
                )
            )
            continue

        failed = numeric_value <= threshold if operator == "gt" else numeric_value >= threshold
        if not failed:
            continue

        message = (
            f"该值应大于 {expected_value}。"
            if operator == "gt"
            else f"该值应小于 {expected_value}。"
        )
        abnormal_results.append(
            _build_fixed_rule_result(
                row_index=row["_row_index"],
                raw_value=raw_value,
                rule_name=rule_name,
                sheet_name=variable.sheet,
                column_name=column_name,
                message=message,
            )
        )

    return abnormal_results

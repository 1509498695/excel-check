"""基础规则实现。"""

from __future__ import annotations

from typing import Any

import pandas as pd

from backend.app.api.schemas import ValidationRule
from backend.app.rules.engine_core import (
    RuleExecutionContext,
    register_rule,
)


def _get_target_tags(rule: ValidationRule) -> list[str]:
    target_tags = rule.params.get("target_tags")
    if not isinstance(target_tags, list) or not target_tags:
        raise ValueError(
            f"Rule '{rule.rule_type}' requires non-empty params.target_tags."
        )
    if not all(isinstance(tag, str) and tag for tag in target_tags):
        raise ValueError(
            f"Rule '{rule.rule_type}' requires params.target_tags to be a string list."
        )
    return target_tags


def _get_variable_frame(
    context: RuleExecutionContext, tag: str, rule_type: str
) -> pd.DataFrame:
    frame = context.loaded_variables.get(tag)
    if frame is None:
        raise ValueError(f"Rule '{rule_type}' references unknown tag '{tag}'.")
    return frame


def _get_business_column_name(frame: pd.DataFrame, tag: str) -> str:
    business_columns = [column for column in frame.columns if column != "_row_index"]
    if len(business_columns) != 1:
        raise ValueError(
            f"Tag '{tag}' must map to exactly one business column, got {business_columns}."
        )
    return business_columns[0]


def _normalize_text(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


def _is_empty_value(value: Any) -> bool:
    normalized = _normalize_text(value)
    if pd.isna(normalized):
        return True
    return normalized == ""


def _build_abnormal_result(
    *,
    level: str,
    rule_name: str,
    tag: str,
    column_name: str,
    row_index: int,
    raw_value: Any,
    message: str,
) -> dict[str, Any]:
    if hasattr(raw_value, "item"):
        raw_value = raw_value.item()
    return {
        "level": level,
        "rule_name": rule_name,
        "location": f"{tag} -> {column_name}",
        "row_index": int(row_index),
        "raw_value": raw_value,
        "message": message,
    }


@register_rule("not_null")
def check_not_null(
    rule: ValidationRule, context: RuleExecutionContext
) -> list[dict[str, Any]]:
    """校验目标列中的空值。"""
    abnormal_results: list[dict[str, Any]] = []

    for tag in _get_target_tags(rule):
        frame = _get_variable_frame(context, tag, rule.rule_type)
        column_name = _get_business_column_name(frame, tag)
        series = frame[column_name]
        empty_mask = series.apply(_is_empty_value)

        for _, row in frame.loc[empty_mask, [column_name, "_row_index"]].iterrows():
            abnormal_results.append(
                _build_abnormal_result(
                    level="error",
                    rule_name=rule.rule_type,
                    tag=tag,
                    column_name=column_name,
                    row_index=row["_row_index"],
                    raw_value=row[column_name],
                    message="该字段不能为空。",
                )
            )

    return abnormal_results


@register_rule("unique")
def check_unique(
    rule: ValidationRule, context: RuleExecutionContext
) -> list[dict[str, Any]]:
    """校验目标列中的重复值。"""
    abnormal_results: list[dict[str, Any]] = []

    for tag in _get_target_tags(rule):
        frame = _get_variable_frame(context, tag, rule.rule_type)
        column_name = _get_business_column_name(frame, tag)
        series = frame[column_name]
        non_empty_mask = ~series.apply(_is_empty_value)
        duplicated_mask = series[non_empty_mask].duplicated(keep=False)
        invalid_rows = frame.loc[non_empty_mask].loc[duplicated_mask]

        for _, row in invalid_rows[[column_name, "_row_index"]].iterrows():
            abnormal_results.append(
                _build_abnormal_result(
                    level="warning",
                    rule_name=rule.rule_type,
                    tag=tag,
                    column_name=column_name,
                    row_index=row["_row_index"],
                    raw_value=row[column_name],
                    message="该值存在重复项。",
                )
            )

    return abnormal_results


@register_rule("regex")
def check_regex(
    rule: ValidationRule, context: RuleExecutionContext
) -> list[dict[str, Any]]:
    """预留正则校验处理器，后续接入真实规则计算。"""
    return []

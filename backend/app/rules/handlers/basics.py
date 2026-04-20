"""基础规则实现。"""

from __future__ import annotations

from typing import Any

from backend.app.api.schemas import ValidationRule
from backend.app.rules.domain.result import build_basic_result
from backend.app.rules.domain.value import (
    get_business_column_name,
    get_variable_frame,
    is_empty_value,
)
from backend.app.rules.engine_core import (
    RuleExecutionContext,
    register_rule,
)
from backend.app.rules.infrastructure.tag_extractor import by_target_tags, no_tags


def _get_rule_display_name(rule: ValidationRule) -> str:
    """优先使用规则自定义展示名，否则回退到 rule_type。"""
    display_name = rule.params.get("rule_name")
    if isinstance(display_name, str) and display_name.strip():
        return display_name.strip()
    return rule.rule_type


def _get_rule_location(rule: ValidationRule, *, tag: str, column_name: str) -> str:
    """优先使用规则传入的展示定位，避免固定规则页退化成 tag 定位。"""
    location = rule.params.get("location")
    if isinstance(location, str) and location.strip():
        return location.strip()
    return f"{tag} -> {column_name}"


@register_rule("not_null", dependent_tags=by_target_tags)
def check_not_null(
    rule: ValidationRule, context: RuleExecutionContext
) -> list[dict[str, Any]]:
    """校验目标列中的空值。"""
    abnormal_results: list[dict[str, Any]] = []

    for tag in by_target_tags(rule):
        frame = get_variable_frame(context, tag, rule.rule_type)
        column_name = get_business_column_name(frame, tag)
        series = frame[column_name]
        empty_mask = series.apply(is_empty_value)

        for _, row in frame.loc[empty_mask, [column_name, "_row_index"]].iterrows():
            abnormal_results.append(
                build_basic_result(
                    level="error",
                    rule_name=_get_rule_display_name(rule),
                    tag=tag,
                    column_name=column_name,
                    row_index=row["_row_index"],
                    raw_value=row[column_name],
                    message="该字段不能为空。",
                    location=_get_rule_location(rule, tag=tag, column_name=column_name),
                )
            )

    return abnormal_results


@register_rule("unique", dependent_tags=by_target_tags)
def check_unique(
    rule: ValidationRule, context: RuleExecutionContext
) -> list[dict[str, Any]]:
    """校验目标列中的重复值。"""
    abnormal_results: list[dict[str, Any]] = []

    for tag in by_target_tags(rule):
        frame = get_variable_frame(context, tag, rule.rule_type)
        column_name = get_business_column_name(frame, tag)
        series = frame[column_name]
        non_empty_mask = ~series.apply(is_empty_value)
        duplicated_mask = series[non_empty_mask].duplicated(keep=False)
        invalid_rows = frame.loc[non_empty_mask].loc[duplicated_mask]

        for _, row in invalid_rows[[column_name, "_row_index"]].iterrows():
            abnormal_results.append(
                build_basic_result(
                    level="warning",
                    rule_name=_get_rule_display_name(rule),
                    tag=tag,
                    column_name=column_name,
                    row_index=row["_row_index"],
                    raw_value=row[column_name],
                    message="该值存在重复项。",
                    location=_get_rule_location(rule, tag=tag, column_name=column_name),
                )
            )

    return abnormal_results


@register_rule("regex", dependent_tags=no_tags)
def check_regex(
    rule: ValidationRule, context: RuleExecutionContext
) -> list[dict[str, Any]]:
    """预留正则校验处理器，后续接入真实规则计算。"""
    return []

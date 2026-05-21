"""固定规则基础与单变量规则 handler。"""

from __future__ import annotations

import re
from typing import Any

from backend.app.api.schemas import ValidationRule
from backend.app.rules.domain.operators import matches_expected_text
from backend.app.rules.domain.result import build_basic_result, build_fixed_result
from backend.app.rules.domain.value import (
    get_business_column_name,
    get_variable_frame,
    is_empty_value,
    normalize_fixed_text,
    to_number,
)
from backend.app.rules.engine_core import RuleExecutionContext, register_rule
from backend.app.rules.handlers.fixed.common import (
    _get_display_field_param,
    _get_expected_value_set_display,
    _get_fixed_rule_expected_value_mode,
    _get_fixed_rule_param,
    _get_row_display_value,
    _get_single_variable_frame,
)
from backend.app.rules.infrastructure.tag_extractor import by_target_tag, by_target_tags, no_tags


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


def _get_display_value(rule: ValidationRule, row: Any, column_name: str) -> Any:
    """单变量规则只允许展示当前关联列。"""
    display_field = rule.params.get("display_field")
    if not isinstance(display_field, str) or display_field.strip() != column_name:
        return None
    return row[column_name]


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
                    display_value=_get_display_value(rule, row, column_name),
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
                    display_value=_get_display_value(rule, row, column_name),
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


@register_rule("regex_check", dependent_tags=by_target_tag)
def check_regex_check(
    rule: ValidationRule,
    context: RuleExecutionContext,
) -> list[dict[str, Any]]:
    """执行固定规则模块的单列正则校验。"""
    target_tag = _get_fixed_rule_param(rule, "target_tag")
    pattern = _get_fixed_rule_param(rule, "pattern")
    rule_name = _get_fixed_rule_param(rule, "rule_name")

    try:
        compiled_pattern = re.compile(pattern)
    except re.error as exc:  # pragma: no cover - 保存阶段已拦截
        raise ValueError(f"Rule '{rule.rule_type}' requires a valid params.pattern.") from exc

    variable, frame, column_name = _get_single_variable_frame(
        context,
        target_tag,
        rule.rule_type,
    )
    location = f"{variable.sheet} -> {column_name}"
    abnormal_results: list[dict[str, Any]] = []
    display_field = _get_display_field_param(rule)

    for _, row in frame[[column_name, "_row_index"]].iterrows():
        text = normalize_fixed_text(row[column_name])
        normalized_text = "" if text is None else text
        if compiled_pattern.fullmatch(normalized_text):
            continue
        abnormal_results.append(
            build_fixed_result(
                row_index=row["_row_index"],
                raw_value=row[column_name],
                display_value=_get_row_display_value(row, display_field),
                rule_name=rule_name,
                location=location,
                message=f"该值不符合正则格式 {pattern}。",
            )
        )

    return abnormal_results


@register_rule("fixed_value_compare", dependent_tags=by_target_tag)
def check_fixed_value_compare(
    rule: ValidationRule,
    context: RuleExecutionContext,
) -> list[dict[str, Any]]:
    """执行固定规则模块的单列常量比较。"""
    target_tag = _get_fixed_rule_param(rule, "target_tag")
    operator = _get_fixed_rule_param(rule, "operator")
    expected_value = _get_fixed_rule_param(rule, "expected_value")
    expected_value_mode = _get_fixed_rule_expected_value_mode(rule)
    rule_name = _get_fixed_rule_param(rule, "rule_name")

    variable, frame, column_name = _get_single_variable_frame(
        context,
        target_tag,
        rule.rule_type,
    )
    abnormal_results: list[dict[str, Any]] = []
    location = f"{variable.sheet} -> {column_name}"
    display_field = _get_display_field_param(rule)

    if operator in {"eq", "ne"}:
        expected_display = (
            _get_expected_value_set_display(expected_value)
            if expected_value_mode == "set"
            else expected_value.strip()
        )
        for _, row in frame[[column_name, "_row_index"]].iterrows():
            is_match = matches_expected_text(
                actual_value=row[column_name],
                expected_value=expected_value,
                expected_value_mode=expected_value_mode,
            )
            should_report = is_match if operator == "ne" else not is_match
            if not should_report:
                continue

            message = (
                (
                    f"该值不应等于规则集中的任一值：{expected_display}。"
                    if expected_value_mode == "set"
                    else f"该值不应等于 {expected_display}。"
                )
                if operator == "ne"
                else (
                    f"该值应等于规则集中的任一值：{expected_display}。"
                    if expected_value_mode == "set"
                    else f"该值应等于 {expected_display}。"
                )
            )
            abnormal_results.append(
                build_fixed_result(
                    row_index=row["_row_index"],
                    raw_value=row[column_name],
                    display_value=_get_row_display_value(row, display_field),
                    rule_name=rule_name,
                    location=location,
                    message=message,
                )
            )
        return abnormal_results

    threshold = float(expected_value)
    for _, row in frame[[column_name, "_row_index"]].iterrows():
        raw_value = row[column_name]
        numeric_value = to_number(raw_value)
        if numeric_value is None:
            if normalize_fixed_text(raw_value) in {None, ""}:
                continue
            abnormal_results.append(
                build_fixed_result(
                    row_index=row["_row_index"],
                    raw_value=raw_value,
                    display_value=_get_row_display_value(row, display_field),
                    rule_name=rule_name,
                    location=location,
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
            build_fixed_result(
                row_index=row["_row_index"],
                raw_value=raw_value,
                display_value=_get_row_display_value(row, display_field),
                rule_name=rule_name,
                location=location,
                message=message,
            )
        )

    return abnormal_results

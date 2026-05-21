"""双组合变量比对 handler。"""

from __future__ import annotations

from typing import Any

import pandas as pd

from backend.app.api.fixed_rules_schemas import DualCompositeComparison
from backend.app.api.schemas import ValidationRule, VariableTag
from backend.app.rules.domain.operators import evaluate_compare_assertion
from backend.app.rules.domain.result import build_fixed_result
from backend.app.rules.domain.value import is_empty_value
from backend.app.rules.engine_core import RuleExecutionContext, register_rule
from backend.app.rules.handlers.fixed.common import (
    _build_rule_location,
    _get_composite_variable_frame,
    _get_display_field_param,
    _get_dual_composite_comparisons,
    _get_dual_composite_filters,
    _get_dual_key_field,
    _get_field_display_name,
    _get_fixed_rule_param,
    _get_row_display_value,
)
from backend.app.rules.handlers.fixed.condition_eval import (
    _append_empty_dual_filter_warning,
    _apply_composite_filters,
    _build_dual_filter_context,
    _raise_duplicate_dual_keys,
)
from backend.app.rules.infrastructure.tag_extractor import by_reference_and_target_tag


@register_rule("dual_composite_compare", dependent_tags=by_reference_and_target_tag)
def check_dual_composite_compare(
    rule: ValidationRule,
    context: RuleExecutionContext,
) -> list[dict[str, Any]]:
    """按外层 Key 关联两个组合变量或同变量筛选子集，并逐项比较 Value 字段。"""
    target_tag = _get_fixed_rule_param(rule, "target_tag")
    reference_tag = _get_fixed_rule_param(rule, "reference_tag")
    key_check_mode = _get_fixed_rule_param(rule, "key_check_mode")
    rule_name = _get_fixed_rule_param(rule, "rule_name")
    display_field = _get_display_field_param(rule)
    comparisons = _get_dual_composite_comparisons(rule)
    left_filters = _get_dual_composite_filters(rule, "left_filters")
    right_filters = _get_dual_composite_filters(rule, "right_filters")
    left_key_field = _get_dual_key_field(rule, "left_key_field")
    right_key_field = _get_dual_key_field(rule, "right_key_field")

    if key_check_mode not in {"baseline_only", "bidirectional"}:
        raise ValueError(
            f"Rule '{rule.rule_type}' requires params.key_check_mode to be 'baseline_only' or 'bidirectional'."
        )

    target_variable, target_frame = _get_composite_variable_frame(context, target_tag, rule.rule_type)
    reference_variable, reference_frame = _get_composite_variable_frame(
        context,
        reference_tag,
        rule.rule_type,
    )
    if target_tag == reference_tag and (not left_filters or not right_filters):
        raise ValueError(
            "Rule 'dual_composite_compare' requires both left_filters and right_filters "
            "when target_tag equals reference_tag."
        )

    filtered_target_frame = _apply_composite_filters(
        target_frame.copy(),
        target_variable,
        left_filters,
    )
    filtered_reference_frame = _apply_composite_filters(
        reference_frame.copy(),
        reference_variable,
        right_filters,
    )
    abnormal_results: list[dict[str, Any]] = []
    target_key_location = _build_rule_location(target_variable, left_key_field)
    reference_key_location = _build_rule_location(reference_variable, right_key_field)
    filter_context = _build_dual_filter_context(
        target_variable=target_variable,
        reference_variable=reference_variable,
        left_filters=left_filters,
        right_filters=right_filters,
    )

    if filtered_target_frame.empty:
        _append_empty_dual_filter_warning(
            abnormal_results,
            rule_name=rule_name,
            location=target_key_location,
            side_label="左侧",
            filter_context=filter_context,
        )
    if filtered_reference_frame.empty:
        _append_empty_dual_filter_warning(
            abnormal_results,
            rule_name=rule_name,
            location=reference_key_location,
            side_label="右侧",
            filter_context=filter_context,
        )
    if abnormal_results:
        return abnormal_results

    _raise_duplicate_dual_keys(
        filtered_target_frame,
        side_label="左侧",
        key_field=left_key_field,
        variable=target_variable,
    )
    _raise_duplicate_dual_keys(
        filtered_reference_frame,
        side_label="右侧",
        key_field=right_key_field,
        variable=reference_variable,
    )

    target_by_key = filtered_target_frame.set_index(left_key_field, drop=False)
    reference_by_key = filtered_reference_frame.set_index(right_key_field, drop=False)

    for key in target_by_key.index.tolist():
        if key not in reference_by_key.index:
            row = target_by_key.loc[key]
            abnormal_results.append(
                build_fixed_result(
                    row_index=int(row["_row_index"]),
                    raw_value=key,
                    display_value=_get_row_display_value(row, display_field),
                    rule_name=rule_name,
                    location=target_key_location,
                    message=f"目标组合变量中缺失该 Key ({key})。{filter_context}",
                )
            )
            continue

        target_row = target_by_key.loc[key]
        reference_row = reference_by_key.loc[key]
        if (
            target_tag == reference_tag
            and int(target_row["_row_index"]) == int(reference_row["_row_index"])
        ):
            continue
        abnormal_results.extend(
            _evaluate_dual_composite_key(
                rule_name=rule_name,
                key=str(key),
                target_variable=target_variable,
                reference_variable=reference_variable,
                target_row=target_row,
                reference_row=reference_row,
                comparisons=comparisons,
                display_field=display_field,
                filter_context=filter_context,
            )
        )

    if key_check_mode == "bidirectional":
        for key in reference_by_key.index.tolist():
            if key in target_by_key.index:
                continue
            row = reference_by_key.loc[key]
            abnormal_results.append(
                build_fixed_result(
                    row_index=int(row["_row_index"]),
                    raw_value=key,
                    display_value=_get_row_display_value(row, display_field),
                    rule_name=rule_name,
                    location=reference_key_location,
                    message=f"基准组合变量中缺失该 Key ({key})。{filter_context}",
                )
            )

    return abnormal_results


def _evaluate_dual_composite_key(
    *,
    rule_name: str,
    key: str,
    target_variable: VariableTag,
    reference_variable: VariableTag,
    target_row: pd.Series,
    reference_row: pd.Series,
    comparisons: list[DualCompositeComparison],
    display_field: str | None,
    filter_context: str = "",
) -> list[dict[str, Any]]:
    """执行单个 Key 上的全部字段比较。"""
    abnormal_results: list[dict[str, Any]] = []

    for comparison in comparisons:
        left_field = comparison.left_field
        right_field = comparison.right_field
        operator = comparison.operator
        row_index = int(target_row["_row_index"])
        location = (
            f"{target_variable.sheet} -> {_get_field_display_name(target_variable, left_field)}"
            f" ⇄ {reference_variable.sheet} -> {_get_field_display_name(reference_variable, right_field)}"
        )

        if left_field not in target_row.index:
            abnormal_results.append(
                build_fixed_result(
                    row_index=row_index,
                    raw_value=key,
                    display_value=_get_row_display_value(target_row, display_field),
                    rule_name=rule_name,
                    location=location,
                    message=f"Key {key} 的基准变量缺少字段 {left_field}。{filter_context}",
                )
            )
            continue
        if right_field not in reference_row.index:
            abnormal_results.append(
                build_fixed_result(
                    row_index=row_index,
                    raw_value=key,
                    display_value=_get_row_display_value(target_row, display_field),
                    rule_name=rule_name,
                    location=location,
                    message=f"Key {key} 的目标变量缺少字段 {right_field}。{filter_context}",
                )
            )
            continue

        left_value = target_row[left_field]
        right_value = reference_row[right_field]
        left_label = _get_field_display_name(target_variable, left_field)
        right_label = _get_field_display_name(reference_variable, right_field)

        if operator == "not_null":
            if is_empty_value(left_value) or is_empty_value(right_value):
                abnormal_results.append(
                    build_fixed_result(
                        row_index=row_index,
                        raw_value=left_value,
                        display_value=_get_row_display_value(target_row, display_field),
                        rule_name=rule_name,
                        location=location,
                        message=(
                            f"Key {key} 字段非空失败：基准变量({left_label}={left_value}) / "
                            f"目标变量({right_label}={right_value}) 不能为空。{filter_context}"
                        ),
                    )
                )
            continue

        result = evaluate_compare_assertion(
            actual_value=left_value,
            operator=operator,
            expected_value=right_value,
        )
        if result.incomparable:
            abnormal_results.append(
                build_fixed_result(
                    row_index=row_index,
                    raw_value=left_value,
                    display_value=_get_row_display_value(target_row, display_field),
                    rule_name=rule_name,
                    location=location,
                    message=(
                        f"Key {key} 字段比对失败：基准变量({left_label}={left_value}) 与 "
                        f"目标变量({right_label}={right_value}) 无法按数值比较。{filter_context}"
                    ),
                )
            )
            continue
        if result.failed:
            operator_text = {"eq": "=", "ne": "!=", "gt": ">", "lt": "<"}[operator]
            abnormal_results.append(
                build_fixed_result(
                    row_index=row_index,
                    raw_value=left_value,
                    display_value=_get_row_display_value(target_row, display_field),
                    rule_name=rule_name,
                    location=location,
                    message=(
                        f"字段比对失败：Key {key} 下，基准变量({left_label}={left_value}) "
                        f"{operator_text} 目标变量({right_label}={right_value}) 不成立。{filter_context}"
                    ),
                )
            )

    return abnormal_results

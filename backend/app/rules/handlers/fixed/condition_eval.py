"""固定规则组合条件求值与共用断言执行。"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from backend.app.api.fixed_rules_schemas import (
    CompositeBranch,
    CompositeCondition,
    MultiCompositeMappingExclusionRange,
    MultiCompositeMappingFilter,
)
from backend.app.api.schemas import VariableTag
from backend.app.rules.domain.operators import (
    COMPARE_OPERATORS,
    evaluate_compare_assertion,
    is_not_null_violation,
    matches_compare_filter,
    matches_contains_filter,
    matches_not_contains_filter,
    matches_not_null_filter,
    normalize_expected_value_mode,
    parse_expected_value_set,
)
from backend.app.rules.domain.result import build_fixed_result
from backend.app.rules.domain.value import is_empty_value, normalize_fixed_text
from backend.app.rules.handlers.fixed.common import (
    _build_rule_location,
    _get_expected_value_set_display,
    _get_field_display_name,
    _get_row_display_value,
)


def _resolve_condition_expected_value(
    row: pd.Series,
    variable: VariableTag,
    condition: CompositeCondition,
) -> Any:
    """根据值来源解析条件右值。"""
    if condition.value_source == "field":
        expected_field = condition.expected_field or ""
        if expected_field not in row.index:
            raise ValueError(
                f"Composite rule references unknown field '{expected_field}'."
            )
        return row[expected_field]
    return condition.expected_value


def _apply_composite_filters(
    frame: pd.DataFrame,
    variable: VariableTag,
    conditions: list[CompositeCondition],
) -> pd.DataFrame:
    """按 AND 关系顺序应用组合变量筛选条件。"""
    if not conditions or frame.empty:
        return frame

    filtered = frame
    for condition in conditions:
        mask = _build_composite_filter_mask(filtered, variable, condition)
        filtered = filtered.loc[mask].copy()
        if filtered.empty:
            return filtered

    return filtered


def _build_composite_filter_mask(
    frame: pd.DataFrame,
    variable: VariableTag,
    condition: CompositeCondition,
) -> pd.Series:
    """生成单条组合变量筛选条件的命中布尔序列。"""
    field = condition.field
    if field not in frame.columns:
        raise ValueError(
            f"Composite variable '{variable.tag}' is missing field '{field}'."
        )

    series = frame[field]
    if condition.operator == "not_null":
        return series.apply(matches_not_null_filter)
    if condition.operator == "contains":
        return series.apply(
            lambda value: matches_contains_filter(
                actual_value=value,
                expected_value=condition.expected_value,
            )
        )
    if condition.operator == "not_contains":
        return series.apply(
            lambda value: matches_not_contains_filter(
                actual_value=value,
                expected_value=condition.expected_value,
            )
        )
    return frame.apply(
        lambda row: matches_compare_filter(
            actual_value=row[field],
            operator=condition.operator,
            expected_value=_resolve_condition_expected_value(row, variable, condition),
            expected_value_mode=condition.expected_value_mode
            if condition.value_source != "field"
            else None,
        ),
        axis=1,
    )


def _build_compare_failure_message(
    *,
    variable: VariableTag,
    branch_title: str,
    condition: CompositeCondition,
    expected_display: str,
) -> str:
    """生成组合变量比较断言失败的提示语。"""
    field_name = _get_field_display_name(variable, condition.field)
    is_rule_set = (
        condition.operator in {"eq", "ne"}
        and condition.value_source != "field"
        and normalize_expected_value_mode(condition.expected_value_mode) == "set"
    )
    if condition.operator == "eq":
        if is_rule_set:
            return f"{branch_title}：{field_name} 应等于规则集中的任一值：{expected_display}。"
        return f"{branch_title}：{field_name} 应等于 {expected_display}。"
    if condition.operator == "ne":
        if is_rule_set:
            return f"{branch_title}：{field_name} 不应等于规则集中的任一值：{expected_display}。"
        return f"{branch_title}：{field_name} 不应等于 {expected_display}。"
    if condition.operator == "gt":
        return f"{branch_title}：{field_name} 应大于 {expected_display}。"
    return f"{branch_title}：{field_name} 应小于 {expected_display}。"


def _evaluate_row_assertion(
    *,
    variable: VariableTag,
    branch_title: str,
    rule_name: str,
    frame: pd.DataFrame,
    condition: CompositeCondition,
    display_field: str | None,
) -> list[dict[str, Any]]:
    """执行组合变量的逐行断言。"""
    abnormal_results: list[dict[str, Any]] = []
    field = condition.field
    location = _build_rule_location(variable, field)

    for _, row in frame.iterrows():
        actual_value = row[field]

        if condition.operator == "not_null":
            if is_not_null_violation(actual_value):
                abnormal_results.append(
                    build_fixed_result(
                        row_index=row["_row_index"],
                        raw_value=actual_value,
                        display_value=_get_row_display_value(row, display_field),
                        rule_name=rule_name,
                        location=location,
                        message=f"{branch_title}：{_get_field_display_name(variable, field)} 不能为空。",
                    )
                )
            continue

        expected_value = _resolve_condition_expected_value(row, variable, condition)
        expected_display = (
            _get_field_display_name(variable, condition.expected_field or "")
            if condition.value_source == "field"
            else (
                _get_expected_value_set_display(condition.expected_value or "")
                if condition.operator in {"eq", "ne"}
                and normalize_expected_value_mode(condition.expected_value_mode) == "set"
                else str(condition.expected_value or "")
            )
        )

        result = evaluate_compare_assertion(
            actual_value=actual_value,
            operator=condition.operator,
            expected_value=expected_value,
            expected_value_mode=condition.expected_value_mode
            if condition.value_source != "field"
            else None,
        )

        if result.incomparable:
            abnormal_results.append(
                build_fixed_result(
                    row_index=row["_row_index"],
                    raw_value=actual_value,
                    display_value=_get_row_display_value(row, display_field),
                    rule_name=rule_name,
                    location=location,
                    message=(
                        f"{branch_title}：{_get_field_display_name(variable, field)} 无法按数值与 "
                        f"{expected_display} 进行比较。"
                    ),
                )
            )
            continue

        if result.failed:
            abnormal_results.append(
                build_fixed_result(
                    row_index=row["_row_index"],
                    raw_value=actual_value,
                    display_value=_get_row_display_value(row, display_field),
                    rule_name=rule_name,
                    location=location,
                    message=_build_compare_failure_message(
                        variable=variable,
                        branch_title=branch_title,
                        condition=condition,
                        expected_display=expected_display,
                    ),
                )
            )

    return abnormal_results


def _evaluate_unique_assertion(
    *,
    variable: VariableTag,
    branch_title: str,
    rule_name: str,
    frame: pd.DataFrame,
    condition: CompositeCondition,
    display_field: str | None,
) -> list[dict[str, Any]]:
    """执行组合变量的唯一性断言。"""
    field = condition.field
    series = frame[field]
    non_empty_mask = ~series.apply(is_empty_value)
    duplicated_mask = series[non_empty_mask].duplicated(keep=False)
    invalid_rows = frame.loc[non_empty_mask].loc[duplicated_mask]
    location = _build_rule_location(variable, field)

    return [
        build_fixed_result(
            row_index=row["_row_index"],
            raw_value=row[field],
            display_value=_get_row_display_value(row, display_field),
            rule_name=rule_name,
            location=location,
            level="warning",
            message=(
                f"{branch_title}：{_get_field_display_name(variable, field)} 在当前分支命中数据中应保持唯一。"
            ),
        )
        for _, row in invalid_rows.iterrows()
    ]


def _evaluate_duplicate_required_assertion(
    *,
    variable: VariableTag,
    branch_title: str,
    rule_name: str,
    frame: pd.DataFrame,
    condition: CompositeCondition,
    display_field: str | None,
) -> list[dict[str, Any]]:
    """执行“至少存在一组重复值”的集合断言。"""
    field = condition.field
    series = frame[field]
    non_empty_mask = ~series.apply(is_empty_value)
    candidate_rows = frame.loc[non_empty_mask]
    if candidate_rows.empty:
        return []

    duplicated_mask = candidate_rows[field].duplicated(keep=False)
    if duplicated_mask.any():
        return []

    location = _build_rule_location(variable, field)
    return [
        build_fixed_result(
            row_index=row["_row_index"],
            raw_value=row[field],
            display_value=_get_row_display_value(row, display_field),
            rule_name=rule_name,
            location=location,
            level="warning",
            message=(
                f"{branch_title}：{_get_field_display_name(variable, field)} 在当前分支命中数据中至少需要出现一组重复值。"
            ),
        )
        for _, row in candidate_rows.iterrows()
    ]


def _evaluate_regex_assertion(
    *,
    variable: VariableTag,
    branch_title: str,
    rule_name: str,
    frame: pd.DataFrame,
    condition: CompositeCondition,
    display_field: str | None,
) -> list[dict[str, Any]]:
    """执行组合变量分支上的正则断言。"""
    compiled_pattern = re.compile(condition.expected_value or "")
    field = condition.field
    location = _build_rule_location(variable, field)
    return [
        build_fixed_result(
            row_index=row["_row_index"],
            raw_value=row[field],
            display_value=_get_row_display_value(row, display_field),
            rule_name=rule_name,
            location=location,
            message=(
                f"{branch_title}：{_get_field_display_name(variable, field)} 不符合正则格式"
                f" {condition.expected_value or ''}。"
            ),
        )
        for _, row in frame.iterrows()
        if not compiled_pattern.fullmatch(
            "" if normalize_fixed_text(row[field]) is None else normalize_fixed_text(row[field]) or ""
        )
    ]


def _evaluate_composite_branch_assertions(
    *,
    variable: VariableTag,
    branch_title: str,
    rule_name: str,
    frame: pd.DataFrame,
    branch: CompositeBranch,
    display_field: str | None,
) -> list[dict[str, Any]]:
    """执行单个分支上的所有断言。"""
    abnormal_results: list[dict[str, Any]] = []

    for condition in branch.assertions:
        if condition.operator in COMPARE_OPERATORS or condition.operator == "not_null":
            abnormal_results.extend(
                _evaluate_row_assertion(
                    variable=variable,
                    branch_title=branch_title,
                    rule_name=rule_name,
                    frame=frame,
                    condition=condition,
                    display_field=display_field,
                )
            )
        elif condition.operator == "unique":
            abnormal_results.extend(
                _evaluate_unique_assertion(
                    variable=variable,
                    branch_title=branch_title,
                    rule_name=rule_name,
                    frame=frame,
                    condition=condition,
                    display_field=display_field,
                )
            )
        elif condition.operator == "duplicate_required":
            abnormal_results.extend(
                _evaluate_duplicate_required_assertion(
                    variable=variable,
                    branch_title=branch_title,
                    rule_name=rule_name,
                    frame=frame,
                    condition=condition,
                    display_field=display_field,
                )
            )
        elif condition.operator == "regex":
            abnormal_results.extend(
                _evaluate_regex_assertion(
                    variable=variable,
                    branch_title=branch_title,
                    rule_name=rule_name,
                    frame=frame,
                    condition=condition,
                    display_field=display_field,
                )
            )
        else:  # pragma: no cover - 接口层与 service 已做校验
            raise ValueError(
                f"Unsupported composite assertion operator '{condition.operator}'."
            )

    return abnormal_results


def _evaluate_pipeline_node_assertions(
    *,
    variable: VariableTag,
    node_title: str,
    rule_name: str,
    frame: pd.DataFrame,
    assertions: list[CompositeCondition],
    display_field: str | None,
) -> list[dict[str, Any]]:
    """执行多组合变量串行校验单个节点上的全部最终判定。"""
    abnormal_results: list[dict[str, Any]] = []

    for condition in assertions:
        if condition.operator in COMPARE_OPERATORS or condition.operator == "not_null":
            abnormal_results.extend(
                _evaluate_row_assertion(
                    variable=variable,
                    branch_title=node_title,
                    rule_name=rule_name,
                    frame=frame,
                    condition=condition,
                    display_field=display_field,
                )
            )
        elif condition.operator == "unique":
            abnormal_results.extend(
                _evaluate_unique_assertion(
                    variable=variable,
                    branch_title=node_title,
                    rule_name=rule_name,
                    frame=frame,
                    condition=condition,
                    display_field=display_field,
                )
            )
        elif condition.operator == "duplicate_required":
            abnormal_results.extend(
                _evaluate_duplicate_required_assertion(
                    variable=variable,
                    branch_title=node_title,
                    rule_name=rule_name,
                    frame=frame,
                    condition=condition,
                    display_field=display_field,
                )
            )
        elif condition.operator == "regex":
            abnormal_results.extend(
                _evaluate_regex_assertion(
                    variable=variable,
                    branch_title=node_title,
                    rule_name=rule_name,
                    frame=frame,
                    condition=condition,
                    display_field=display_field,
                )
            )
        else:  # pragma: no cover - 接口层与 service 已做校验
            raise ValueError(
                f"Unsupported pipeline assertion operator '{condition.operator}'."
            )

    return abnormal_results


def _is_row_in_mapping_exclusion_ranges(
    row_index: int,
    actual_value: Any,
    ranges: list[MultiCompositeMappingExclusionRange],
) -> bool:
    """判断筛选失败行是否同时命中排除行号范围与判定值集合。"""
    actual_text = normalize_fixed_text(actual_value)
    for row_range in ranges:
        if not (row_range.start_row <= row_index <= row_range.end_row):
            continue
        expected_value = (row_range.expected_value or "").strip()
        if not expected_value:
            raise ValueError("Mapping exclusion range requires expected_value.")
        if actual_text in parse_expected_value_set(expected_value):
            return True
    return False


def _validate_mapping_exclusion_ranges(
    ranges: list[MultiCompositeMappingExclusionRange],
) -> None:
    """提前校验排除范围判定值，避免无异常行时漏掉配置问题。"""
    for row_range in ranges:
        expected_value = (row_range.expected_value or "").strip()
        if not expected_value:
            raise ValueError("Mapping exclusion range requires expected_value.")
        parse_expected_value_set(expected_value)


def _evaluate_mapping_filter_check(
    *,
    variable: VariableTag,
    node_title: str,
    filter_title: str,
    rule_name: str,
    frame: pd.DataFrame,
    condition: MultiCompositeMappingFilter,
    display_field: str | None,
) -> list[dict[str, Any]]:
    """按单条筛选条件检查失败行，并应用筛选失败排除行号范围。"""
    abnormal_results: list[dict[str, Any]] = []
    field = condition.field
    location = _build_rule_location(variable, field)
    field_name = _get_field_display_name(variable, field)
    if field not in frame.columns:
        raise ValueError(f"Mapping rule references unknown field '{field}'.")
    _validate_mapping_exclusion_ranges(condition.exclusion_ranges)

    matched_mask = _build_composite_filter_mask(frame, variable, condition)
    failed_frame = frame.loc[~matched_mask].copy()
    if failed_frame.empty:
        return abnormal_results

    for _, row in failed_frame.iterrows():
        row_index = int(row["_row_index"])
        actual_value = row[field]
        if _is_row_in_mapping_exclusion_ranges(row_index, actual_value, condition.exclusion_ranges):
            continue
        abnormal_results.append(
            build_fixed_result(
                row_index=row_index,
                raw_value=actual_value,
                display_value=_get_row_display_value(row, display_field),
                rule_name=rule_name,
                location=location,
                message=(
                    f"{node_title} / {filter_title}：Excel 第 {row_index} 行未通过筛选条件，"
                    f"字段 {field_name} 未命中筛选失败排除行号范围或判定值。"
                ),
            )
        )

    return abnormal_results


def _format_dual_filter_summary(
    *,
    variable: VariableTag,
    filters: list[CompositeCondition],
) -> str:
    """生成同变量筛选对比时用于结果文案的筛选摘要。"""
    if not filters:
        return "全量"

    operator_text = {
        "eq": "=",
        "ne": "!=",
        "gt": ">",
        "lt": "<",
        "not_null": "非空",
        "contains": "包含",
        "not_contains": "不包含",
    }
    parts: list[str] = []
    for condition in filters:
        field_label = _get_field_display_name(variable, condition.field)
        operator = operator_text.get(condition.operator, condition.operator)
        if condition.operator == "not_null":
            parts.append(f"{field_label} 非空")
            continue
        expected = (
            _get_field_display_name(variable, condition.expected_field or "")
            if condition.value_source == "field"
            else condition.expected_value or ""
        )
        parts.append(f"{field_label} {operator} {expected}")
    return "；".join(parts)


def _build_dual_filter_context(
    *,
    target_variable: VariableTag,
    reference_variable: VariableTag,
    left_filters: list[CompositeCondition],
    right_filters: list[CompositeCondition],
) -> str:
    """同变量模式下为异常文案追加左右筛选说明。"""
    if target_variable.tag != reference_variable.tag:
        return ""
    return (
        f" [左侧筛选: {_format_dual_filter_summary(variable=target_variable, filters=left_filters)}; "
        f"右侧筛选: {_format_dual_filter_summary(variable=reference_variable, filters=right_filters)}]"
    )


def _append_empty_dual_filter_warning(
    abnormal_results: list[dict[str, Any]],
    *,
    rule_name: str,
    location: str,
    side_label: str,
    filter_context: str,
) -> None:
    """筛选后无数据时输出非阻断提醒，避免静默通过。"""
    abnormal_results.append(
        build_fixed_result(
            row_index=0,
            raw_value="",
            rule_name=rule_name,
            location=location,
            level="warning",
            message=f"{side_label}筛选后无数据，未执行字段比对。{filter_context}",
        )
    )


def _raise_duplicate_dual_keys(
    frame: pd.DataFrame,
    *,
    side_label: str,
    key_field: str,
    variable: VariableTag,
) -> None:
    """双组合变量比对要求筛选后 Key 唯一，避免一对多比较语义不清。"""
    if key_field not in frame.columns:
        raise ValueError(
            f"{side_label}组合变量 '{variable.tag}' 缺少关联 Key 字段 '{key_field}'。"
        )
    duplicate_mask = frame[key_field].duplicated(keep=False)
    if not duplicate_mask.any():
        return
    duplicate_keys = [str(key) for key in frame.loc[duplicate_mask, key_field].drop_duplicates().tolist()]
    preview = "、".join(duplicate_keys[:10])
    suffix = "..." if len(duplicate_keys) > 10 else ""
    key_label = _get_field_display_name(variable, key_field)
    raise ValueError(
        f"{side_label}筛选后关联 Key 字段 {key_label} 存在重复值 {preview}{suffix}，无法对齐比较；"
        "请检查关联 Key 字段或筛选条件。"
    )

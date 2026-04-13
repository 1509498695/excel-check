"""固定规则模块的单变量与组合变量规则执行器。"""

from __future__ import annotations

from typing import Any

import pandas as pd

from backend.app.api.fixed_rules_schemas import (
    CompositeBranch,
    CompositeCondition,
    CompositeRuleConfig,
)
from backend.app.api.schemas import ValidationRule, VariableTag
from backend.app.rules.engine_core import RuleExecutionContext, register_rule
from backend.app.rules.rule_basics import _is_empty_value


COMPOSITE_KEY_FIELD = "__key__"
COMPARE_OPERATORS = {"eq", "ne", "gt", "lt"}
SET_STYLE_OPERATORS = {"unique", "duplicate_required"}


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
    """尝试把值转成数字，失败时返回 `None`。"""
    normalized = _normalize_fixed_text(value)
    if normalized in {None, ""}:
        return None
    try:
        return float(normalized)
    except ValueError:
        return None


def _get_variable_by_tag(
    context: RuleExecutionContext,
    tag: str,
    rule_type: str,
) -> VariableTag:
    """按变量标签查找变量定义，并确保存在。"""
    variable = next(
        (item for item in context.task_tree.variables if item.tag == tag),
        None,
    )
    if variable is None:
        raise ValueError(f"Rule '{rule_type}' references unknown tag '{tag}'.")
    return variable


def _get_single_variable_frame(
    context: RuleExecutionContext,
    tag: str,
    rule_type: str,
) -> tuple[VariableTag, pd.DataFrame, str]:
    """读取单变量规则依赖的数据切片。"""
    variable = _get_variable_by_tag(context, tag, rule_type)
    if (variable.variable_kind or "single") != "single" or not variable.column:
        raise ValueError(
            f"Rule '{rule_type}' only supports single variables, got '{tag}'."
        )

    frame = context.loaded_variables.get(tag)
    if frame is None:
        raise ValueError(f"Rule '{rule_type}' references unknown tag '{tag}'.")
    return variable, frame, variable.column


def _get_composite_variable_frame(
    context: RuleExecutionContext,
    tag: str,
    rule_type: str,
) -> tuple[VariableTag, pd.DataFrame]:
    """读取组合变量规则依赖的数据切片。"""
    variable = _get_variable_by_tag(context, tag, rule_type)
    if (variable.variable_kind or "single") != "composite":
        raise ValueError(
            f"Rule '{rule_type}' only supports composite variables, got '{tag}'."
        )

    frame = context.loaded_variables.get(tag)
    if frame is None:
        raise ValueError(f"Rule '{rule_type}' references unknown tag '{tag}'.")
    return variable, frame


def _get_field_display_name(variable: VariableTag, field: str) -> str:
    """把内部字段名转换为更友好的展示名。"""
    if field == COMPOSITE_KEY_FIELD:
        key_column = (variable.key_column or "").strip()
        return f"{key_column} (Key)" if key_column else "Key(映射键)"
    return field


def _build_rule_location(variable: VariableTag, field: str) -> str:
    """构建固定规则结果里的定位信息。"""
    return f"{variable.sheet} -> {_get_field_display_name(variable, field)}"


def _build_fixed_rule_result(
    *,
    row_index: int,
    raw_value: Any,
    rule_name: str,
    location: str,
    message: str,
    level: str = "error",
) -> dict[str, Any]:
    """构建固定规则模块的统一异常结构。"""
    if hasattr(raw_value, "item"):
        raw_value = raw_value.item()
    return {
        "level": level,
        "rule_name": rule_name,
        "location": location,
        "row_index": int(row_index),
        "raw_value": raw_value,
        "message": message,
    }


def _get_composite_rule_config(rule: ValidationRule) -> CompositeRuleConfig:
    """读取并校验组合变量条件分支规则配置。"""
    config_payload = rule.params.get("composite_config")
    if not isinstance(config_payload, dict):
        raise ValueError(
            f"Rule '{rule.rule_type}' requires params.composite_config."
        )
    try:
        return CompositeRuleConfig.model_validate(config_payload)
    except Exception as exc:  # pragma: no cover - 非法配置由接口层先挡一层
        raise ValueError(
            f"Rule '{rule.rule_type}' provides invalid composite_config: {exc}"
        ) from exc


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


def _matches_compare_filter(
    *,
    actual_value: Any,
    operator: str,
    expected_value: Any,
) -> bool:
    """在筛选阶段判断一条比较条件是否命中。"""
    if operator in {"eq", "ne"}:
        actual_text = _normalize_fixed_text(actual_value)
        expected_text = _normalize_fixed_text(expected_value)
        is_match = actual_text == expected_text
        return is_match if operator == "eq" else not is_match

    actual_number = _to_number(actual_value)
    expected_number = _to_number(expected_value)
    if actual_number is None or expected_number is None:
        return False
    return actual_number > expected_number if operator == "gt" else actual_number < expected_number


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
        field = condition.field
        if field not in filtered.columns:
            raise ValueError(
                f"Composite variable '{variable.tag}' is missing field '{field}'."
            )

        series = filtered[field]
        if condition.operator == "not_null":
            mask = ~series.apply(_is_empty_value)
        else:
            mask = filtered.apply(
                lambda row: _matches_compare_filter(
                    actual_value=row[field],
                    operator=condition.operator,
                    expected_value=_resolve_condition_expected_value(row, variable, condition),
                ),
                axis=1,
            )
        filtered = filtered.loc[mask].copy()
        if filtered.empty:
            return filtered

    return filtered


def _build_compare_failure_message(
    *,
    variable: VariableTag,
    branch_title: str,
    condition: CompositeCondition,
    expected_display: str,
) -> str:
    """生成组合变量比较断言失败的提示语。"""
    field_name = _get_field_display_name(variable, condition.field)
    if condition.operator == "eq":
        return f"{branch_title}：{field_name} 应等于 {expected_display}。"
    if condition.operator == "ne":
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
) -> list[dict[str, Any]]:
    """执行组合变量的逐行断言。"""
    abnormal_results: list[dict[str, Any]] = []
    field = condition.field
    location = _build_rule_location(variable, field)

    for _, row in frame.iterrows():
        actual_value = row[field]

        if condition.operator == "not_null":
            if _is_empty_value(actual_value):
                abnormal_results.append(
                    _build_fixed_rule_result(
                        row_index=row["_row_index"],
                        raw_value=actual_value,
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
            else str(condition.expected_value or "")
        )

        if condition.operator in {"eq", "ne"}:
            actual_text = _normalize_fixed_text(actual_value)
            expected_text = _normalize_fixed_text(expected_value)
            is_match = actual_text == expected_text
            failed = not is_match if condition.operator == "eq" else is_match
            if failed:
                abnormal_results.append(
                    _build_fixed_rule_result(
                        row_index=row["_row_index"],
                        raw_value=actual_value,
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
            continue

        actual_number = _to_number(actual_value)
        expected_number = _to_number(expected_value)
        if actual_number is None or expected_number is None:
            abnormal_results.append(
                _build_fixed_rule_result(
                    row_index=row["_row_index"],
                    raw_value=actual_value,
                    rule_name=rule_name,
                    location=location,
                    message=(
                        f"{branch_title}：{_get_field_display_name(variable, field)} 无法按数值与 "
                        f"{expected_display} 进行比较。"
                    ),
                )
            )
            continue

        failed = (
            actual_number <= expected_number
            if condition.operator == "gt"
            else actual_number >= expected_number
        )
        if failed:
            abnormal_results.append(
                _build_fixed_rule_result(
                    row_index=row["_row_index"],
                    raw_value=actual_value,
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
) -> list[dict[str, Any]]:
    """执行组合变量的唯一性断言。"""
    field = condition.field
    series = frame[field]
    non_empty_mask = ~series.apply(_is_empty_value)
    duplicated_mask = series[non_empty_mask].duplicated(keep=False)
    invalid_rows = frame.loc[non_empty_mask].loc[duplicated_mask]
    location = _build_rule_location(variable, field)

    return [
        _build_fixed_rule_result(
            row_index=row["_row_index"],
            raw_value=row[field],
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
) -> list[dict[str, Any]]:
    """执行“至少存在一组重复值”的集合断言。"""
    field = condition.field
    series = frame[field]
    non_empty_mask = ~series.apply(_is_empty_value)
    candidate_rows = frame.loc[non_empty_mask]
    if candidate_rows.empty:
        return []

    duplicated_mask = candidate_rows[field].duplicated(keep=False)
    if duplicated_mask.any():
        return []

    location = _build_rule_location(variable, field)
    return [
        _build_fixed_rule_result(
            row_index=row["_row_index"],
            raw_value=row[field],
            rule_name=rule_name,
            location=location,
            level="warning",
            message=(
                f"{branch_title}：{_get_field_display_name(variable, field)} 在当前分支命中数据中至少需要出现一组重复值。"
            ),
        )
        for _, row in candidate_rows.iterrows()
    ]


def _evaluate_composite_branch_assertions(
    *,
    variable: VariableTag,
    branch_title: str,
    rule_name: str,
    frame: pd.DataFrame,
    branch: CompositeBranch,
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
                )
            )
        else:  # pragma: no cover - 接口层与 service 已做校验
            raise ValueError(
                f"Unsupported composite assertion operator '{condition.operator}'."
            )

    return abnormal_results


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

    variable, frame, column_name = _get_single_variable_frame(
        context,
        target_tag,
        rule.rule_type,
    )
    abnormal_results: list[dict[str, Any]] = []
    location = f"{variable.sheet} -> {column_name}"

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
                    location=location,
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
            _build_fixed_rule_result(
                row_index=row["_row_index"],
                raw_value=raw_value,
                rule_name=rule_name,
                location=location,
                message=message,
            )
        )

    return abnormal_results


@register_rule("composite_condition_check")
def check_composite_condition_check(
    rule: ValidationRule,
    context: RuleExecutionContext,
) -> list[dict[str, Any]]:
    """执行组合变量条件分支校验。"""
    target_tag = _get_fixed_rule_param(rule, "target_tag")
    rule_name = _get_fixed_rule_param(rule, "rule_name")
    composite_config = _get_composite_rule_config(rule)
    variable, frame = _get_composite_variable_frame(context, target_tag, rule.rule_type)

    filtered_frame = _apply_composite_filters(
        frame,
        variable,
        composite_config.global_filters,
    )
    if filtered_frame.empty:
        return []

    abnormal_results: list[dict[str, Any]] = []
    for branch_index, branch in enumerate(composite_config.branches, start=1):
        branch_frame = _apply_composite_filters(filtered_frame, variable, branch.filters)
        if branch_frame.empty:
            continue

        branch_title = f"分支 {branch_index}"
        abnormal_results.extend(
            _evaluate_composite_branch_assertions(
                variable=variable,
                branch_title=branch_title,
                rule_name=rule_name,
                frame=branch_frame,
                branch=branch,
            )
        )

    return abnormal_results

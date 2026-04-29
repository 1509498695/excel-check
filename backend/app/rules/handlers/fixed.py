"""固定规则模块的单变量与组合变量规则执行器。"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from backend.app.api.fixed_rules_schemas import (
    CompositeBranch,
    CompositeCondition,
    CompositeRuleConfig,
    DualCompositeComparison,
    MultiCompositeMappingConfig,
    MultiCompositeMappingExclusionRange,
    MultiCompositeMappingFilter,
    MultiCompositePipelineConfig,
)
from backend.app.api.schemas import ValidationRule, VariableTag
from backend.app.rules.domain.operators import (
    COMPARE_OPERATORS,
    SET_STYLE_OPERATORS,  # noqa: F401  保留导出，下游 Phase 2 拆分时复用
    evaluate_compare_assertion,
    format_expected_value_set,
    is_not_null_violation,
    matches_compare_filter,
    matches_contains_filter,
    matches_expected_text,
    matches_not_contains_filter,
    matches_not_null_filter,
    normalize_expected_value_mode,
    parse_expected_value_set,
)
from backend.app.rules.domain.result import build_fixed_result
from backend.app.rules.domain.value import (
    is_empty_value,
    normalize_fixed_text,
    to_number,
)
from backend.app.rules.engine_core import RuleExecutionContext, register_rule
from backend.app.rules.infrastructure.tag_extractor import (
    by_mapping_node_tags,
    by_pipeline_node_tags,
    by_reference_and_target_tag,
    by_target_tag,
)


COMPOSITE_KEY_FIELD = "__key__"


def _get_fixed_rule_param(rule: ValidationRule, param_name: str) -> str:
    """读取固定规则所需的单值参数。"""
    value = rule.params.get(param_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Rule '{rule.rule_type}' requires params.{param_name}.")
    return value.strip()


def _get_fixed_rule_expected_value_mode(rule: ValidationRule) -> str:
    """读取固定值比较模式，缺省保持历史单值语义。"""
    try:
        return normalize_expected_value_mode(rule.params.get("expected_value_mode"))
    except ValueError as exc:
        raise ValueError(
            f"Rule '{rule.rule_type}' requires params.expected_value_mode to be 'single' or 'set'."
        ) from exc


def _get_expected_value_set_display(expected_value: str) -> str:
    """统一规则集异常提示里的值列表展示。"""
    return format_expected_value_set(parse_expected_value_set(expected_value))


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


def _get_dual_composite_comparisons(rule: ValidationRule) -> list[DualCompositeComparison]:
    """读取并校验双组合变量比对规则的字段比较列表。"""
    payload = rule.params.get("comparisons")
    if not isinstance(payload, list) or not payload:
        raise ValueError(f"Rule '{rule.rule_type}' requires non-empty params.comparisons.")

    comparisons: list[DualCompositeComparison] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError(f"Rule '{rule.rule_type}' provides invalid params.comparisons.")
        try:
            comparisons.append(DualCompositeComparison.model_validate(item))
        except Exception as exc:  # pragma: no cover
            raise ValueError(
                f"Rule '{rule.rule_type}' provides invalid comparison config: {exc}"
            ) from exc
    return comparisons


def _get_multi_composite_pipeline_config(
    rule: ValidationRule,
) -> MultiCompositePipelineConfig:
    """读取并校验多组合变量串行校验规则配置。"""
    config_payload = rule.params.get("pipeline_config")
    if not isinstance(config_payload, dict):
        raise ValueError(
            f"Rule '{rule.rule_type}' requires params.pipeline_config."
        )
    try:
        return MultiCompositePipelineConfig.model_validate(config_payload)
    except Exception as exc:  # pragma: no cover - 非法配置由接口层先挡一层
        raise ValueError(
            f"Rule '{rule.rule_type}' provides invalid pipeline_config: {exc}"
        ) from exc


def _get_multi_composite_mapping_config(
    rule: ValidationRule,
) -> MultiCompositeMappingConfig:
    """读取并校验多组映射校验规则配置。"""
    config_payload = rule.params.get("mapping_config")
    if not isinstance(config_payload, dict):
        raise ValueError(
            f"Rule '{rule.rule_type}' requires params.mapping_config."
        )
    try:
        return MultiCompositeMappingConfig.model_validate(config_payload)
    except Exception as exc:  # pragma: no cover - 非法配置由接口层先挡一层
        raise ValueError(
            f"Rule '{rule.rule_type}' provides invalid mapping_config: {exc}"
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
    non_empty_mask = ~series.apply(is_empty_value)
    duplicated_mask = series[non_empty_mask].duplicated(keep=False)
    invalid_rows = frame.loc[non_empty_mask].loc[duplicated_mask]
    location = _build_rule_location(variable, field)

    return [
        build_fixed_result(
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
) -> list[dict[str, Any]]:
    """执行组合变量分支上的正则断言。"""
    compiled_pattern = re.compile(condition.expected_value or "")
    field = condition.field
    location = _build_rule_location(variable, field)
    return [
        build_fixed_result(
            row_index=row["_row_index"],
            raw_value=row[field],
            rule_name=rule_name,
            location=location,
            message=(
                f"{branch_title}：{_get_field_display_name(variable, field)} 不符合正则格式"
                f" {condition.expected_value or ''}。"
            ),
        )
        for _, row in frame[[field, "_row_index"]].iterrows()
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
        elif condition.operator == "regex":
            abnormal_results.extend(
                _evaluate_regex_assertion(
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


def _evaluate_pipeline_node_assertions(
    *,
    variable: VariableTag,
    node_title: str,
    rule_name: str,
    frame: pd.DataFrame,
    assertions: list[CompositeCondition],
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
                )
            )
        else:  # pragma: no cover - 接口层与 service 已做校验
            raise ValueError(
                f"Unsupported pipeline assertion operator '{condition.operator}'."
            )

    return abnormal_results


def _is_row_in_mapping_exclusion_ranges(
    row_index: int,
    ranges: list[MultiCompositeMappingExclusionRange],
) -> bool:
    """判断筛选失败行是否命中当前筛选的排除范围。"""
    return any(row_range.start_row <= row_index <= row_range.end_row for row_range in ranges)


def _evaluate_mapping_filter_check(
    *,
    variable: VariableTag,
    node_title: str,
    filter_title: str,
    rule_name: str,
    frame: pd.DataFrame,
    condition: MultiCompositeMappingFilter,
) -> list[dict[str, Any]]:
    """按单条筛选条件检查失败行，并应用筛选失败排除行号范围。"""
    abnormal_results: list[dict[str, Any]] = []
    field = condition.field
    location = _build_rule_location(variable, field)
    field_name = _get_field_display_name(variable, field)
    if field not in frame.columns:
        raise ValueError(f"Mapping rule references unknown field '{field}'.")

    matched_mask = _build_composite_filter_mask(frame, variable, condition)
    failed_frame = frame.loc[~matched_mask].copy()
    if failed_frame.empty:
        return abnormal_results

    for _, row in failed_frame.iterrows():
        row_index = int(row["_row_index"])
        actual_value = row[field]
        if _is_row_in_mapping_exclusion_ranges(row_index, condition.exclusion_ranges):
            continue
        abnormal_results.append(
            build_fixed_result(
                row_index=row_index,
                raw_value=actual_value,
                rule_name=rule_name,
                location=location,
                message=(
                    f"{node_title} / {filter_title}：Excel 第 {row_index} 行未通过筛选条件，"
                    f"字段 {field_name} 未命中筛选失败排除行号范围。"
                ),
            )
        )

    return abnormal_results


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

    for _, row in frame[[column_name, "_row_index"]].iterrows():
        text = normalize_fixed_text(row[column_name])
        normalized_text = "" if text is None else text
        if compiled_pattern.fullmatch(normalized_text):
            continue
        abnormal_results.append(
            build_fixed_result(
                row_index=row["_row_index"],
                raw_value=row[column_name],
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
                rule_name=rule_name,
                location=location,
                message=message,
            )
        )

    return abnormal_results


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


@register_rule("composite_condition_check", dependent_tags=by_target_tag)
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


@register_rule("multi_composite_pipeline_check", dependent_tags=by_pipeline_node_tags)
def check_multi_composite_pipeline_check(
    rule: ValidationRule,
    context: RuleExecutionContext,
) -> list[dict[str, Any]]:
    """按节点顺序执行多组合变量串行校验，节点失败时短路后续节点。"""
    rule_name = _get_fixed_rule_param(rule, "rule_name")
    pipeline_config = _get_multi_composite_pipeline_config(rule)

    for node_index, node in enumerate(pipeline_config.nodes, start=1):
        variable, frame = _get_composite_variable_frame(
            context,
            node.variable_tag,
            rule.rule_type,
        )
        filtered_frame = _apply_composite_filters(frame, variable, node.filters)
        if filtered_frame.empty:
            continue

        node_title = f"节点 {node_index}"
        node_abnormal_results = _evaluate_pipeline_node_assertions(
            variable=variable,
            node_title=node_title,
            rule_name=rule_name,
            frame=filtered_frame,
            assertions=node.assertions,
        )
        if node_abnormal_results:
            return node_abnormal_results

    return []


@register_rule("multi_composite_mapping_check", dependent_tags=by_mapping_node_tags)
def check_multi_composite_mapping_check(
    rule: ValidationRule,
    context: RuleExecutionContext,
) -> list[dict[str, Any]]:
    """执行多组映射校验；所有节点独立执行并汇总异常。"""
    rule_name = _get_fixed_rule_param(rule, "rule_name")
    mapping_config = _get_multi_composite_mapping_config(rule)
    abnormal_results: list[dict[str, Any]] = []

    for node_index, node in enumerate(mapping_config.nodes, start=1):
        variable, frame = _get_composite_variable_frame(
            context,
            node.variable_tag,
            rule.rule_type,
        )

        node_title = f"映射节点 {node_index}"
        for filter_index, condition in enumerate(
            node.filters,
            start=1,
        ):
            abnormal_results.extend(
                _evaluate_mapping_filter_check(
                    variable=variable,
                    node_title=node_title,
                    filter_title=f"筛选条件 {filter_index}",
                    rule_name=rule_name,
                    frame=frame,
                    condition=condition,
                )
            )

    return abnormal_results


@register_rule("dual_composite_compare", dependent_tags=by_reference_and_target_tag)
def check_dual_composite_compare(
    rule: ValidationRule,
    context: RuleExecutionContext,
) -> list[dict[str, Any]]:
    """按外层 Key 关联两个组合变量，并逐项比较 Value 字段。"""
    target_tag = _get_fixed_rule_param(rule, "target_tag")
    reference_tag = _get_fixed_rule_param(rule, "reference_tag")
    key_check_mode = _get_fixed_rule_param(rule, "key_check_mode")
    rule_name = _get_fixed_rule_param(rule, "rule_name")
    comparisons = _get_dual_composite_comparisons(rule)

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

    target_by_key = target_frame.set_index(COMPOSITE_KEY_FIELD, drop=False)
    reference_by_key = reference_frame.set_index(COMPOSITE_KEY_FIELD, drop=False)
    abnormal_results: list[dict[str, Any]] = []
    target_key_location = _build_rule_location(target_variable, COMPOSITE_KEY_FIELD)
    reference_key_location = _build_rule_location(reference_variable, COMPOSITE_KEY_FIELD)

    for key in target_by_key.index.tolist():
        if key not in reference_by_key.index:
            row = target_by_key.loc[key]
            abnormal_results.append(
                build_fixed_result(
                    row_index=int(row["_row_index"]),
                    raw_value=key,
                    rule_name=rule_name,
                    location=target_key_location,
                    message=f"目标组合变量中缺失该 Key ({key})。",
                )
            )
            continue

        target_row = target_by_key.loc[key]
        reference_row = reference_by_key.loc[key]
        abnormal_results.extend(
            _evaluate_dual_composite_key(
                rule_name=rule_name,
                key=str(key),
                target_variable=target_variable,
                reference_variable=reference_variable,
                target_row=target_row,
                reference_row=reference_row,
                comparisons=comparisons,
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
                    rule_name=rule_name,
                    location=reference_key_location,
                    message=f"基准组合变量中缺失该 Key ({key})。",
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
                    rule_name=rule_name,
                    location=location,
                    message=f"Key {key} 的基准变量缺少字段 {left_field}。",
                )
            )
            continue
        if right_field not in reference_row.index:
            abnormal_results.append(
                build_fixed_result(
                    row_index=row_index,
                    raw_value=key,
                    rule_name=rule_name,
                    location=location,
                    message=f"Key {key} 的目标变量缺少字段 {right_field}。",
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
                        rule_name=rule_name,
                        location=location,
                        message=(
                            f"Key {key} 字段非空失败：基准变量({left_label}={left_value}) / "
                            f"目标变量({right_label}={right_value}) 不能为空。"
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
                    rule_name=rule_name,
                    location=location,
                    message=(
                        f"Key {key} 字段比对失败：基准变量({left_label}={left_value}) 与 "
                        f"目标变量({right_label}={right_value}) 无法按数值比较。"
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
                    rule_name=rule_name,
                    location=location,
                    message=(
                        f"字段比对失败：Key {key} 下，基准变量({left_label}={left_value}) "
                        f"{operator_text} 目标变量({right_label}={right_value}) 不成立。"
                    ),
                )
            )

    return abnormal_results

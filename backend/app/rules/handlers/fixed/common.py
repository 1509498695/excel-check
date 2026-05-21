"""固定规则 handler 共用参数、变量读取与展示辅助。"""

from __future__ import annotations

from typing import Any

import pandas as pd

from backend.app.api.fixed_rules_schemas import (
    CompositeCondition,
    CompositeRuleConfig,
    DualCompositeComparison,
    MultiCompositeMappingConfig,
    MultiCompositePipelineConfig,
)
from backend.app.api.schemas import ValidationRule, VariableTag
from backend.app.rules.domain.operators import (
    format_expected_value_set,
    normalize_expected_value_mode,
    parse_expected_value_set,
)
from backend.app.rules.engine_core import RuleExecutionContext


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
    if rule_type != "composite_condition_check" and COMPOSITE_KEY_FIELD in frame.columns:
        frame = frame.loc[frame[COMPOSITE_KEY_FIELD].notna()].copy()
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


def _get_display_field_param(rule: ValidationRule) -> str | None:
    """读取可选结果显示字段。"""
    display_field = rule.params.get("display_field")
    if isinstance(display_field, str) and display_field.strip():
        return display_field.strip()
    return None


def _get_row_display_value(row: pd.Series, display_field: str | None) -> Any:
    """按异常行读取结果显示字段值；未配置或字段不存在时保持空。"""
    if not display_field or display_field not in row.index:
        return None
    return row[display_field]


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


def _get_dual_composite_filters(
    rule: ValidationRule,
    param_name: str,
) -> list[CompositeCondition]:
    """读取双组合变量比对的可选筛选条件。"""
    payload = rule.params.get(param_name, [])
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise ValueError(f"Rule '{rule.rule_type}' requires params.{param_name} to be a list.")

    filters: list[CompositeCondition] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError(f"Rule '{rule.rule_type}' provides invalid params.{param_name}.")
        try:
            condition = CompositeCondition.model_validate(item)
        except Exception as exc:  # pragma: no cover
            raise ValueError(
                f"Rule '{rule.rule_type}' provides invalid {param_name} config: {exc}"
            ) from exc
        if condition.operator not in {
            "eq",
            "ne",
            "gt",
            "lt",
            "not_null",
            "contains",
            "not_contains",
        }:
            raise ValueError(
                f"Rule '{rule.rule_type}' params.{param_name} only supports filter operators."
            )
        filters.append(condition)
    return filters


def _get_dual_key_field(rule: ValidationRule, param_name: str) -> str:
    """读取双组合变量比对的关联 Key 字段，缺省按历史 `__key__` 对齐。"""
    value = rule.params.get(param_name)
    if value is None:
        return COMPOSITE_KEY_FIELD
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Rule '{rule.rule_type}' requires params.{param_name} to be a string.")
    return value.strip()


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

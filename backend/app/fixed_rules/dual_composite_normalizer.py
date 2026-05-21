"""双组合变量比对规则归一化。"""

from __future__ import annotations

from backend.app.api.fixed_rules_schemas import CompositeCondition, DualCompositeComparison, DualCompositeKeyCheckMode
from backend.app.api.schemas import VariableTag
from backend.app.fixed_rules.config_common import (
    COMPOSITE_KEY_FIELD,
    SUPPORTED_COMPOSITE_FILTER_OPERATORS,
    SUPPORTED_DUAL_COMPOSITE_KEY_CHECK_MODES,
    SUPPORTED_DUAL_COMPOSITE_OPERATORS,
    _collect_composite_available_fields,
    _resolve_identifier_against_available,
)
from backend.app.fixed_rules.composite_rule_normalizer import _normalize_composite_conditions


def _normalize_dual_composite_rule(
    *,
    rule_id: str,
    target_variable: VariableTag,
    target_variable_tag: str,
    reference_variable_tag: str,
    key_check_mode: DualCompositeKeyCheckMode | None,
    left_key_field: str | None,
    right_key_field: str | None,
    comparisons: list[DualCompositeComparison],
    left_filters: list[CompositeCondition],
    right_filters: list[CompositeCondition],
    variable_map: dict[str, VariableTag],
) -> tuple[
    str,
    DualCompositeKeyCheckMode,
    str,
    str,
    list[DualCompositeComparison],
    list[CompositeCondition],
    list[CompositeCondition],
]:
    """校验并规范双组合变量比对规则。"""
    if not reference_variable_tag:
        raise ValueError(f"规则 '{rule_id}' 缺少 reference_variable_tag。")
    if reference_variable_tag not in variable_map:
        raise ValueError(
            f"规则 '{rule_id}' 引用了不存在的目标组合变量 '{reference_variable_tag}'。"
        )

    reference_variable = variable_map[reference_variable_tag]
    if (reference_variable.variable_kind or "single") != "composite":
        raise ValueError(
            f"规则 '{rule_id}' 的目标变量 '{reference_variable_tag}' 必须是组合变量。"
        )

    normalized_key_check_mode = str(key_check_mode or "baseline_only").strip()
    if normalized_key_check_mode not in SUPPORTED_DUAL_COMPOSITE_KEY_CHECK_MODES:
        raise ValueError(
            f"规则 '{rule_id}' 的 key_check_mode 仅支持 baseline_only 或 bidirectional。"
        )

    if not comparisons:
        raise ValueError(f"规则 '{rule_id}' 至少需要一条字段比对规则。")

    left_fields = _collect_composite_available_fields(target_variable)
    right_fields = _collect_composite_available_fields(reference_variable)
    normalized_left_key_field = _normalize_dual_key_field(
        rule_id=rule_id,
        field=left_key_field,
        available_fields=left_fields,
        section_label="左侧关联 Key 字段",
    )
    normalized_right_key_field = _normalize_dual_key_field(
        rule_id=rule_id,
        field=right_key_field,
        available_fields=right_fields,
        section_label="右侧关联 Key 字段",
    )
    normalized_left_filters = _normalize_composite_conditions(
        rule_id=rule_id,
        conditions=left_filters,
        section_label="左侧筛选条件",
        available_fields=left_fields,
        allowed_operators=SUPPORTED_COMPOSITE_FILTER_OPERATORS,
    )
    normalized_right_filters = _normalize_composite_conditions(
        rule_id=rule_id,
        conditions=right_filters,
        section_label="右侧筛选条件",
        available_fields=right_fields,
        allowed_operators=SUPPORTED_COMPOSITE_FILTER_OPERATORS,
    )
    if reference_variable_tag == target_variable_tag and (
        not normalized_left_filters or not normalized_right_filters
    ):
        raise ValueError(
            f"规则 '{rule_id}' 同一组合变量进行筛选对比时，左右筛选条件都不能为空。"
        )

    normalized_comparisons: list[DualCompositeComparison] = []
    seen_comparison_ids: set[str] = set()

    for index, comparison in enumerate(comparisons, start=1):
        comparison_id = comparison.comparison_id.strip()
        left_field = comparison.left_field or ""
        operator = str(comparison.operator).strip()
        right_field = comparison.right_field or ""

        if not comparison_id:
            raise ValueError(f"规则 '{rule_id}' 的字段比对 {index} 缺少 comparison_id。")
        if comparison_id in seen_comparison_ids:
            raise ValueError(
                f"规则 '{rule_id}' 的字段比对存在重复 comparison_id '{comparison_id}'。"
            )
        if not left_field.strip():
            raise ValueError(f"规则 '{rule_id}' 的字段比对 {index} 缺少左侧字段。")
        try:
            resolved_left_field = _resolve_identifier_against_available(
                left_field,
                left_fields,
                identifier_label="左侧字段",
                context=f"规则 '{rule_id}' 的字段比对 {index}",
            )
        except ValueError as exc:
            raise ValueError(
                f"规则 '{rule_id}' 的字段比对 {index} 引用了无效的左侧字段 '{left_field}'。"
            ) from exc
        if operator not in SUPPORTED_DUAL_COMPOSITE_OPERATORS:
            raise ValueError(
                f"规则 '{rule_id}' 的字段比对 {index} 使用了不支持的运算符 '{operator}'。"
            )
        if not right_field.strip():
            raise ValueError(f"规则 '{rule_id}' 的字段比对 {index} 缺少右侧字段。")
        try:
            resolved_right_field = _resolve_identifier_against_available(
                right_field,
                right_fields,
                identifier_label="右侧字段",
                context=f"规则 '{rule_id}' 的字段比对 {index}",
            )
        except ValueError as exc:
            raise ValueError(
                f"规则 '{rule_id}' 的字段比对 {index} 引用了无效的右侧字段 '{right_field}'。"
            ) from exc

        normalized_comparisons.append(
            DualCompositeComparison(
                comparison_id=comparison_id,
                left_field=resolved_left_field,
                operator=operator,
                right_field=resolved_right_field,
            )
        )
        seen_comparison_ids.add(comparison_id)

    return (
        reference_variable_tag,
        normalized_key_check_mode,
        normalized_left_key_field,
        normalized_right_key_field,
        normalized_comparisons,
        normalized_left_filters,
        normalized_right_filters,
    )


def _normalize_dual_key_field(
    *,
    rule_id: str,
    field: str | None,
    available_fields: list[str],
    section_label: str,
) -> str:
    """规范跨组变量比对的显式关联 Key 字段，缺省兼容内部 `__key__`。"""
    normalized_field = (field or COMPOSITE_KEY_FIELD).strip() or COMPOSITE_KEY_FIELD
    try:
        return _resolve_identifier_against_available(
            normalized_field,
            available_fields,
            identifier_label=section_label,
            context=f"规则 '{rule_id}'",
        )
    except ValueError as exc:
        raise ValueError(
            f"规则 '{rule_id}' 的{section_label} '{normalized_field}' 不属于对应组合变量。"
        ) from exc

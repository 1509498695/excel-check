"""组合变量规则条件归一化。"""

from __future__ import annotations

import re

from backend.app.api.fixed_rules_schemas import CompositeBranch, CompositeCondition, CompositeRuleConfig
from backend.app.api.schemas import VariableTag
from backend.app.fixed_rules.config_common import (
    COMPARE_STYLE_OPERATORS,
    SET_STYLE_OPERATORS,
    SUPPORTED_COMPOSITE_ASSERTION_OPERATORS,
    SUPPORTED_COMPOSITE_FILTER_OPERATORS,
    _collect_composite_available_fields,
    _normalize_expected_value_mode_for_operator,
    _resolve_identifier_against_available,
)
from backend.app.rules.domain.operators import normalize_expected_value_mode


def _normalize_composite_rule_config(
    *,
    rule_id: str,
    variable: VariableTag,
    composite_config: CompositeRuleConfig | None,
) -> CompositeRuleConfig:
    """????????????????"""
    if composite_config is None:
        raise ValueError(f"???? '{rule_id}' ?? composite_config?")

    available_fields = _collect_composite_available_fields(variable)
    global_filters = _normalize_composite_conditions(
        rule_id=rule_id,
        conditions=composite_config.global_filters,
        section_label="??????",
        available_fields=available_fields,
        allowed_operators=SUPPORTED_COMPOSITE_FILTER_OPERATORS,
    )

    normalized_branches: list[CompositeBranch] = []
    seen_branch_ids: set[str] = set()
    if not composite_config.branches:
        raise ValueError(f"???? '{rule_id}' ???????????")

    for branch_index, branch in enumerate(composite_config.branches, start=1):
        branch_id = branch.branch_id.strip()
        if not branch_id:
            raise ValueError(f"???? '{rule_id}' ????? branch_id?")
        if branch_id in seen_branch_ids:
            raise ValueError(f"???? '{rule_id}' ??? ID ???'{branch_id}'?")
        seen_branch_ids.add(branch_id)

        filters = _normalize_composite_conditions(
            rule_id=rule_id,
            conditions=branch.filters,
            section_label=f"?? {branch_index} ?????",
            available_fields=available_fields,
            allowed_operators=SUPPORTED_COMPOSITE_FILTER_OPERATORS,
        )
        assertions = _normalize_composite_conditions(
            rule_id=rule_id,
            conditions=branch.assertions,
            section_label=f"?? {branch_index} ?????",
            available_fields=available_fields,
            allowed_operators=SUPPORTED_COMPOSITE_ASSERTION_OPERATORS,
        )
        if not assertions:
            raise ValueError(f"???? '{rule_id}' ??? {branch_index} ???????????")

        normalized_branches.append(
            CompositeBranch(
                branch_id=branch_id,
                filters=filters,
                assertions=assertions,
            )
        )

    return CompositeRuleConfig(
        global_filters=global_filters,
        branches=normalized_branches,
    )


def _normalize_composite_conditions(
    *,
    rule_id: str,
    conditions: list[CompositeCondition],
    section_label: str,
    available_fields: list[str],
    allowed_operators: set[str],
) -> list[CompositeCondition]:
    """????????????????"""
    normalized_conditions: list[CompositeCondition] = []
    seen_condition_ids: set[str] = set()

    for condition in conditions:
        condition_id = condition.condition_id.strip()
        field = condition.field or ""
        operator = str(condition.operator).strip()
        value_source = condition.value_source
        expected_value = condition.expected_value.strip() if condition.expected_value else ""
        expected_value_mode = condition.expected_value_mode
        expected_field = condition.expected_field or ""

        if not condition_id:
            raise ValueError(f"???? '{rule_id}' ?{section_label}???? condition_id ????")
        if condition_id in seen_condition_ids:
            raise ValueError(
                f"???? '{rule_id}' ?{section_label}???? condition_id?'{condition_id}'?"
            )
        if not field.strip():
            raise ValueError(f"???? '{rule_id}' ?{section_label}??????????")
        try:
            resolved_field = _resolve_identifier_against_available(
                field,
                available_fields,
                identifier_label="字段",
                context=f"规则 '{rule_id}' 的{section_label}",
            )
        except ValueError as exc:
            raise ValueError(
                f"???? '{rule_id}' ?{section_label}????????? '{field}'?"
            ) from exc
        if operator not in allowed_operators:
            raise ValueError(
                f"???? '{rule_id}' ?{section_label}?????????? '{operator}'?"
            )

        normalized_value_source: str | None = None
        normalized_expected_value: str | None = None
        normalized_expected_value_mode: str | None = None
        normalized_expected_field: str | None = None

        if operator in COMPARE_STYLE_OPERATORS:
            normalized_value_source = value_source or "literal"
            if normalized_value_source == "literal":
                if not expected_value:
                    raise ValueError(f"???? '{rule_id}' ?{section_label}??????")
                if operator in {"gt", "lt"}:
                    try:
                        float(expected_value)
                    except ValueError as exc:
                        raise ValueError(
                            f"???? '{rule_id}' ?{section_label}? '{operator}' ????????????"
                        ) from exc
                normalized_expected_value_mode = _normalize_expected_value_mode_for_operator(
                    operator=operator,
                    expected_value=expected_value,
                    expected_value_mode=expected_value_mode,
                    context=f"规则 '{rule_id}' 的{section_label}",
                )
                normalized_expected_value = expected_value
            elif normalized_value_source == "field":
                if normalize_expected_value_mode(expected_value_mode) == "set":
                    raise ValueError(
                        f"规则 '{rule_id}' 的{section_label}字段对比不支持规则集比较值。"
                    )
                if not expected_field.strip():
                    raise ValueError(f"???? '{rule_id}' ?{section_label}?????????")
                try:
                    resolved_expected_field = _resolve_identifier_against_available(
                        expected_field,
                        available_fields,
                        identifier_label="右侧字段",
                        context=f"规则 '{rule_id}' 的{section_label}",
                    )
                except ValueError as exc:
                    raise ValueError(
                        f"???? '{rule_id}' ?{section_label}??????????? '{expected_field}'?"
                    ) from exc
                normalized_expected_field = resolved_expected_field
            else:
                raise ValueError(
                    f"???? '{rule_id}' ?{section_label}??????? value_source '{value_source}'?"
                )
        elif operator in {"contains", "not_contains"}:
            normalized_value_source = "literal"
            if value_source == "field":
                raise ValueError(
                    f"规则 '{rule_id}' 的{section_label}操作符 '{operator}' 只支持固定值。"
                )
            if not expected_value:
                raise ValueError(f"规则 '{rule_id}' 的{section_label}缺少比较值。")
            if expected_field:
                raise ValueError(
                    f"规则 '{rule_id}' 的{section_label}操作符 '{operator}' 不支持右侧字段。"
                )
            normalized_expected_value = expected_value
        elif operator == "not_null":
            normalized_value_source = None
            if value_source or expected_value or expected_field:
                raise ValueError(
                    f"???? '{rule_id}' ?{section_label}? 'not_null' ????????????"
                )
        elif operator == "regex":
            normalized_value_source = None
            if value_source:
                raise ValueError(
                    f"规则 '{rule_id}' 的{section_label}操作符 'regex' 不支持右值来源。"
                )
            if not expected_value:
                raise ValueError(f"规则 '{rule_id}' 的{section_label}缺少正则表达式。")
            if expected_field:
                raise ValueError(
                    f"规则 '{rule_id}' 的{section_label}操作符 'regex' 不支持右侧字段。"
                )
            try:
                re.compile(expected_value)
            except re.error as exc:
                raise ValueError(
                    f"规则 '{rule_id}' 的{section_label}正则表达式无效：{expected_value}"
                ) from exc
            normalized_expected_value = expected_value
        elif operator in SET_STYLE_OPERATORS:
            if value_source or expected_value or expected_field:
                raise ValueError(
                    f"???? '{rule_id}' ?{section_label}? '{operator}' ????????????"
                )
        else:
            raise ValueError(
                f"???? '{rule_id}' ?{section_label}?????????? '{operator}'?"
            )

        normalized_conditions.append(
            CompositeCondition(
                condition_id=condition_id,
                field=resolved_field,
                operator=operator,
                value_source=normalized_value_source,
                expected_value=normalized_expected_value,
                expected_value_mode=normalized_expected_value_mode,
                expected_field=normalized_expected_field,
            )
        )
        seen_condition_ids.add(condition_id)

    return normalized_conditions

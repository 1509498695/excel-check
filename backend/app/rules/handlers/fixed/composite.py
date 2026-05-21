"""组合变量条件分支规则 handler。"""

from __future__ import annotations

from typing import Any

from backend.app.api.schemas import ValidationRule
from backend.app.rules.engine_core import RuleExecutionContext, register_rule
from backend.app.rules.handlers.fixed.common import (
    _get_composite_rule_config,
    _get_composite_variable_frame,
    _get_display_field_param,
    _get_fixed_rule_param,
)
from backend.app.rules.handlers.fixed.condition_eval import (
    _apply_composite_filters,
    _evaluate_composite_branch_assertions,
)
from backend.app.rules.infrastructure.tag_extractor import by_target_tag


@register_rule("composite_condition_check", dependent_tags=by_target_tag)
def check_composite_condition_check(
    rule: ValidationRule,
    context: RuleExecutionContext,
) -> list[dict[str, Any]]:
    """执行组合变量条件分支校验。"""
    target_tag = _get_fixed_rule_param(rule, "target_tag")
    rule_name = _get_fixed_rule_param(rule, "rule_name")
    display_field = _get_display_field_param(rule)
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
                display_field=display_field,
            )
        )

    return abnormal_results

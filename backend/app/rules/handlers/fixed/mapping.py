"""多组合变量映射校验 handler。"""

from __future__ import annotations

from typing import Any

from backend.app.api.schemas import ValidationRule
from backend.app.rules.engine_core import RuleExecutionContext, register_rule
from backend.app.rules.handlers.fixed.common import (
    _get_composite_variable_frame,
    _get_fixed_rule_param,
    _get_multi_composite_mapping_config,
)
from backend.app.rules.handlers.fixed.condition_eval import _evaluate_mapping_filter_check
from backend.app.rules.infrastructure.tag_extractor import by_mapping_node_tags


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
                    display_field=node.display_field,
                )
            )

    return abnormal_results

"""多组合变量串行校验 handler。"""

from __future__ import annotations

from typing import Any

from backend.app.api.schemas import ValidationRule
from backend.app.rules.engine_core import RuleExecutionContext, register_rule
from backend.app.rules.handlers.fixed.common import (
    _get_composite_variable_frame,
    _get_fixed_rule_param,
    _get_multi_composite_pipeline_config,
)
from backend.app.rules.handlers.fixed.condition_eval import (
    _apply_composite_filters,
    _evaluate_pipeline_node_assertions,
)
from backend.app.rules.infrastructure.tag_extractor import by_pipeline_node_tags


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
            display_field=node.display_field,
        )
        if node_abnormal_results:
            return node_abnormal_results

    return []

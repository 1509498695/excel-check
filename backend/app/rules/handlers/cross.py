"""跨表规则实现。"""

from __future__ import annotations

from typing import Any

from backend.app.api.schemas import ValidationRule
from backend.app.rules.domain.result import build_basic_result
from backend.app.rules.domain.value import (
    get_business_column_name,
    get_variable_frame,
    is_empty_value,
)
from backend.app.rules.engine_core import (
    RuleExecutionContext,
    register_rule,
)
from backend.app.rules.infrastructure.tag_extractor import by_dict_and_target_tag


@register_rule("cross_table_mapping", dependent_tags=by_dict_and_target_tag)
def check_cross_table_mapping(
    rule: ValidationRule, context: RuleExecutionContext
) -> list[dict[str, Any]]:
    """校验目标列中的值是否存在于基础字典列中。"""
    dict_tag, target_tag = by_dict_and_target_tag(rule)

    dict_frame = get_variable_frame(context, dict_tag, rule.rule_type)
    target_frame = get_variable_frame(context, target_tag, rule.rule_type)

    dict_column = get_business_column_name(dict_frame, dict_tag)
    target_column = get_business_column_name(target_frame, target_tag)

    dict_series = dict_frame[dict_column]
    target_series = target_frame[target_column]

    valid_dict_values = {
        value for value in dict_series.tolist() if not is_empty_value(value)
    }
    non_empty_target_mask = ~target_series.apply(is_empty_value)
    missing_mapping_mask = ~target_series.isin(valid_dict_values) & non_empty_target_mask

    abnormal_results: list[dict[str, Any]] = []
    for _, row in target_frame.loc[
        missing_mapping_mask, [target_column, "_row_index"]
    ].iterrows():
        abnormal_results.append(
            build_basic_result(
                level="error",
                rule_name=rule.rule_type,
                tag=target_tag,
                column_name=target_column,
                row_index=row["_row_index"],
                raw_value=row[target_column],
                message="在基础字典中未命中该映射值。",
            )
        )

    return abnormal_results

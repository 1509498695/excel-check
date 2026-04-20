"""5 种 rule_type 的依赖 tag 提取器。

每个 ``rule_type`` 在注册时通过 ``register_rule(..., dependent_tags=...)`` 显式
绑定一个提取器，供 ``execute_api._filter_executable_rules`` 在加载阶段统一
判定「规则依赖的 source 是否已成功加载」。

异常文案逐字保留与原 ``execute_api._extract_rule_tags`` 一致，避免破坏现有
基线测试与 baseline 快照。
"""

from __future__ import annotations

from collections.abc import Callable

from backend.app.api.schemas import ValidationRule


TagExtractor = Callable[[ValidationRule], list[str]]


def by_target_tags(rule: ValidationRule) -> list[str]:
    """``not_null`` / ``unique``：从 ``params.target_tags`` 中提取多 tag。"""
    target_tags = rule.params.get("target_tags")
    if not isinstance(target_tags, list) or not target_tags:
        raise ValueError(
            f"Rule '{rule.rule_type}' requires non-empty params.target_tags."
        )
    if not all(isinstance(tag, str) and tag for tag in target_tags):
        raise ValueError(
            f"Rule '{rule.rule_type}' requires params.target_tags to be a string list."
        )
    return target_tags


def by_dict_and_target_tag(rule: ValidationRule) -> list[str]:
    """``cross_table_mapping``：从 ``params.dict_tag`` / ``target_tag`` 中提取双 tag。"""
    dict_tag = rule.params.get("dict_tag")
    target_tag = rule.params.get("target_tag")
    if not isinstance(dict_tag, str) or not dict_tag:
        raise ValueError("Rule 'cross_table_mapping' requires params.dict_tag.")
    if not isinstance(target_tag, str) or not target_tag:
        raise ValueError("Rule 'cross_table_mapping' requires params.target_tag.")
    return [dict_tag, target_tag]


def by_target_tag(rule: ValidationRule) -> list[str]:
    """``fixed_value_compare`` / ``composite_condition_check``：单 tag 提取。

    文案与原 ``fixed_value_compare`` 在 ``execute_api._extract_rule_tags`` 中的硬编码
    版本完全一致；同时也与 ``composite_condition_check`` handler 内部
    ``_get_fixed_rule_param`` 抛出的文案一致，避免重复触发同义异常时出现差异。
    """
    target_tag = rule.params.get("target_tag")
    if not isinstance(target_tag, str) or not target_tag:
        raise ValueError(f"Rule '{rule.rule_type}' requires params.target_tag.")
    return [target_tag]


def no_tags(rule: ValidationRule) -> list[str]:
    """占位规则（如 ``regex``）：当前不依赖任何变量 tag。"""
    return []

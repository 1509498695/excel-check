"""规则引擎注册与执行入口。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pandas as pd

from backend.app.api.schemas import TaskTree, ValidationRule


RuleResult = list[dict[str, Any]]


@dataclass(frozen=True)
class RuleExecutionContext:
    """规则执行上下文，封装任务树和已加载变量切片。"""

    task_tree: TaskTree
    loaded_variables: dict[str, pd.DataFrame]


RuleHandler = Callable[[ValidationRule, RuleExecutionContext], RuleResult]
RULE_REGISTRY: dict[str, RuleHandler] = {}


def register_rule(rule_type: str) -> Callable[[RuleHandler], RuleHandler]:
    """注册规则处理器，供执行阶段按 `rule_type` 查找。"""

    def decorator(func: RuleHandler) -> RuleHandler:
        RULE_REGISTRY[rule_type] = func
        return func

    return decorator


def execute_rules(
    task_tree: TaskTree, loaded_variables: dict[str, pd.DataFrame]
) -> RuleResult:
    """按规则顺序执行已注册处理器并汇总统一异常结构。"""
    abnormal_results: RuleResult = []
    context = RuleExecutionContext(
        task_tree=task_tree,
        loaded_variables=loaded_variables,
    )

    for rule in task_tree.rules:
        handler = RULE_REGISTRY.get(rule.rule_type)
        if handler is None:
            raise ValueError(f"Unsupported rule_type: '{rule.rule_type}'.")
        result = handler(rule, context)
        if result:
            abnormal_results.extend(result)

    return abnormal_results


from backend.app.rules import rule_basics, rule_cross  # noqa: E402,F401

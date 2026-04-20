"""规则引擎注册与执行入口。

本模块对外暴露三个稳定符号：

- :data:`RULE_REGISTRY`：``rule_type -> RuleSpec`` 注册表
- :func:`register_rule`：装饰器，向 ``RULE_REGISTRY`` 注册 handler 与依赖 tag 提取器
- :func:`execute_rules`：按 :class:`TaskTree` 顺序执行规则并汇总异常结果

注册表条目升级为 :class:`RuleSpec`（``handler`` + ``dependent_tags``），让
``execute_api._extract_rule_tags`` 不再维护 if/elif 长链，直接调用注册表里
登记好的 ``dependent_tags`` 提取器，与 handler 真实依赖保持一致。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pandas as pd

from backend.app.api.schemas import TaskTree, ValidationRule
from backend.app.rules.infrastructure.tag_extractor import TagExtractor


RuleResult = list[dict[str, Any]]


@dataclass(frozen=True)
class RuleExecutionContext:
    """规则执行上下文，封装任务树和已加载变量切片。"""

    task_tree: TaskTree
    loaded_variables: dict[str, pd.DataFrame]


RuleHandler = Callable[[ValidationRule, RuleExecutionContext], RuleResult]


@dataclass(frozen=True)
class RuleSpec:
    """注册表条目：handler 与依赖 tag 提取器一一对应。"""

    handler: RuleHandler
    dependent_tags: TagExtractor


RULE_REGISTRY: dict[str, RuleSpec] = {}


def register_rule(
    rule_type: str, *, dependent_tags: TagExtractor
) -> Callable[[RuleHandler], RuleHandler]:
    """注册规则处理器，供执行阶段按 ``rule_type`` 查找。

    新签名要求显式传入 ``dependent_tags``，与 handler 真实依赖一一对应；
    旧的 ``register_rule(rule_type)`` 写法已不再支持，仓库内只有自家
    handler 在用，故一次性切换。
    """

    def decorator(func: RuleHandler) -> RuleHandler:
        RULE_REGISTRY[rule_type] = RuleSpec(
            handler=func,
            dependent_tags=dependent_tags,
        )
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
        spec = RULE_REGISTRY.get(rule.rule_type)
        if spec is None:
            raise ValueError(f"Unsupported rule_type: '{rule.rule_type}'.")
        result = spec.handler(rule, context)
        if result:
            abnormal_results.extend(result)

    return abnormal_results


from backend.app.rules import handlers  # noqa: E402,F401

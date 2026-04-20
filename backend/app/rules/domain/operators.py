"""eq / ne / gt / lt / not_null 在筛选与断言两种语义下的统一判定。

筛选语义（用于组合变量的 ``global_filters`` / ``branch.filters``）：
返回 bool，True 表示行命中条件应保留。

断言语义（用于固定规则单列比较与组合变量分支断言）：
返回 :class:`CompareAssertionResult`，区分 ``failed``（命中异常需上报）
与 ``incomparable``（gt/lt 模式下无法转数字，需要走「无法按数值比较」报错路径）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.app.rules.domain.value import (
    is_empty_value,
    normalize_fixed_text,
    to_number,
)


COMPARE_OPERATORS = {"eq", "ne", "gt", "lt"}
SET_STYLE_OPERATORS = {"unique", "duplicate_required"}


@dataclass(frozen=True)
class CompareAssertionResult:
    """eq / ne / gt / lt 在断言语义下的判定结果。"""

    failed: bool
    incomparable: bool = False


def matches_compare_filter(
    *,
    actual_value: Any,
    operator: str,
    expected_value: Any,
) -> bool:
    """筛选语义：True 表示行命中条件，应保留。

    与原 ``rule_fixed._matches_compare_filter`` 行为完全一致：
    - eq/ne 走文本归一化后的相等比较
    - gt/lt 走数值比较；任一侧无法转数字时直接返回 False（行被剔除）
    """
    if operator in {"eq", "ne"}:
        actual_text = normalize_fixed_text(actual_value)
        expected_text = normalize_fixed_text(expected_value)
        is_match = actual_text == expected_text
        return is_match if operator == "eq" else not is_match

    actual_number = to_number(actual_value)
    expected_number = to_number(expected_value)
    if actual_number is None or expected_number is None:
        return False
    return actual_number > expected_number if operator == "gt" else actual_number < expected_number


def evaluate_compare_assertion(
    *,
    actual_value: Any,
    operator: str,
    expected_value: Any,
) -> CompareAssertionResult:
    """断言语义：返回 ``failed`` / ``incomparable``。

    与原 ``rule_fixed._evaluate_row_assertion`` 中 eq/ne 与 gt/lt 分支语义一致：
    - eq/ne：文本归一化后比较；不一致 → ``failed=True``
    - gt/lt：任一侧无法转数字 → ``incomparable=True``（上报「无法按数值比较」）；
      数值化成功后按 ``<= / >=`` 判定 ``failed``
    """
    if operator in {"eq", "ne"}:
        actual_text = normalize_fixed_text(actual_value)
        expected_text = normalize_fixed_text(expected_value)
        is_match = actual_text == expected_text
        failed = not is_match if operator == "eq" else is_match
        return CompareAssertionResult(failed=failed)

    actual_number = to_number(actual_value)
    expected_number = to_number(expected_value)
    if actual_number is None or expected_number is None:
        return CompareAssertionResult(failed=False, incomparable=True)

    failed = (
        actual_number <= expected_number
        if operator == "gt"
        else actual_number >= expected_number
    )
    return CompareAssertionResult(failed=failed)


def matches_not_null_filter(value: Any) -> bool:
    """筛选语义：True 表示值非空，行应保留。"""
    return not is_empty_value(value)


def is_not_null_violation(value: Any) -> bool:
    """断言语义：True 表示空值需要报告。"""
    return is_empty_value(value)

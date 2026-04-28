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
EXPECTED_VALUE_MODES = {"single", "set"}


@dataclass(frozen=True)
class CompareAssertionResult:
    """eq / ne / gt / lt 在断言语义下的判定结果。"""

    failed: bool
    incomparable: bool = False


def normalize_expected_value_mode(value: Any) -> str:
    """缺省按单固定值处理，仅显式 set 启用逗号规则集。"""
    if value is None:
        return "single"
    normalized = str(value).strip()
    if not normalized:
        return "single"
    if normalized not in EXPECTED_VALUE_MODES:
        raise ValueError("expected_value_mode must be 'single' or 'set'.")
    return normalized


def parse_expected_value_set(expected_value: Any) -> list[str]:
    """把英文逗号分隔的规则集解析为归一化文本列表。"""
    values: list[str] = []
    for item in str(expected_value).split(","):
        normalized = normalize_fixed_text(item)
        if normalized:
            values.append(normalized)
    if not values:
        raise ValueError("expected_value set must contain at least one value.")
    return values


def format_expected_value_set(expected_values: list[str]) -> str:
    """规则集在异常信息中的展示文本。"""
    return ", ".join(expected_values)


def matches_expected_text(
    *,
    actual_value: Any,
    expected_value: Any,
    expected_value_mode: Any = None,
) -> bool:
    """eq/ne 共用的文本比较；set 模式命中任一值即视为匹配。"""
    actual_text = normalize_fixed_text(actual_value)
    mode = normalize_expected_value_mode(expected_value_mode)
    if mode == "set":
        return actual_text in parse_expected_value_set(expected_value)

    expected_text = normalize_fixed_text(expected_value)
    return actual_text == expected_text


def matches_compare_filter(
    *,
    actual_value: Any,
    operator: str,
    expected_value: Any,
    expected_value_mode: Any = None,
) -> bool:
    """筛选语义：True 表示行命中条件，应保留。

    与原 ``rule_fixed._matches_compare_filter`` 行为完全一致：
    - eq/ne 走文本归一化后的相等比较
    - gt/lt 走数值比较；任一侧无法转数字时直接返回 False（行被剔除）
    """
    mode = normalize_expected_value_mode(expected_value_mode)
    if mode == "set" and operator not in {"eq", "ne"}:
        raise ValueError("expected_value_mode='set' only supports eq/ne operators.")

    if operator in {"eq", "ne"}:
        is_match = matches_expected_text(
            actual_value=actual_value,
            expected_value=expected_value,
            expected_value_mode=mode,
        )
        return is_match if operator == "eq" else not is_match

    actual_number = to_number(actual_value)
    expected_number = to_number(expected_value)
    if actual_number is None or expected_number is None:
        return False
    return actual_number > expected_number if operator == "gt" else actual_number < expected_number


def matches_contains_filter(
    *,
    actual_value: Any,
    expected_value: Any,
) -> bool:
    """筛选语义：True 表示左侧文本包含右侧片段。"""
    if is_empty_value(actual_value):
        return False

    actual_text = str(actual_value).strip()
    expected_text = str(expected_value).strip()
    if not expected_text:
        return False
    return expected_text in actual_text


def matches_not_contains_filter(
    *,
    actual_value: Any,
    expected_value: Any,
) -> bool:
    """筛选语义：True 表示左侧文本不包含右侧片段。"""
    if is_empty_value(actual_value):
        return False

    actual_text = str(actual_value).strip()
    expected_text = str(expected_value).strip()
    if not expected_text:
        return False
    return expected_text not in actual_text


def evaluate_compare_assertion(
    *,
    actual_value: Any,
    operator: str,
    expected_value: Any,
    expected_value_mode: Any = None,
) -> CompareAssertionResult:
    """断言语义：返回 ``failed`` / ``incomparable``。

    与原 ``rule_fixed._evaluate_row_assertion`` 中 eq/ne 与 gt/lt 分支语义一致：
    - eq/ne：文本归一化后比较；不一致 → ``failed=True``
    - gt/lt：任一侧无法转数字 → ``incomparable=True``（上报「无法按数值比较」）；
      数值化成功后按 ``<= / >=`` 判定 ``failed``
    """
    mode = normalize_expected_value_mode(expected_value_mode)
    if mode == "set" and operator not in {"eq", "ne"}:
        raise ValueError("expected_value_mode='set' only supports eq/ne operators.")

    if operator in {"eq", "ne"}:
        is_match = matches_expected_text(
            actual_value=actual_value,
            expected_value=expected_value,
            expected_value_mode=mode,
        )
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

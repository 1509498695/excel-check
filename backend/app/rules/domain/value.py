"""值层规范化工具与变量数据切片读取。

本模块汇集原 ``rule_basics`` / ``rule_fixed`` 中的私有 helper，统一为下划线
命名的内部 API：

- 文本与数值的规范化：``normalize_text`` / ``normalize_fixed_text`` / ``to_number``
- 空判断与 numpy 标量降级：``is_empty_value`` / ``unwrap_scalar``
- 变量切片与列名解析：``get_variable_frame`` / ``get_business_column_name``

所有函数行为与原版 1:1 一致，包括异常文案；仅做物理位置整合，不引入新行为。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from backend.app.rules.engine_core import RuleExecutionContext


def normalize_text(value: Any) -> Any:
    """对字符串去首尾空白；非字符串原样返回。"""
    if isinstance(value, str):
        return value.strip()
    return value


def is_empty_value(value: Any) -> bool:
    """判断单元格是否为空：``NaN`` / ``None`` / 仅空白字符串都视为空。"""
    normalized = normalize_text(value)
    if pd.isna(normalized):
        return True
    return normalized == ""


def normalize_fixed_text(value: Any) -> str | None:
    """把单元格内容标准化为可比较的文本。

    与 :func:`normalize_text` 的区别：本函数会把非字符串、非 NaN 的值
    强转为 ``str``，便于固定规则做基于字符串的相等比较。
    """
    if pd.isna(value):
        return None
    if isinstance(value, str):
        return value.strip()
    return str(value)


def to_number(value: Any) -> float | None:
    """尝试把值转成 ``float``，失败时返回 ``None``。"""
    normalized = normalize_fixed_text(value)
    if normalized in {None, ""}:
        return None
    try:
        return float(normalized)
    except ValueError:
        return None


def unwrap_scalar(value: Any) -> Any:
    """把 numpy / pandas 标量降级为 Python 原生类型，便于 JSON 序列化。"""
    if hasattr(value, "item"):
        return value.item()
    return value


def get_variable_frame(
    context: "RuleExecutionContext",
    tag: str,
    rule_type: str,
) -> pd.DataFrame:
    """按 tag 取出已加载的单变量数据切片，组合变量直接拒绝。

    与原 ``rule_basics._get_variable_frame`` 行为完全一致：
    - 命中 composite 变量 → 抛出中文异常 ``规则 '<rule_type>' 仅支持单个变量...``
    - tag 未加载 → 抛出英文异常 ``Rule '<rule_type>' references unknown tag...``
    """
    variable = next(
        (item for item in context.task_tree.variables if item.tag == tag),
        None,
    )
    if variable is not None and variable.variable_kind == "composite":
        raise ValueError(
            f"规则 '{rule_type}' 仅支持单个变量，不支持组合变量 '{tag}'。"
        )

    frame = context.loaded_variables.get(tag)
    if frame is None:
        raise ValueError(f"Rule '{rule_type}' references unknown tag '{tag}'.")
    return frame


def get_business_column_name(frame: pd.DataFrame, tag: str) -> str:
    """从单变量切片中取出唯一的业务列名（排除内部 ``_row_index``）。"""
    business_columns = [column for column in frame.columns if column != "_row_index"]
    if len(business_columns) != 1:
        raise ValueError(
            f"Tag '{tag}' must map to exactly one business column, got {business_columns}."
        )
    return business_columns[0]

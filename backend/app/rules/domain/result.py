"""统一的异常结果值对象与构造工具。

本模块封装原 ``rule_basics._build_abnormal_result`` 与
``rule_fixed._build_fixed_rule_result`` 两份构造逻辑，统一对外 dict 形态：
``{level, rule_name, location, row_index, raw_value, message}``。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.app.rules.domain.value import unwrap_scalar


@dataclass(frozen=True)
class AbnormalResult:
    """统一异常结果值对象，对应每条 ``data.abnormal_results`` 元素。"""

    level: str
    rule_name: str
    location: str
    row_index: int
    raw_value: Any
    message: str

    def to_dict(self) -> dict[str, Any]:
        """导出为与历史接口字节级兼容的 dict。"""
        return {
            "level": self.level,
            "rule_name": self.rule_name,
            "location": self.location,
            "row_index": int(self.row_index),
            "raw_value": self.raw_value,
            "message": self.message,
        }


def build_basic_result(
    *,
    level: str,
    rule_name: str,
    tag: str,
    column_name: str,
    row_index: int,
    raw_value: Any,
    message: str,
    location: str | None = None,
) -> dict[str, Any]:
    """对应原 ``rule_basics._build_abnormal_result``。

    ``location`` 优先使用规则注入值，否则回落到 ``f"{tag} -> {column_name}"``。
    ``raw_value`` 自动通过 :func:`unwrap_scalar` 降级。
    """
    return AbnormalResult(
        level=level,
        rule_name=rule_name,
        location=location or f"{tag} -> {column_name}",
        row_index=int(row_index),
        raw_value=unwrap_scalar(raw_value),
        message=message,
    ).to_dict()


def build_fixed_result(
    *,
    rule_name: str,
    location: str,
    row_index: int,
    raw_value: Any,
    message: str,
    level: str = "error",
) -> dict[str, Any]:
    """对应原 ``rule_fixed._build_fixed_rule_result``。

    与 :func:`build_basic_result` 的区别：``location`` 必须显式传入；
    ``level`` 默认为 ``"error"``，符合固定规则模块的约定。
    """
    return AbnormalResult(
        level=level,
        rule_name=rule_name,
        location=location,
        row_index=int(row_index),
        raw_value=unwrap_scalar(raw_value),
        message=message,
    ).to_dict()

"""基础规则兼容入口。

基础固定规则的真实实现已迁移到 ``backend.app.rules.handlers.fixed.basic``，
保留本模块避免旧 import 路径失效。
"""

from __future__ import annotations

from backend.app.rules.handlers.fixed.basic import (  # noqa: F401
    check_not_null,
    check_regex,
    check_unique,
)

__all__ = ["check_not_null", "check_unique", "check_regex"]

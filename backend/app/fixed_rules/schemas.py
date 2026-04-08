"""固定规则模块配置模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


UNGROUPED_GROUP_ID = "ungrouped"
UNGROUPED_GROUP_NAME = "未分组"


def create_default_group() -> "FixedRuleGroup":
    """返回系统内置的默认规则组。"""
    return FixedRuleGroup(
        group_id=UNGROUPED_GROUP_ID,
        group_name=UNGROUPED_GROUP_NAME,
        builtin=True,
    )


class FixedRuleGroup(BaseModel):
    """描述单个固定规则组。"""

    model_config = ConfigDict(extra="forbid")

    group_id: str
    group_name: str
    builtin: bool = False


class FixedRuleItem(BaseModel):
    """描述单条固定规则。"""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    group_id: str = UNGROUPED_GROUP_ID
    rule_name: str
    column: str
    operator: Literal["eq", "ne", "gt", "lt"]
    expected_value: str = ""


class FixedRulesConfig(BaseModel):
    """描述固定规则模块的完整持久化配置。"""

    model_config = ConfigDict(extra="forbid")

    version: int = 1
    configured: bool = False
    file_path: str = ""
    sheet: str = ""
    columns: list[str] = Field(default_factory=list)
    svn_enabled: bool = False
    groups: list[FixedRuleGroup] = Field(default_factory=lambda: [create_default_group()])
    rules: list[FixedRuleItem] = Field(default_factory=list)

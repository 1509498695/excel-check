"""固定规则模块接口模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


FixedRuleType = Literal["fixed_value_compare", "not_null", "unique"]
FixedRuleOperator = Literal["eq", "ne", "gt", "lt"]


UNGROUPED_GROUP_ID = "ungrouped"
UNGROUPED_GROUP_NAME = "未分组"


class FixedRuleBinding(BaseModel):
    """描述单条固定规则绑定的文件位置与目标列。"""

    model_config = ConfigDict(extra="forbid")

    file_path: str
    sheet: str
    column: str


class FixedRuleGroup(BaseModel):
    """描述一组固定规则的分组信息。"""

    model_config = ConfigDict(extra="forbid")

    group_id: str
    group_name: str
    builtin: bool = False


class FixedRuleDefinition(BaseModel):
    """描述一条固定规则。"""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    group_id: str
    rule_name: str
    binding: FixedRuleBinding
    rule_type: FixedRuleType = "fixed_value_compare"
    operator: FixedRuleOperator | None = None
    expected_value: str | None = None


class FixedRulesConfig(BaseModel):
    """描述固定规则模块的整份持久化配置。"""

    model_config = ConfigDict(extra="forbid")

    version: int = 3
    configured: bool = False
    groups: list[FixedRuleGroup] = Field(default_factory=list)
    rules: list[FixedRuleDefinition] = Field(default_factory=list)

"""固定规则模块接口模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.api.schemas import DataSource, VariableTag


FixedRuleType = Literal[
    "fixed_value_compare",
    "regex_check",
    "not_null",
    "unique",
    "sequence_order_check",
    "cross_table_mapping",
    "composite_condition_check",
    "dual_composite_compare",
]
FixedRuleOperator = Literal["eq", "ne", "gt", "lt"]
SequenceDirection = Literal["asc", "desc"]
SequenceStartMode = Literal["auto", "manual"]
CompositeFilterOperator = Literal[
    "eq",
    "ne",
    "gt",
    "lt",
    "not_null",
    "contains",
    "not_contains",
]
CompositeAssertionOperator = Literal[
    "eq",
    "ne",
    "gt",
    "lt",
    "not_null",
    "regex",
    "unique",
    "duplicate_required",
]
CompositeValueSource = Literal["literal", "field"]
DualCompositeKeyCheckMode = Literal["baseline_only", "bidirectional"]
DualCompositeOperator = Literal["eq", "ne", "gt", "lt", "not_null"]
FixedRulesConfigIssueLevel = Literal["warning", "error"]


UNGROUPED_GROUP_ID = "ungrouped"
UNGROUPED_GROUP_NAME = "未分组"


class FixedRuleBinding(BaseModel):
    """兼容旧版固定规则配置中的文件级绑定结构。"""

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


class CompositeCondition(BaseModel):
    """描述组合变量条件分支校验中的单条条件。"""

    model_config = ConfigDict(extra="forbid")

    condition_id: str
    field: str
    operator: CompositeFilterOperator | CompositeAssertionOperator
    value_source: CompositeValueSource | None = None
    expected_value: str | None = None
    expected_field: str | None = None


class CompositeBranch(BaseModel):
    """描述组合变量规则中的单个条件分支。"""

    model_config = ConfigDict(extra="forbid")

    branch_id: str
    filters: list[CompositeCondition] = Field(default_factory=list)
    assertions: list[CompositeCondition] = Field(default_factory=list)


class CompositeRuleConfig(BaseModel):
    """描述组合变量条件分支校验的完整配置。"""

    model_config = ConfigDict(extra="forbid")

    global_filters: list[CompositeCondition] = Field(default_factory=list)
    branches: list[CompositeBranch] = Field(default_factory=list)


class DualCompositeComparison(BaseModel):
    """描述双组合变量比对中的单条字段比较规则。"""

    model_config = ConfigDict(extra="forbid")

    comparison_id: str
    left_field: str
    operator: DualCompositeOperator
    right_field: str


class FixedRuleDefinition(BaseModel):
    """描述一条固定规则定义。"""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    group_id: str
    rule_name: str
    target_variable_tag: str | None = None
    binding: FixedRuleBinding | None = None
    rule_type: FixedRuleType = "fixed_value_compare"
    operator: FixedRuleOperator | None = None
    expected_value: str | None = None
    reference_variable_tag: str | None = None
    sequence_direction: SequenceDirection | None = None
    sequence_step: str | None = None
    sequence_start_mode: SequenceStartMode | None = None
    sequence_start_value: str | None = None
    composite_config: CompositeRuleConfig | None = None
    key_check_mode: DualCompositeKeyCheckMode | None = None
    comparisons: list[DualCompositeComparison] = Field(default_factory=list)


class FixedRulesConfigIssue(BaseModel):
    """描述固定规则配置中可修复、但不阻断页面读取的问题。"""

    model_config = ConfigDict(extra="forbid")

    level: FixedRulesConfigIssueLevel = "warning"
    source_id: str | None = None
    variable_tag: str | None = None
    rule_id: str | None = None
    message: str


class FixedRulesConfig(BaseModel):
    """描述固定规则页的完整持久化配置。"""

    model_config = ConfigDict(extra="forbid")

    version: int = 5
    configured: bool = False
    sources: list[DataSource] = Field(default_factory=list)
    variables: list[VariableTag] = Field(default_factory=list)
    groups: list[FixedRuleGroup] = Field(default_factory=list)
    rules: list[FixedRuleDefinition] = Field(default_factory=list)
    path_replacement_presets: list[str] = Field(default_factory=list)
    selected_path_replacement_preset: str | None = None


class FixedRulesExecuteRequest(BaseModel):
    """描述固定规则执行时允许传入的可选规则筛选参数。"""

    model_config = ConfigDict(extra="forbid")

    selected_rule_ids: list[str] | None = None
    page: int | None = Field(default=None, ge=1)
    size: int | None = Field(default=None, ge=1, le=200)

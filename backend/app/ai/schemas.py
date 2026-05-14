"""AI 规则助手接口与内部草稿模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.api.fixed_rules_schemas import (
    CompositeRuleConfig,
    DualCompositeComparison,
    ExpectedValueMode,
    FixedRuleDefinition,
    FixedRuleOperator,
    FixedRuleType,
    MultiCompositeMappingConfig,
    MultiCompositePipelineConfig,
    SequenceDirection,
    SequenceStartMode,
)
from backend.app.api.schemas import DataSource, VariableTag


AiProviderPreset = Literal[
    "openai",
    "anthropic",
    "gemini",
    "deepseek",
    "qwen",
    "kimi",
    "zhipu",
    "openrouter",
    "custom_openai",
]
AiProviderProtocol = Literal["openai_compatible", "anthropic", "gemini"]
AiDraftVerdict = Literal["ready", "needs_input", "rejected"]
AiRuleInputMode = Literal["free_text", "structured", "template"]
RulePromptOptimizeStatus = Literal["optimized", "needs_input", "failed"]
MissingKind = Literal["source", "variable", "rule", "parameter", "ability"]
MissingAction = Literal[
    "open_source_dialog",
    "open_single_variable_dialog",
    "open_composite_variable_dialog",
    "edit_description",
    "none",
]


class AiProviderConfigIn(BaseModel):
    """保存或测试个人 AI 供应商配置的入参。"""

    model_config = ConfigDict(extra="forbid")

    provider_preset: AiProviderPreset
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    extra_headers: dict[str, str] = Field(default_factory=dict)

    @field_validator("base_url", "model", "api_key", mode="before")
    @classmethod
    def _strip_optional_string(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class AiProviderConfigOut(BaseModel):
    """返回给前端的个人 AI 供应商配置，不包含明文 key。"""

    model_config = ConfigDict(extra="forbid")

    provider_preset: AiProviderPreset
    protocol: AiProviderProtocol
    base_url: str
    model: str
    api_key_masked: str
    has_extra_headers: bool = False
    updated_at: str | None = None


class AiProviderTestResult(BaseModel):
    """AI 供应商连通性测试结果。"""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    latency_ms: int | None = None
    category: str | None = None
    message: str | None = None


class AiRuleWorkflowHints(BaseModel):
    """前端工作流提供的结构化线索，用于后端确定性补齐草稿。"""

    model_config = ConfigDict(extra="forbid")

    rule_type_hint: FixedRuleType | None = None
    target_variable_tag: str | None = None
    reference_variable_tag: str | None = None
    left_variable_tag: str | None = None
    right_variable_tag: str | None = None
    source_id: str | None = None
    source_type: Literal["local_excel", "svn"] | None = None
    source_url: str | None = None
    sheet: str | None = None
    target_field: str | None = None
    display_field: str | None = None
    filter_field: str | None = None
    filter_operator: Literal["eq", "ne", "gt", "lt", "contains", "not_contains"] | None = None
    filter_value: str | None = None
    assertion_field: str | None = None
    assertion_operator: Literal["eq", "ne", "gt", "lt", "not_null", "regex", "unique", "duplicate_required"] | None = None
    assertion_value: str | None = None
    operator: FixedRuleOperator | None = None
    expected_value: str | None = None
    expected_value_mode: ExpectedValueMode | None = None
    regex_pattern: str | None = None
    sequence_direction: SequenceDirection | None = None
    sequence_step: str | None = None
    sequence_start_mode: SequenceStartMode | None = None
    sequence_start_value: str | None = None
    key_column: str | None = None
    composite_columns: list[str] = Field(default_factory=list)
    reference_source_id: str | None = None
    reference_source_type: Literal["local_excel", "svn"] | None = None
    reference_source_url: str | None = None
    reference_sheet: str | None = None
    reference_field: str | None = None
    reference_key_column: str | None = None
    reference_composite_columns: list[str] = Field(default_factory=list)
    left_filter_field: str | None = None
    left_filter_operator: Literal["eq", "ne", "gt", "lt", "contains", "not_contains"] | None = None
    left_filter_value: str | None = None
    right_filter_field: str | None = None
    right_filter_operator: Literal["eq", "ne", "gt", "lt", "contains", "not_contains"] | None = None
    right_filter_value: str | None = None
    left_key_field: str | None = None
    right_key_field: str | None = None
    compare_fields: list[str] = Field(default_factory=list)
    pipeline_nodes: list[dict[str, Any]] = Field(default_factory=list)
    mapping_nodes: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator(
        "rule_type_hint",
        "target_variable_tag",
        "reference_variable_tag",
        "left_variable_tag",
        "right_variable_tag",
        "source_id",
        "source_type",
        "source_url",
        "sheet",
        "target_field",
        "display_field",
        "filter_field",
        "filter_operator",
        "filter_value",
        "assertion_field",
        "assertion_operator",
        "assertion_value",
        "operator",
        "expected_value",
        "expected_value_mode",
        "regex_pattern",
        "sequence_direction",
        "sequence_step",
        "sequence_start_mode",
        "sequence_start_value",
        "key_column",
        "reference_source_id",
        "reference_source_type",
        "reference_source_url",
        "reference_sheet",
        "reference_field",
        "reference_key_column",
        "left_filter_field",
        "left_filter_operator",
        "left_filter_value",
        "right_filter_field",
        "right_filter_operator",
        "right_filter_value",
        "left_key_field",
        "right_key_field",
        mode="before",
    )
    @classmethod
    def _strip_optional_string(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator(
        "composite_columns",
        "reference_composite_columns",
        "compare_fields",
        mode="before",
    )
    @classmethod
    def _normalize_text_list(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]
        return value

    @field_validator("composite_columns", "reference_composite_columns", "compare_fields")
    @classmethod
    def _strip_text_list(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


class RuleDraftRequest(BaseModel):
    """生成 AI 规则草稿的请求。"""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1, max_length=4000)
    extra_hints: str | None = Field(default=None, max_length=2000)
    workflow_hints: AiRuleWorkflowHints | None = None
    input_mode: AiRuleInputMode = "free_text"
    allow_auto_complete: bool = True
    selected_variable_tags: list[str] = Field(default_factory=list)

    @field_validator("description", "extra_hints", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("selected_variable_tags", mode="before")
    @classmethod
    def _normalize_selected_variable_tags(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]
        return value

    @field_validator("selected_variable_tags")
    @classmethod
    def _strip_selected_variable_tags(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in value:
            tag = item.strip()
            if tag and tag not in seen:
                seen.add(tag)
                result.append(tag)
        return result


class RulePromptOptimizeRequest(BaseModel):
    """优化智能规则自然语言输入的请求。"""

    model_config = ConfigDict(extra="forbid")

    selected_variable_tags: list[str] = Field(default_factory=list)
    raw_description: str = Field(default="", max_length=4000)
    allow_auto_complete: bool = False
    context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("raw_description", mode="before")
    @classmethod
    def _strip_raw_description(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("selected_variable_tags", mode="before")
    @classmethod
    def _normalize_selected_variable_tags(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]
        return value

    @field_validator("selected_variable_tags")
    @classmethod
    def _strip_selected_variable_tags(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in value:
            tag = item.strip()
            if tag and tag not in seen:
                seen.add(tag)
                result.append(tag)
        return result


class RulePromptOptimizeClues(BaseModel):
    """优化输入时识别到的规则线索。"""

    model_config = ConfigDict(extra="forbid")

    rule_type_hint: FixedRuleType | None = None
    involved_variables: list[str] = Field(default_factory=list)
    target_field: str | None = None
    key_field: str | None = None
    filters: list[dict[str, Any]] = Field(default_factory=list)
    compare_fields: list[str] = Field(default_factory=list)
    compare_operator: FixedRuleOperator | None = None


class RulePromptOptimizeResponse(BaseModel):
    """优化智能规则自然语言输入的响应。"""

    model_config = ConfigDict(extra="forbid")

    status: RulePromptOptimizeStatus
    raw_description: str
    optimized_description: str = ""
    detected_clues: RulePromptOptimizeClues = Field(default_factory=RulePromptOptimizeClues)
    missing: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    fallback: bool = False


class VariableIntent(BaseModel):
    """模型输出的变量意图，后端会据此确定性编译为 VariableTag。"""

    model_config = ConfigDict(extra="forbid")

    tag: str | None = None
    source_id: str | None = None
    source_type: str | None = None
    path_or_url: str | None = None
    sheet: str | None = None
    variable_kind: Literal["single", "composite"] = "single"
    column: str | None = None
    columns: list[str] = Field(default_factory=list)
    key_column: str | None = None
    append_index_to_key: bool = False
    expected_type: Literal["int", "str", "json"] | None = None


class RuleIntent(BaseModel):
    """模型输出的规则意图；禁止直接作为最终配置保存。"""

    model_config = ConfigDict(extra="forbid")

    verdict: AiDraftVerdict
    rule_type: FixedRuleType | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    reasoning_summary: str = ""
    rule_name: str | None = None
    display_field: str | None = None
    target: VariableIntent | None = None
    reference: VariableIntent | None = None
    operator: Literal["eq", "ne", "gt", "lt"] | None = None
    expected_value: str | None = None
    expected_value_mode: Literal["single", "set"] | None = None
    regex_pattern: str | None = None
    sequence_direction: Literal["asc", "desc"] | None = None
    sequence_step: str | None = None
    sequence_start_mode: Literal["auto", "manual"] | None = None
    sequence_start_value: str | None = None
    composite_config: CompositeRuleConfig | None = None
    key_check_mode: Literal["baseline_only", "bidirectional"] | None = None
    left_key_field: str | None = None
    right_key_field: str | None = None
    comparisons: list[DualCompositeComparison] = Field(default_factory=list)
    left_filters: list[dict[str, Any]] = Field(default_factory=list)
    right_filters: list[dict[str, Any]] = Field(default_factory=list)
    pipeline_config: MultiCompositePipelineConfig | None = None
    mapping_config: MultiCompositeMappingConfig | None = None
    missing: list["MissingItem"] = Field(default_factory=list)
    rejection_reason: str | None = None


class MissingItem(BaseModel):
    """展示给用户的缺口说明。"""

    model_config = ConfigDict(extra="forbid")

    kind: MissingKind
    message: str
    suggested_action: MissingAction = "none"
    prefill: dict[str, Any] = Field(default_factory=dict)


class RuleDraftPayload(BaseModel):
    """可应用到个人校验 store 的配置草稿。"""

    model_config = ConfigDict(extra="forbid")

    sources_to_add: list[DataSource] = Field(default_factory=list)
    variables_to_add: list[VariableTag] = Field(default_factory=list)
    rules_to_add: list[FixedRuleDefinition] = Field(default_factory=list)
    reuse_variable_tags: list[str] = Field(default_factory=list)


class RuleDraftResponse(BaseModel):
    """AI 规则草稿接口返回体。"""

    model_config = ConfigDict(extra="forbid")

    draft_id: int | None = None
    description: str | None = None
    verdict: AiDraftVerdict
    rule_type: FixedRuleType | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    reasoning_summary: str = ""
    draft: RuleDraftPayload = Field(default_factory=RuleDraftPayload)
    missing: list[MissingItem] = Field(default_factory=list)
    rejection_reason: str | None = None
    extension_suggestions: list[str] = Field(default_factory=list)
    applied: bool = False
    created_at: str | None = None


RuleIntent.model_rebuild()

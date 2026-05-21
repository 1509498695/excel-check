"""Schemas for importing personal workbench rules into project fixed rules."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.api.fixed_rules_schemas import FixedRuleDefinition, FixedRuleGroup, FixedRulesConfig
from backend.app.api.schemas import DataSource, VariableTag


ImportScopeMode = Literal["all", "groups", "rules"]
SourceMappingAction = Literal["new", "reuse", "replace", "skip"]
ImportItemStatus = Literal["new", "reuse", "renamed", "skipped", "error"]
DuplicateRuleAction = Literal["rename", "skip"]


class ImportScope(BaseModel):
    """Selected personal rules to import."""

    model_config = ConfigDict(extra="forbid")

    mode: ImportScopeMode = "all"
    group_ids: list[str] = Field(default_factory=list)
    rule_ids: list[str] = Field(default_factory=list)


class SourceMapping(BaseModel):
    """How an imported personal source should map to project fixed-rules sources."""

    model_config = ConfigDict(extra="forbid")

    personal_source_id: str
    action: SourceMappingAction
    project_source_id: str | None = None
    next_source: DataSource | None = None
    confirmed: bool = False


class ImportConflictResolutions(BaseModel):
    """Optional user-provided conflict resolutions."""

    model_config = ConfigDict(extra="forbid")

    variable_tags: dict[str, str] = Field(default_factory=dict)
    rule_names: dict[str, str] = Field(default_factory=dict)
    group_names: dict[str, str] = Field(default_factory=dict)


class WorkbenchImportPreviewRequest(BaseModel):
    """Request body for previewing or committing an import."""

    model_config = ConfigDict(extra="forbid")

    scope: ImportScope = Field(default_factory=ImportScope)
    selected_rule_ids: list[str] | None = None
    selected_group_ids: list[str] | None = None
    user_id: int | None = None
    project_id: int | None = None
    source_mappings: list[SourceMapping] = Field(default_factory=list)
    conflict_resolutions: ImportConflictResolutions = Field(default_factory=ImportConflictResolutions)
    duplicate_rule_actions: dict[str, DuplicateRuleAction] = Field(default_factory=dict)


class ImportConflict(BaseModel):
    """Conflict or recommendation found during import planning."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    level: Literal["info", "warning", "error"] = "warning"
    item_id: str
    message: str
    candidates: list[str] = Field(default_factory=list)


class ImportSummary(BaseModel):
    """Counts for import results."""

    model_config = ConfigDict(extra="forbid")

    sources_new: int = 0
    sources_reused: int = 0
    sources_skipped: int = 0
    variables_new: int = 0
    variables_reused: int = 0
    variables_skipped: int = 0
    groups_new: int = 0
    groups_reused: int = 0
    rules_new: int = 0
    rules_renamed: int = 0
    rules_skipped: int = 0
    blocking_errors: int = 0


class SourceMappingDraft(BaseModel):
    """Initial source mapping recommendation for the wizard."""

    model_config = ConfigDict(extra="forbid")

    personal_source: DataSource
    recommended_action: SourceMappingAction
    project_source_id: str | None = None
    next_source: DataSource | None = None
    reason: str
    candidates: list[DataSource] = Field(default_factory=list)
    requires_confirmation: bool = False


class ImportItemResult(BaseModel):
    """Per-item import preview result."""

    model_config = ConfigDict(extra="forbid")

    item_id: str
    status: ImportItemStatus
    message: str
    next_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class VariablePreviewResult(BaseModel):
    """Preview data for one imported variable."""

    model_config = ConfigDict(extra="forbid")

    tag: str
    status: Literal["ok", "warning", "error"]
    message: str
    preview: dict[str, Any] | None = None


class WorkbenchImportDraft(BaseModel):
    """Initial import wizard data."""

    model_config = ConfigDict(extra="forbid")

    personal_config: FixedRulesConfig
    project_config: FixedRulesConfig
    importable_groups: list[FixedRuleGroup]
    importable_rules: list[FixedRuleDefinition]
    importable_sources: list[DataSource]
    importable_variables: list[VariableTag]
    source_mappings: list[SourceMappingDraft]
    conflicts: list[ImportConflict]
    summary: ImportSummary


class WorkbenchImportPreview(BaseModel):
    """Import preview result. It is not persisted."""

    model_config = ConfigDict(extra="forbid")

    summary: ImportSummary
    source_results: list[ImportItemResult]
    variable_results: list[ImportItemResult]
    group_results: list[ImportItemResult]
    rule_results: list[ImportItemResult]
    variable_previews: list[VariablePreviewResult]
    conflicts: list[ImportConflict]
    blocking_errors: list[str]
    next_config_preview: FixedRulesConfig


class WorkbenchImportCommitResult(BaseModel):
    """Commit result with latest fixed-rules config."""

    model_config = ConfigDict(extra="forbid")

    config: FixedRulesConfig
    import_summary: ImportSummary
    source_results: list[ImportItemResult]
    variable_results: list[ImportItemResult]
    group_results: list[ImportItemResult]
    rule_results: list[ImportItemResult]

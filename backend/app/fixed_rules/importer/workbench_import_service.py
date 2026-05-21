"""Service layer for importing personal workbench rules into project fixed rules."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.fixed_rules_schemas import (
    FixedRuleDefinition,
    FixedRuleGroup,
    FixedRulesConfig,
)
from backend.app.api.schemas import DataSource, VariableTag
from backend.app.fixed_rules.config_loader import (
    build_default_fixed_rules_config,
    load_fixed_rules_config_with_issues,
    parse_raw_fixed_rules_config,
)
from backend.app.fixed_rules.config_common import _build_default_group
from backend.app.fixed_rules.db_service import load_fixed_rules_config_from_db
from backend.app.fixed_rules.importer.conflict_detector import detect_initial_conflicts
from backend.app.fixed_rules.importer.import_committer import commit_import_preview
from backend.app.fixed_rules.importer.import_preview import build_import_preview
from backend.app.fixed_rules.importer.schemas import (
    ImportConflict,
    ImportScope,
    ImportSummary,
    WorkbenchImportCommitResult,
    WorkbenchImportDraft,
    WorkbenchImportPreview,
    WorkbenchImportPreviewRequest,
)
from backend.app.fixed_rules.importer.rule_mapper import (
    collect_rule_variable_tags,
    select_rules_by_scope,
)
from backend.app.fixed_rules.importer.source_mapper import build_source_mapping_drafts
from backend.app.models import WorkbenchConfigRecord


async def build_workbench_import_draft(
    db: AsyncSession,
    *,
    project_id: int,
    user_id: int,
    selected_rule_ids: list[str] | None = None,
    selected_group_ids: list[str] | None = None,
) -> WorkbenchImportDraft:
    """Load personal and project configs and return import wizard draft data."""
    personal_config = await _load_personal_workbench_as_fixed_config(
        db,
        project_id=project_id,
        user_id=user_id,
    )
    project_config = await _load_project_fixed_rules_config(db, project_id=project_id)
    personal_config = _filter_personal_config_for_scope(
        personal_config,
        selected_rule_ids=selected_rule_ids,
        selected_group_ids=selected_group_ids,
    )
    source_mappings, source_conflicts = build_source_mapping_drafts(
        personal_config.sources,
        project_config.sources,
    )
    conflicts = [
        *source_conflicts,
        *detect_initial_conflicts(personal_config, project_config),
        *_detect_variable_conflicts(personal_config, project_config),
        *_detect_group_name_conflicts(personal_config, project_config),
        *_detect_rule_name_conflicts(personal_config, project_config),
    ]
    return WorkbenchImportDraft(
        personal_config=personal_config,
        project_config=project_config,
        importable_groups=personal_config.groups,
        importable_rules=personal_config.rules,
        importable_sources=personal_config.sources,
        importable_variables=personal_config.variables,
        source_mappings=source_mappings,
        conflicts=_dedupe_conflicts(conflicts),
        summary=ImportSummary(
            sources_new=len(personal_config.sources),
            variables_new=len(personal_config.variables),
            groups_new=max(0, len(personal_config.groups) - 1),
            rules_new=len(personal_config.rules),
        ),
    )


async def preview_workbench_import(
    db: AsyncSession,
    *,
    project_id: int,
    user_id: int,
    request: WorkbenchImportPreviewRequest,
) -> WorkbenchImportPreview:
    """Preview import without persisting anything."""
    personal_config = await _load_personal_workbench_as_fixed_config(
        db,
        project_id=project_id,
        user_id=user_id,
    )
    project_config = await _load_project_fixed_rules_config(db, project_id=project_id)
    return build_import_preview(
        personal_config=personal_config,
        project_config=project_config,
        request=request,
    )


async def commit_workbench_import(
    db: AsyncSession,
    *,
    project_id: int,
    user_id: int,
    request: WorkbenchImportPreviewRequest,
) -> WorkbenchImportCommitResult:
    """Re-preview and persist imported rules only if validation passes."""
    personal_config = await _load_personal_workbench_as_fixed_config(
        db,
        project_id=project_id,
        user_id=user_id,
    )
    project_config = await _load_project_fixed_rules_config(db, project_id=project_id)
    return await commit_import_preview(
        db=db,
        project_id=project_id,
        personal_config=personal_config,
        project_config=project_config,
        request=request,
    )


async def _load_project_fixed_rules_config(
    db: AsyncSession,
    *,
    project_id: int,
) -> FixedRulesConfig:
    raw = await load_fixed_rules_config_from_db(db, project_id)
    if raw is None:
        return build_default_fixed_rules_config()
    parsed = parse_raw_fixed_rules_config(raw)
    config, _ = load_fixed_rules_config_with_issues(
        parsed,
        allow_legacy_mapping_config=True,
    )
    return config


async def _load_personal_workbench_as_fixed_config(
    db: AsyncSession,
    *,
    project_id: int,
    user_id: int,
) -> FixedRulesConfig:
    result = await db.execute(
        select(WorkbenchConfigRecord).where(
            WorkbenchConfigRecord.project_id == project_id,
            WorkbenchConfigRecord.user_id == user_id,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        return build_default_fixed_rules_config()
    try:
        payload = json.loads(record.config_json)
    except json.JSONDecodeError as exc:
        raise ValueError("个人校验配置 JSON 格式不正确。") from exc
    return _parse_workbench_payload_as_fixed_config(payload)


def _parse_workbench_payload_as_fixed_config(payload: Any) -> FixedRulesConfig:
    if not isinstance(payload, dict):
        raise ValueError("个人校验配置格式不正确。")
    sources = _validate_list(payload.get("sources"), DataSource)
    variables = _validate_list(payload.get("variables"), VariableTag)
    groups = _validate_list(payload.get("ruleGroups"), FixedRuleGroup)
    rules = _validate_list(payload.get("orchestrationRules"), FixedRuleDefinition)
    return FixedRulesConfig(
        version=6,
        configured=bool(sources or variables or groups or rules),
        sources=sources,
        variables=variables,
        groups=groups or [_build_default_group()],
        rules=rules,
        local_path_replacement_presets=_string_list(
            payload.get("local_path_replacement_presets")
            or payload.get("path_replacement_presets")
            or payload.get("pathReplacementPresets")
        ),
        selected_local_path_replacement_preset=_optional_string(
            payload.get("selected_local_path_replacement_preset")
            or payload.get("selected_path_replacement_preset")
            or payload.get("selectedPathReplacementPreset")
        ),
        svn_path_replacement_presets=_string_list(payload.get("svn_path_replacement_presets")),
        selected_svn_path_replacement_preset=_optional_string(
            payload.get("selected_svn_path_replacement_preset")
        ),
    )


def _filter_personal_config_for_scope(
    config: FixedRulesConfig,
    *,
    selected_rule_ids: list[str] | None,
    selected_group_ids: list[str] | None,
) -> FixedRulesConfig:
    """Return a draft-sized personal config with only selected import dependencies."""
    if selected_rule_ids is None and selected_group_ids is None:
        return config

    scope = ImportScope(mode="all")
    if selected_rule_ids is not None:
        scope = ImportScope(mode="rules", rule_ids=selected_rule_ids)
    elif selected_group_ids is not None:
        scope = ImportScope(mode="groups", group_ids=selected_group_ids)

    selected_rules = select_rules_by_scope(config.rules, scope)
    referenced_tags: set[str] = set()
    for rule in selected_rules:
        referenced_tags.update(collect_rule_variable_tags(rule))

    selected_variables = [
        variable
        for variable in config.variables
        if variable.tag in referenced_tags
    ]
    selected_source_ids = {variable.source_id for variable in selected_variables}
    selected_group_ids_from_rules = {rule.group_id for rule in selected_rules}
    selected_groups = [
        group
        for group in config.groups
        if group.group_id in selected_group_ids_from_rules
    ]
    if not selected_groups:
        selected_groups = [_build_default_group()]

    return config.model_copy(
        update={
            "sources": [source for source in config.sources if source.id in selected_source_ids],
            "variables": selected_variables,
            "groups": selected_groups,
            "rules": selected_rules,
        }
    )


def _validate_list(raw_items: Any, model_type):
    if not isinstance(raw_items, list):
        return []
    return [model_type.model_validate(item) for item in raw_items if isinstance(item, dict)]


def _string_list(raw_items: Any) -> list[str]:
    if not isinstance(raw_items, list):
        return []
    return [str(item) for item in raw_items if str(item or "").strip()]


def _optional_string(raw_item: Any) -> str | None:
    if not isinstance(raw_item, str):
        return None
    normalized = raw_item.strip()
    return normalized or None


def _dedupe_conflicts(conflicts):
    seen: set[tuple[str, str, str]] = set()
    deduped = []
    for conflict in conflicts:
        key = (conflict.kind, conflict.item_id, conflict.message)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(conflict)
    return deduped


def _detect_variable_conflicts(
    personal_config: FixedRulesConfig,
    project_config: FixedRulesConfig,
) -> list[ImportConflict]:
    from backend.app.fixed_rules.importer.variable_mapper import variable_same_definition

    project_by_tag = {variable.tag: variable for variable in project_config.variables}
    conflicts: list[ImportConflict] = []
    for variable in personal_config.variables:
        existing = project_by_tag.get(variable.tag)
        if existing is not None and not variable_same_definition(variable, existing):
            conflicts.append(
                ImportConflict(
                    kind="variable_tag",
                    level="warning",
                    item_id=variable.tag,
                    message="项目校验已存在同名但定义不同的变量，导入前建议改名。",
                    candidates=[existing.tag],
                )
            )
    return conflicts


def _detect_group_name_conflicts(
    personal_config: FixedRulesConfig,
    project_config: FixedRulesConfig,
) -> list[ImportConflict]:
    project_group_names = {group.group_name for group in project_config.groups}
    conflicts: list[ImportConflict] = []
    for group in personal_config.groups:
        if group.group_id == "ungrouped":
            continue
        if group.group_name in project_group_names:
            conflicts.append(
                ImportConflict(
                    kind="group_name",
                    level="info",
                    item_id=group.group_id,
                    message="项目校验已存在同名规则组，默认会复用；如需新建可填写新规则组名。",
                    candidates=[group.group_name],
                )
            )
    return conflicts


def _detect_rule_name_conflicts(
    personal_config: FixedRulesConfig,
    project_config: FixedRulesConfig,
) -> list[ImportConflict]:
    project_rule_names = {rule.rule_name for rule in project_config.rules}
    conflicts: list[ImportConflict] = []
    for rule in personal_config.rules:
        if rule.rule_name in project_rule_names:
            conflicts.append(
                ImportConflict(
                    kind="rule_name",
                    level="warning",
                    item_id=rule.rule_id,
                    message="项目校验已存在同名规则，默认会追加“导入”后缀；也可手动填写新规则名。",
                    candidates=[rule.rule_name],
                )
            )
    return conflicts

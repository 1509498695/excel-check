"""个人校验规则导入项目校验的预检与合并服务。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import urlparse
from uuid import uuid4

from backend.app.api.fixed_rules_schemas import (
    CompositeCondition,
    FixedRuleDefinition,
    FixedRuleGroup,
    FixedRulesConfig,
)
from backend.app.api.schemas import DataSource, VariableTag
from backend.app.fixed_rules.service import (
    UNGROUPED_GROUP_ID,
    UNGROUPED_GROUP_NAME,
    build_default_fixed_rules_config,
    load_fixed_rules_config_with_issues,
)
from backend.app.loaders.local_reader import read_source_metadata


ImportRuleStatus = Literal["ready", "duplicate", "skipped"]
SourceMappingMode = Literal["project", "custom", "new", "blocked"]
VariableMappingMode = Literal["project", "new", "blocked"]
VariableIssueCode = Literal[
    "tag_conflict",
    "duplicate_target_tag",
    "field_missing",
    "ambiguous_variable",
]

SUPPORTED_IMPORT_SOURCE_TYPES = {"local_excel", "svn"}
GENERATED_FINGERPRINT_KEYS = {
    "rule_id",
    "rule_name",
    "group_id",
    "display_field",
    "condition_id",
    "branch_id",
    "comparison_id",
    "node_id",
    "range_id",
    "check_id",
}


@dataclass
class FieldRequirement:
    fields: set[str] = field(default_factory=set)
    uses_key: bool = False

    def merge(self, other: "FieldRequirement") -> None:
        self.fields.update(other.fields)
        self.uses_key = self.uses_key or other.uses_key


@dataclass
class SourceMapping:
    personal_source_id: str
    personal_source: DataSource | None
    final_source: DataSource | None
    mode: SourceMappingMode
    status: Literal["ready", "skipped"]
    issue: str | None = None
    project_source_id: str | None = None
    metadata: dict[str, Any] | None = None
    source_to_add: DataSource | None = None


@dataclass
class VariableMapping:
    personal_tag: str
    mode: VariableMappingMode
    status: Literal["ready", "skipped"]
    final_tag: str | None = None
    issue: str | None = None
    override_tag: str | None = None
    suggested_tag: str | None = None
    can_rename: bool = False
    issue_code: VariableIssueCode | None = None
    field_map: dict[str, str] = field(default_factory=dict)
    variable_to_add: VariableTag | None = None


@dataclass
class RuleImportCandidate:
    status: ImportRuleStatus
    rule_id: str
    rule_name: str
    reason: str | None = None
    candidate_rule: FixedRuleDefinition | None = None
    required_tags: list[str] = field(default_factory=list)


@dataclass
class ImportPreviewBuild:
    response: dict[str, Any]
    config: FixedRulesConfig
    sources_to_add: list[DataSource]
    variables_to_add: list[VariableTag]
    groups_to_add: list[FixedRuleGroup]
    rules_to_add: list[FixedRuleDefinition]


def build_import_preview(
    *,
    workbench_payload: object,
    fixed_config: FixedRulesConfig | None,
    selected_rule_ids: list[str],
    source_overrides: dict[str, DataSource] | None = None,
    variable_tag_overrides: dict[str, str] | None = None,
) -> ImportPreviewBuild:
    """构建从个人校验导入项目校验的预检结果。"""
    normalized_selected_rule_ids = [
        rule_id.strip() for rule_id in selected_rule_ids if rule_id.strip()
    ]
    if not normalized_selected_rule_ids:
        raise ValueError("请先勾选需要导入项目校验的个人规则。")

    personal_config = _parse_workbench_config(workbench_payload)
    project_config = fixed_config or build_default_fixed_rules_config()
    overrides = source_overrides or {}
    tag_overrides = _normalize_variable_tag_overrides(variable_tag_overrides)

    personal_rule_map = {rule.rule_id: rule for rule in personal_config.rules}
    personal_variable_map = {variable.tag: variable for variable in personal_config.variables}
    personal_source_map = {source.id: source for source in personal_config.sources}

    selected_rules: list[FixedRuleDefinition] = []
    rule_candidates: list[RuleImportCandidate] = []
    for rule_id in normalized_selected_rule_ids:
        rule = personal_rule_map.get(rule_id)
        if rule is None:
            rule_candidates.append(
                RuleImportCandidate(
                    status="skipped",
                    rule_id=rule_id,
                    rule_name=rule_id,
                    reason="个人校验中已不存在该规则。",
                )
            )
            continue
        selected_rules.append(rule)

    rule_requirements = {
        rule.rule_id: _collect_rule_requirements(rule, personal_variable_map)
        for rule in selected_rules
    }
    global_requirements = _merge_rule_requirements(rule_requirements.values())
    project_variable_tags = {variable.tag for variable in project_config.variables}
    target_tag_counts: dict[str, int] = {}
    for tag in global_requirements:
        target_tag = tag_overrides.get(tag) or tag
        target_tag_counts[target_tag] = target_tag_counts.get(target_tag, 0) + 1
    duplicate_target_tags = {
        tag
        for tag, count in target_tag_counts.items()
        if count > 1 and tag not in project_variable_tags
    }

    source_ids = {
        personal_variable_map[tag].source_id
        for tag in global_requirements
        if tag in personal_variable_map
    }
    source_mappings = {
        source_id: _build_source_mapping(
            source_id=source_id,
            personal_source=personal_source_map.get(source_id),
            project_config=project_config,
            override=overrides.get(source_id),
        )
        for source_id in sorted(source_ids)
    }

    variable_mappings: dict[str, VariableMapping] = {}
    for tag, requirement in global_requirements.items():
        variable_mappings[tag] = _build_variable_mapping(
            personal_tag=tag,
            personal_variable=personal_variable_map.get(tag),
            requirement=requirement,
            source_mappings=source_mappings,
            project_config=project_config,
            override_tag=tag_overrides.get(tag),
            duplicate_target_tags=duplicate_target_tags,
        )

    group_map, groups_to_add = _build_group_mapping(
        personal_config=personal_config,
        project_config=project_config,
        selected_rules=selected_rules,
    )
    sources_to_add = _unique_sources(
        mapping.source_to_add
        for mapping in source_mappings.values()
        if mapping.status == "ready"
    )
    variables_to_add = _unique_variables(
        mapping.variable_to_add
        for mapping in variable_mappings.values()
        if mapping.status == "ready"
    )

    existing_fingerprints = {
        _fingerprint_rule(rule) for rule in project_config.rules
    }
    candidate_fingerprints: set[str] = set()
    rules_to_add: list[FixedRuleDefinition] = []

    for rule in selected_rules:
        requirements = rule_requirements[rule.rule_id]
        blocking_reasons = _collect_rule_blocking_reasons(
            requirements=requirements,
            personal_variable_map=personal_variable_map,
            variable_mappings=variable_mappings,
        )
        if blocking_reasons:
            rule_candidates.append(
                RuleImportCandidate(
                    status="skipped",
                    rule_id=rule.rule_id,
                    rule_name=rule.rule_name,
                    reason="；".join(blocking_reasons),
                    required_tags=sorted(requirements),
                )
            )
            continue

        mapped_rule = _build_mapped_rule(
            rule=rule,
            requirements=requirements,
            variable_mappings=variable_mappings,
            group_id=group_map.get(rule.group_id, UNGROUPED_GROUP_ID),
        )
        fingerprint = _fingerprint_rule(mapped_rule)
        if fingerprint in existing_fingerprints or fingerprint in candidate_fingerprints:
            rule_candidates.append(
                RuleImportCandidate(
                    status="duplicate",
                    rule_id=rule.rule_id,
                    rule_name=rule.rule_name,
                    reason="项目校验中已存在语义相同的规则。",
                    required_tags=sorted(requirements),
                )
            )
            continue

        validation_error = _validate_candidate_rule(
            project_config=project_config,
            sources_to_add=sources_to_add,
            variables_to_add=variables_to_add,
            groups_to_add=groups_to_add,
            candidate_rule=mapped_rule,
        )
        if validation_error:
            rule_candidates.append(
                RuleImportCandidate(
                    status="skipped",
                    rule_id=rule.rule_id,
                    rule_name=rule.rule_name,
                    reason=validation_error,
                    required_tags=sorted(requirements),
                )
            )
            continue

        candidate_fingerprints.add(fingerprint)
        rules_to_add.append(mapped_rule)
        rule_candidates.append(
            RuleImportCandidate(
                status="ready",
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                candidate_rule=mapped_rule,
                required_tags=sorted(requirements),
            )
        )

    ready_final_tags = {
        variable_mappings[tag].final_tag
        for candidate in rule_candidates
        if candidate.status == "ready"
        for tag in candidate.required_tags
        if variable_mappings.get(tag) and variable_mappings[tag].final_tag
    }
    variables_to_add = [
        variable for variable in variables_to_add if variable.tag in ready_final_tags
    ]
    ready_source_ids = {variable.source_id for variable in variables_to_add}
    sources_to_add = [
        source for source in sources_to_add if source.id in ready_source_ids
    ]
    ready_group_ids = {rule.group_id for rule in rules_to_add}
    groups_to_add = [group for group in groups_to_add if group.group_id in ready_group_ids]

    response = _build_preview_response(
        selected_rule_ids=normalized_selected_rule_ids,
        source_overrides=overrides,
        variable_tag_overrides=tag_overrides,
        source_mappings=source_mappings,
        variable_mappings=variable_mappings,
        rule_candidates=rule_candidates,
    )
    return ImportPreviewBuild(
        response=response,
        config=project_config,
        sources_to_add=sources_to_add,
        variables_to_add=variables_to_add,
        groups_to_add=groups_to_add,
        rules_to_add=rules_to_add,
    )


def build_imported_config(preview: ImportPreviewBuild) -> FixedRulesConfig:
    """基于预检结果合并项目校验配置。"""
    merged = FixedRulesConfig(
        version=6,
        configured=True,
        sources=[*preview.config.sources, *preview.sources_to_add],
        variables=[*preview.config.variables, *preview.variables_to_add],
        groups=[*preview.config.groups, *preview.groups_to_add],
        rules=[*preview.config.rules, *preview.rules_to_add],
        local_path_replacement_presets=preview.config.local_path_replacement_presets,
        selected_local_path_replacement_preset=preview.config.selected_local_path_replacement_preset,
        svn_path_replacement_presets=preview.config.svn_path_replacement_presets,
        selected_svn_path_replacement_preset=preview.config.selected_svn_path_replacement_preset,
    )
    normalized, _issues = load_fixed_rules_config_with_issues(
        merged,
        allow_legacy_mapping_config=True,
        allow_unsupported_csv=False,
    )
    return normalized


def _parse_workbench_config(payload: object) -> FixedRulesConfig:
    if not isinstance(payload, dict):
        raise ValueError("个人校验配置格式不正确。")
    config_payload = {
        "version": 6,
        "configured": bool(payload),
        "sources": payload.get("sources") if isinstance(payload.get("sources"), list) else [],
        "variables": payload.get("variables")
        if isinstance(payload.get("variables"), list)
        else [],
        "groups": payload.get("ruleGroups")
        if isinstance(payload.get("ruleGroups"), list)
        else [],
        "rules": payload.get("orchestrationRules")
        if isinstance(payload.get("orchestrationRules"), list)
        else [],
    }
    return FixedRulesConfig.model_validate(config_payload)


def _normalize_variable_tag_overrides(
    variable_tag_overrides: dict[str, str] | None,
) -> dict[str, str]:
    result: dict[str, str] = {}
    for personal_tag, target_tag in (variable_tag_overrides or {}).items():
        normalized_personal_tag = str(personal_tag or "").strip()
        normalized_target_tag = str(target_tag or "").strip()
        if not normalized_personal_tag or not normalized_target_tag:
            continue
        result[normalized_personal_tag] = normalized_target_tag
    return result


def _build_source_mapping(
    *,
    source_id: str,
    personal_source: DataSource | None,
    project_config: FixedRulesConfig,
    override: DataSource | None,
) -> SourceMapping:
    if personal_source is None:
        return SourceMapping(
            personal_source_id=source_id,
            personal_source=None,
            final_source=None,
            mode="blocked",
            status="skipped",
            issue=f"个人数据源“{source_id}”不存在。",
        )

    project_sources_by_id = {source.id: source for source in project_config.sources}
    final_source: DataSource | None = None
    project_source: DataSource | None = None
    mode: SourceMappingMode = "blocked"
    source_to_add: DataSource | None = None

    if override is not None:
        conflict = project_sources_by_id.get(override.id)
        if conflict is not None and not _is_same_source_locator(conflict, override):
            return SourceMapping(
                personal_source_id=source_id,
                personal_source=personal_source,
                final_source=override,
                mode="blocked",
                status="skipped",
                project_source_id=conflict.id,
                issue=(
                    f"自定义数据源标识“{override.id}”已存在于项目校验，"
                    "且路径或类型不同。请修改标识后重新预检。"
                ),
            )
        if conflict is not None:
            final_source = conflict
            project_source = conflict
            mode = "project"
        else:
            final_source = override
            mode = "custom"
            source_to_add = override
    else:
        same_id_source = project_sources_by_id.get(personal_source.id)
        if same_id_source is not None and same_id_source.type == personal_source.type:
            final_source = same_id_source
            project_source = same_id_source
            mode = "project"
        elif same_id_source is not None:
            return SourceMapping(
                personal_source_id=source_id,
                personal_source=personal_source,
                final_source=None,
                mode="blocked",
                status="skipped",
                project_source_id=same_id_source.id,
                issue=(
                    f"项目校验中已存在同名数据源“{personal_source.id}”，"
                    "但数据源类型不同。请在导入页改为自定义数据源标识。"
                ),
            )
        else:
            matched_sources = _find_project_sources_by_basename(
                project_config.sources,
                personal_source,
            )
            if len(matched_sources) == 1:
                final_source = matched_sources[0]
                project_source = matched_sources[0]
                mode = "project"
            elif len(matched_sources) > 1:
                return SourceMapping(
                    personal_source_id=source_id,
                    personal_source=personal_source,
                    final_source=None,
                    mode="blocked",
                    status="skipped",
                    issue=(
                        f"项目校验中存在多个与个人数据源“{source_id}”文件名相同的候选，"
                        "请在导入页改为自定义数据源。"
                    ),
                )
            else:
                final_source = personal_source
                mode = "new"
                source_to_add = personal_source

    if final_source is None:
        return SourceMapping(
            personal_source_id=source_id,
            personal_source=personal_source,
            final_source=None,
            mode="blocked",
            status="skipped",
            issue=f"无法确定个人数据源“{source_id}”的导入目标。",
        )

    if final_source.type not in SUPPORTED_IMPORT_SOURCE_TYPES:
        return SourceMapping(
            personal_source_id=source_id,
            personal_source=personal_source,
            final_source=final_source,
            mode="blocked",
            status="skipped",
            project_source_id=project_source.id if project_source else None,
            issue="规则导入仅支持 Excel 或 SVN Excel 数据源。",
        )

    metadata, metadata_error = _read_metadata_safely(final_source)
    if metadata_error:
        return SourceMapping(
            personal_source_id=source_id,
            personal_source=personal_source,
            final_source=final_source,
            mode=mode,
            status="skipped",
            project_source_id=project_source.id if project_source else None,
            issue=metadata_error,
            source_to_add=source_to_add,
        )

    return SourceMapping(
        personal_source_id=source_id,
        personal_source=personal_source,
        final_source=final_source,
        mode=mode,
        status="ready",
        project_source_id=project_source.id if project_source else None,
        metadata=metadata,
        source_to_add=source_to_add if mode in {"custom", "new"} else None,
    )


def _build_variable_mapping(
    *,
    personal_tag: str,
    personal_variable: VariableTag | None,
    requirement: FieldRequirement,
    source_mappings: dict[str, SourceMapping],
    project_config: FixedRulesConfig,
    override_tag: str | None,
    duplicate_target_tags: set[str],
) -> VariableMapping:
    project_variables_by_tag = {
        variable.tag: variable for variable in project_config.variables
    }
    target_tag = override_tag or personal_tag
    suggested_tag = _suggest_import_tag(
        target_tag,
        unavailable_tags={
            *project_variables_by_tag.keys(),
            *duplicate_target_tags,
            target_tag,
        },
    )

    if personal_variable is None:
        return VariableMapping(
            personal_tag=personal_tag,
            mode="blocked",
            status="skipped",
            issue=f"个人变量“{personal_tag}”不存在。",
            override_tag=override_tag,
            suggested_tag=suggested_tag,
            can_rename=True,
            issue_code="tag_conflict",
        )

    if target_tag in duplicate_target_tags:
        return VariableMapping(
            personal_tag=personal_tag,
            mode="blocked",
            status="skipped",
            issue=f"多个个人变量指向同一个新增目标变量“{target_tag}”，请分别修改变量池标签。",
            override_tag=override_tag,
            suggested_tag=suggested_tag,
            can_rename=True,
            issue_code="duplicate_target_tag",
        )

    source_mapping = source_mappings.get(personal_variable.source_id)
    if source_mapping is None or source_mapping.status != "ready" or source_mapping.final_source is None:
        return VariableMapping(
            personal_tag=personal_tag,
            mode="blocked",
            status="skipped",
            issue=source_mapping.issue if source_mapping else "变量引用的数据源无法映射。",
            override_tag=override_tag,
            suggested_tag=suggested_tag,
            can_rename=True,
            issue_code="field_missing",
        )

    try:
        normalized = _normalize_personal_variable_for_target(
            personal_variable,
            requirement,
            source_mapping,
        )
    except ValueError as exc:
        return VariableMapping(
            personal_tag=personal_tag,
            mode="blocked",
            status="skipped",
            issue=str(exc),
            override_tag=override_tag,
            suggested_tag=suggested_tag,
            can_rename=False,
            issue_code="field_missing",
        )

    normalized_variable = normalized["variable"].model_copy(update={"tag": target_tag})
    matching_variables = [
        variable
        for variable in project_config.variables
        if _project_variable_matches(
            project_variable=variable,
            normalized_variable=normalized_variable,
            field_set=normalized["field_set"],
            metadata=source_mapping.metadata or {},
        )
    ]

    same_tag_variable = project_variables_by_tag.get(target_tag)
    if same_tag_variable is not None:
        same_tag_matches = [
            variable for variable in matching_variables if variable.tag == target_tag
        ]
        if same_tag_matches:
            return VariableMapping(
                personal_tag=personal_tag,
                mode="project",
                status="ready",
                final_tag=same_tag_matches[0].tag,
                override_tag=override_tag,
                suggested_tag=suggested_tag,
                can_rename=False,
                field_map=_build_field_map_for_project_variable(
                    personal_variable,
                    same_tag_matches[0],
                    normalized["field_map"],
                    source_mapping.metadata or {},
                ),
            )
        return VariableMapping(
            personal_tag=personal_tag,
            mode="blocked",
            status="skipped",
            issue=f"项目变量池中已存在同名变量“{target_tag}”，但绑定表或字段不同。请修改变量池标签后重新预检。",
            override_tag=override_tag,
            suggested_tag=suggested_tag,
            can_rename=True,
            issue_code="tag_conflict",
        )

    if override_tag:
        return VariableMapping(
            personal_tag=personal_tag,
            mode="new",
            status="ready",
            final_tag=target_tag,
            override_tag=override_tag,
            suggested_tag=suggested_tag,
            can_rename=False,
            field_map=normalized["field_map"],
            variable_to_add=normalized_variable,
        )

    if len(matching_variables) > 1:
        candidate_tags = "、".join(variable.tag for variable in matching_variables[:5])
        return VariableMapping(
            personal_tag=personal_tag,
            mode="blocked",
            status="skipped",
            issue=f"项目变量池中有多个字段覆盖候选：{candidate_tags}。",
            override_tag=override_tag,
            suggested_tag=suggested_tag,
            can_rename=True,
            issue_code="ambiguous_variable",
        )
    if len(matching_variables) == 1:
        matched_variable = matching_variables[0]
        return VariableMapping(
            personal_tag=personal_tag,
            mode="project",
            status="ready",
            final_tag=matched_variable.tag,
            override_tag=override_tag,
            suggested_tag=suggested_tag,
            can_rename=False,
            field_map=_build_field_map_for_project_variable(
                personal_variable,
                matched_variable,
                normalized["field_map"],
                source_mapping.metadata or {},
            ),
        )

    return VariableMapping(
        personal_tag=personal_tag,
        mode="new",
        status="ready",
        final_tag=target_tag,
        override_tag=override_tag,
        suggested_tag=suggested_tag,
        can_rename=False,
        field_map=normalized["field_map"],
        variable_to_add=normalized_variable,
    )


def _normalize_personal_variable_for_target(
    personal_variable: VariableTag,
    requirement: FieldRequirement,
    source_mapping: SourceMapping,
) -> dict[str, Any]:
    metadata = source_mapping.metadata or {}
    sheet_names = [str(sheet["name"]) for sheet in metadata.get("sheets", [])]
    resolved_sheet = _resolve_identifier(
        personal_variable.sheet,
        sheet_names,
        label="Sheet",
        context=f"变量“{personal_variable.tag}”",
    )
    available_columns = _get_sheet_columns(metadata, resolved_sheet)
    variable_kind = personal_variable.variable_kind or "single"
    field_map = {"__key__": "__key__"}

    if variable_kind == "single":
        column = _resolve_identifier(
            personal_variable.column or "",
            available_columns,
            label="列名",
            context=f"变量“{personal_variable.tag}”",
        )
        if personal_variable.column:
            field_map[personal_variable.column] = column
        return {
            "variable": VariableTag(
                tag=personal_variable.tag,
                source_id=source_mapping.final_source.id,  # type: ignore[union-attr]
                sheet=resolved_sheet,
                variable_kind="single",
                column=column,
                expected_type=personal_variable.expected_type or "str",
            ),
            "field_set": {column},
            "field_map": field_map,
        }

    key_column = _resolve_identifier(
        personal_variable.key_column or "",
        available_columns,
        label="key 列",
        context=f"变量“{personal_variable.tag}”",
    )
    field_map[personal_variable.key_column or ""] = key_column
    requested_fields = set(requirement.fields)
    if requirement.uses_key or not requested_fields:
        requested_fields.add(personal_variable.key_column or "")
    if personal_variable.key_column:
        requested_fields.add(personal_variable.key_column)

    resolved_columns: list[str] = []
    for field_name in _unique_strings(
        [
            *(personal_variable.columns or []),
            *sorted(requested_fields),
        ]
    ):
        if field_name not in requested_fields and len(resolved_columns) >= 2:
            continue
        resolved = _resolve_identifier(
            field_name,
            available_columns,
            label="列名",
            context=f"变量“{personal_variable.tag}”",
        )
        field_map[field_name] = resolved
        if field_name in requested_fields or len(resolved_columns) < 2:
            resolved_columns.append(resolved)

    resolved_columns = _unique_strings([key_column, *resolved_columns])
    if len(resolved_columns) < 2:
        raise ValueError(f"组合变量“{personal_variable.tag}”可导入字段不足 2 列。")

    return {
        "variable": VariableTag(
            tag=personal_variable.tag,
            source_id=source_mapping.final_source.id,  # type: ignore[union-attr]
            sheet=resolved_sheet,
            variable_kind="composite",
            columns=resolved_columns,
            key_column=key_column,
            append_index_to_key=personal_variable.append_index_to_key,
            expected_type="json",
        ),
        "field_set": set(resolved_columns),
        "field_map": field_map,
    }


def _project_variable_matches(
    *,
    project_variable: VariableTag,
    normalized_variable: VariableTag,
    field_set: set[str],
    metadata: dict[str, Any],
) -> bool:
    if (project_variable.variable_kind or "single") != (
        normalized_variable.variable_kind or "single"
    ):
        return False
    if project_variable.source_id != normalized_variable.source_id:
        return False
    try:
        project_sheet = _resolve_identifier(
            project_variable.sheet,
            [str(sheet["name"]) for sheet in metadata.get("sheets", [])],
            label="Sheet",
            context=f"项目变量“{project_variable.tag}”",
        )
    except ValueError:
        return False
    if project_sheet != normalized_variable.sheet:
        return False

    if (normalized_variable.variable_kind or "single") == "single":
        return _safe_resolve_column(
            project_variable.column or "",
            metadata,
            project_sheet,
        ) == normalized_variable.column

    project_key = _safe_resolve_column(
        project_variable.key_column or "",
        metadata,
        project_sheet,
    )
    if project_key != normalized_variable.key_column:
        return False
    if project_variable.append_index_to_key != normalized_variable.append_index_to_key:
        return False
    project_columns = {
        resolved
        for column in (project_variable.columns or [])
        if (resolved := _safe_resolve_column(column, metadata, project_sheet))
    }
    return field_set.issubset(project_columns)


def _build_field_map_for_project_variable(
    personal_variable: VariableTag,
    project_variable: VariableTag,
    base_field_map: dict[str, str],
    metadata: dict[str, Any],
) -> dict[str, str]:
    if (project_variable.variable_kind or "single") == "single":
        column = _safe_resolve_column(
            project_variable.column or "",
            metadata,
            project_variable.sheet,
        ) or project_variable.column
        return {
            **base_field_map,
            personal_variable.column or "": column or "",
            "__key__": "__key__",
        }

    project_columns = [
        _safe_resolve_column(column, metadata, project_variable.sheet) or column
        for column in (project_variable.columns or [])
    ]
    field_map = {"__key__": "__key__", **base_field_map}
    for original, resolved in list(base_field_map.items()):
        if original == "__key__":
            continue
        matched = _resolve_identifier_or_none(resolved, project_columns)
        if matched:
            field_map[original] = matched
    if personal_variable.key_column:
        project_key = _safe_resolve_column(
            project_variable.key_column or "",
            metadata,
            project_variable.sheet,
        )
        field_map[personal_variable.key_column] = project_key or project_variable.key_column or ""
    return field_map


def _build_group_mapping(
    *,
    personal_config: FixedRulesConfig,
    project_config: FixedRulesConfig,
    selected_rules: list[FixedRuleDefinition],
) -> tuple[dict[str, str], list[FixedRuleGroup]]:
    personal_groups = {group.group_id: group for group in personal_config.groups}
    project_groups_by_name = {group.group_name: group for group in project_config.groups}
    project_group_ids = {group.group_id for group in project_config.groups}
    group_map: dict[str, str] = {UNGROUPED_GROUP_ID: UNGROUPED_GROUP_ID}
    groups_to_add: list[FixedRuleGroup] = []

    for rule in selected_rules:
        if rule.group_id in group_map:
            continue
        personal_group = personal_groups.get(rule.group_id)
        group_name = (
            personal_group.group_name
            if personal_group and personal_group.group_name.strip()
            else UNGROUPED_GROUP_NAME
        )
        if group_name == UNGROUPED_GROUP_NAME:
            group_map[rule.group_id] = UNGROUPED_GROUP_ID
            continue
        matched_project_group = project_groups_by_name.get(group_name)
        if matched_project_group:
            group_map[rule.group_id] = matched_project_group.group_id
            continue
        group_id = _new_entity_id("import-group")
        while group_id in project_group_ids:
            group_id = _new_entity_id("import-group")
        project_group_ids.add(group_id)
        group_map[rule.group_id] = group_id
        groups_to_add.append(
            FixedRuleGroup(group_id=group_id, group_name=group_name, builtin=False)
        )

    return group_map, groups_to_add


def _collect_rule_requirements(
    rule: FixedRuleDefinition,
    personal_variable_map: dict[str, VariableTag],
) -> dict[str, FieldRequirement]:
    requirements: dict[str, FieldRequirement] = {}

    def ensure(tag: str | None) -> FieldRequirement:
        normalized_tag = (tag or "").strip()
        if normalized_tag not in requirements:
            requirements[normalized_tag] = FieldRequirement()
        return requirements[normalized_tag]

    target_tag = _get_primary_rule_target_tag(rule)
    ensure(target_tag)
    if rule.reference_variable_tag:
        ensure(rule.reference_variable_tag)

    if rule.rule_type == "composite_condition_check" and rule.composite_config:
        target_req = ensure(rule.target_variable_tag)
        _collect_conditions(target_req, rule.composite_config.global_filters)
        for branch in rule.composite_config.branches:
            _collect_conditions(target_req, branch.filters)
            _collect_conditions(target_req, branch.assertions)
        _add_display_field(target_req, rule.display_field)
    elif rule.rule_type == "dual_composite_compare":
        left_req = ensure(rule.target_variable_tag)
        right_req = ensure(rule.reference_variable_tag)
        _add_field(left_req, rule.left_key_field or "__key__")
        _add_field(right_req, rule.right_key_field or "__key__")
        _collect_conditions(left_req, rule.left_filters)
        _collect_conditions(right_req, rule.right_filters)
        for comparison in rule.comparisons:
            _add_field(left_req, comparison.left_field)
            _add_field(right_req, comparison.right_field)
        _add_display_field(left_req, rule.display_field)
    elif rule.rule_type == "multi_composite_pipeline_check" and rule.pipeline_config:
        for node in rule.pipeline_config.nodes:
            node_req = ensure(node.variable_tag)
            _collect_conditions(node_req, node.filters)
            _collect_conditions(node_req, node.assertions)
            _add_display_field(node_req, node.display_field)
    elif rule.rule_type == "multi_composite_mapping_check" and rule.mapping_config:
        for node in rule.mapping_config.nodes:
            node_req = ensure(node.variable_tag)
            _collect_conditions(node_req, node.filters)
            _add_display_field(node_req, node.display_field)

    for tag, req in requirements.items():
        variable = personal_variable_map.get(tag)
        if variable and (variable.variable_kind or "single") == "single" and variable.column:
            req.fields.add(variable.column)
        if variable and (variable.variable_kind or "single") == "composite":
            req.uses_key = req.uses_key or "__key__" in req.fields
            req.fields.discard("__key__")

    return {tag: req for tag, req in requirements.items() if tag}


def _collect_conditions(
    requirement: FieldRequirement,
    conditions: list[CompositeCondition] | None,
) -> None:
    for condition in conditions or []:
        _add_field(requirement, condition.field)
        if condition.value_source == "field":
            _add_field(requirement, condition.expected_field)


def _add_display_field(requirement: FieldRequirement, display_field: str | None) -> None:
    if display_field:
        _add_field(requirement, display_field)


def _add_field(requirement: FieldRequirement, field_name: str | None) -> None:
    normalized = (field_name or "").strip()
    if not normalized:
        return
    if normalized == "__key__":
        requirement.uses_key = True
        return
    requirement.fields.add(field_name or normalized)


def _merge_rule_requirements(
    rule_requirements: Any,
) -> dict[str, FieldRequirement]:
    merged: dict[str, FieldRequirement] = {}
    for requirements in rule_requirements:
        for tag, requirement in requirements.items():
            if tag not in merged:
                merged[tag] = FieldRequirement()
            merged[tag].merge(requirement)
    return merged


def _collect_rule_blocking_reasons(
    *,
    requirements: dict[str, FieldRequirement],
    personal_variable_map: dict[str, VariableTag],
    variable_mappings: dict[str, VariableMapping],
) -> list[str]:
    reasons: list[str] = []
    for tag in sorted(requirements):
        if tag not in personal_variable_map:
            reasons.append(f"缺少个人变量“{tag}”")
            continue
        mapping = variable_mappings.get(tag)
        if mapping is None or mapping.status != "ready":
            reasons.append(mapping.issue if mapping else f"变量“{tag}”无法映射")
    return _unique_strings(reason for reason in reasons if reason)


def _build_mapped_rule(
    *,
    rule: FixedRuleDefinition,
    requirements: dict[str, FieldRequirement],
    variable_mappings: dict[str, VariableMapping],
    group_id: str,
) -> FixedRuleDefinition:
    payload = rule.model_dump(mode="json", exclude_none=True)
    payload["rule_id"] = _new_entity_id("import-rule")
    payload["group_id"] = group_id

    def tag_map(tag: str | None) -> str | None:
        if not tag:
            return tag
        mapping = variable_mappings.get(tag)
        return mapping.final_tag if mapping and mapping.final_tag else tag

    def field_map(tag: str | None) -> dict[str, str]:
        if not tag:
            return {"__key__": "__key__"}
        mapping = variable_mappings.get(tag)
        return mapping.field_map if mapping else {"__key__": "__key__"}

    original_target_tag = rule.target_variable_tag
    original_reference_tag = rule.reference_variable_tag
    payload["target_variable_tag"] = tag_map(rule.target_variable_tag)
    if rule.reference_variable_tag:
        payload["reference_variable_tag"] = tag_map(rule.reference_variable_tag)

    if rule.display_field:
        payload["display_field"] = _map_field(rule.display_field, field_map(original_target_tag))

    if payload.get("composite_config"):
        _map_composite_config(payload["composite_config"], field_map(original_target_tag))
    if rule.rule_type == "dual_composite_compare":
        left_map = field_map(original_target_tag)
        right_map = field_map(original_reference_tag)
        payload["left_key_field"] = _map_field(payload.get("left_key_field") or "__key__", left_map)
        payload["right_key_field"] = _map_field(payload.get("right_key_field") or "__key__", right_map)
        for condition in payload.get("left_filters", []):
            _map_condition(condition, left_map)
        for condition in payload.get("right_filters", []):
            _map_condition(condition, right_map)
        for comparison in payload.get("comparisons", []):
            comparison["left_field"] = _map_field(comparison.get("left_field"), left_map)
            comparison["right_field"] = _map_field(comparison.get("right_field"), right_map)
    if payload.get("pipeline_config"):
        for node in payload["pipeline_config"].get("nodes", []):
            node_original_tag = node.get("variable_tag")
            node_map = field_map(node_original_tag)
            node["variable_tag"] = tag_map(node_original_tag)
            if node.get("display_field"):
                node["display_field"] = _map_field(node.get("display_field"), node_map)
            for condition in node.get("filters", []):
                _map_condition(condition, node_map)
            for condition in node.get("assertions", []):
                _map_condition(condition, node_map)
    if payload.get("mapping_config"):
        for node in payload["mapping_config"].get("nodes", []):
            node_original_tag = node.get("variable_tag")
            node_map = field_map(node_original_tag)
            node["variable_tag"] = tag_map(node_original_tag)
            if node.get("display_field"):
                node["display_field"] = _map_field(node.get("display_field"), node_map)
            for condition in node.get("filters", []):
                _map_condition(condition, node_map)

    # Ensure target tag follows the first node after node-driven remapping.
    if rule.rule_type == "multi_composite_pipeline_check":
        nodes = payload.get("pipeline_config", {}).get("nodes", [])
        if nodes:
            payload["target_variable_tag"] = nodes[0].get("variable_tag")
    if rule.rule_type == "multi_composite_mapping_check":
        nodes = payload.get("mapping_config", {}).get("nodes", [])
        if nodes:
            payload["target_variable_tag"] = nodes[0].get("variable_tag")

    return FixedRuleDefinition.model_validate(payload)


def _map_composite_config(payload: dict[str, Any], fields: dict[str, str]) -> None:
    for condition in payload.get("global_filters", []):
        _map_condition(condition, fields)
    for branch in payload.get("branches", []):
        for condition in branch.get("filters", []):
            _map_condition(condition, fields)
        for condition in branch.get("assertions", []):
            _map_condition(condition, fields)


def _map_condition(condition: dict[str, Any], fields: dict[str, str]) -> None:
    condition["field"] = _map_field(condition.get("field"), fields)
    if condition.get("value_source") == "field":
        condition["expected_field"] = _map_field(condition.get("expected_field"), fields)


def _map_field(field_name: str | None, fields: dict[str, str]) -> str:
    if not field_name:
        return ""
    if field_name == "__key__":
        return "__key__"
    return fields.get(field_name, fields.get(field_name.strip(), field_name))


def _validate_candidate_rule(
    *,
    project_config: FixedRulesConfig,
    sources_to_add: list[DataSource],
    variables_to_add: list[VariableTag],
    groups_to_add: list[FixedRuleGroup],
    candidate_rule: FixedRuleDefinition,
) -> str | None:
    try:
        load_fixed_rules_config_with_issues(
            FixedRulesConfig(
                version=6,
                configured=True,
                sources=[*project_config.sources, *sources_to_add],
                variables=[*project_config.variables, *variables_to_add],
                groups=[*project_config.groups, *groups_to_add],
                rules=[*project_config.rules, candidate_rule],
                local_path_replacement_presets=project_config.local_path_replacement_presets,
                selected_local_path_replacement_preset=project_config.selected_local_path_replacement_preset,
                svn_path_replacement_presets=project_config.svn_path_replacement_presets,
                selected_svn_path_replacement_preset=project_config.selected_svn_path_replacement_preset,
            ),
            allow_legacy_mapping_config=True,
            allow_unsupported_csv=False,
        )
    except (FileNotFoundError, ValueError, ImportError) as exc:
        return str(exc)
    return None


def _build_preview_response(
    *,
    selected_rule_ids: list[str],
    source_overrides: dict[str, DataSource],
    variable_tag_overrides: dict[str, str],
    source_mappings: dict[str, SourceMapping],
    variable_mappings: dict[str, VariableMapping],
    rule_candidates: list[RuleImportCandidate],
) -> dict[str, Any]:
    summary = {
        "total": len(rule_candidates),
        "ready": sum(1 for item in rule_candidates if item.status == "ready"),
        "duplicate": sum(1 for item in rule_candidates if item.status == "duplicate"),
        "skipped": sum(1 for item in rule_candidates if item.status == "skipped"),
    }
    token_payload = {
        "selected_rule_ids": selected_rule_ids,
        "source_overrides": {
            key: value.model_dump(mode="json", exclude_none=True)
            for key, value in sorted(source_overrides.items())
        },
        "variable_tag_overrides": {
            key: value for key, value in sorted(variable_tag_overrides.items())
        },
    }
    preview_token = hashlib.sha256(
        json.dumps(token_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {
        "preview_token": preview_token,
        "summary": summary,
        "sources": [_source_mapping_to_dict(item) for item in source_mappings.values()],
        "variables": [_variable_mapping_to_dict(item) for item in variable_mappings.values()],
        "rules": [_rule_candidate_to_dict(item) for item in rule_candidates],
    }


def _source_mapping_to_dict(mapping: SourceMapping) -> dict[str, Any]:
    return {
        "personal_source_id": mapping.personal_source_id,
        "status": mapping.status,
        "mode": mapping.mode,
        "project_source_id": mapping.project_source_id,
        "issue": mapping.issue,
        "personal_source": mapping.personal_source.model_dump(mode="json", exclude_none=True)
        if mapping.personal_source
        else None,
        "final_source": mapping.final_source.model_dump(mode="json", exclude_none=True)
        if mapping.final_source
        else None,
        "metadata": mapping.metadata,
    }


def _variable_mapping_to_dict(mapping: VariableMapping) -> dict[str, Any]:
    return {
        "personal_tag": mapping.personal_tag,
        "status": mapping.status,
        "mode": mapping.mode,
        "final_tag": mapping.final_tag,
        "issue": mapping.issue,
        "override_tag": mapping.override_tag,
        "suggested_tag": mapping.suggested_tag,
        "can_rename": mapping.can_rename,
        "issue_code": mapping.issue_code,
        "field_map": mapping.field_map,
        "variable_to_add": mapping.variable_to_add.model_dump(mode="json", exclude_none=True)
        if mapping.variable_to_add
        else None,
    }


def _rule_candidate_to_dict(candidate: RuleImportCandidate) -> dict[str, Any]:
    return {
        "rule_id": candidate.rule_id,
        "rule_name": candidate.rule_name,
        "status": candidate.status,
        "reason": candidate.reason,
        "required_tags": candidate.required_tags,
        "candidate_rule": candidate.candidate_rule.model_dump(mode="json", exclude_none=True)
        if candidate.candidate_rule
        else None,
    }


def _fingerprint_rule(rule: FixedRuleDefinition) -> str:
    normalized = _normalize_fingerprint_value(
        rule.model_dump(mode="json", exclude_none=True)
    )
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True)


def _normalize_fingerprint_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, list):
        return sorted(
            (
                normalized
                for item in value
                if (normalized := _normalize_fingerprint_value(item)) is not None
            ),
            key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True),
        )
    if isinstance(value, dict):
        return {
            key: normalized
            for key, item in sorted(value.items())
            if key not in GENERATED_FINGERPRINT_KEYS
            and (normalized := _normalize_fingerprint_value(item)) is not None
        }
    return str(value).strip()


def _get_primary_rule_target_tag(rule: FixedRuleDefinition) -> str:
    if rule.rule_type == "multi_composite_pipeline_check" and rule.pipeline_config:
        return rule.pipeline_config.nodes[0].variable_tag if rule.pipeline_config.nodes else ""
    if rule.rule_type == "multi_composite_mapping_check" and rule.mapping_config:
        return rule.mapping_config.nodes[0].variable_tag if rule.mapping_config.nodes else ""
    return rule.target_variable_tag or ""


def _read_metadata_safely(source: DataSource) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return read_source_metadata(source), None
    except (FileNotFoundError, ValueError, ImportError) as exc:
        return None, str(exc)


def _find_project_sources_by_basename(
    project_sources: list[DataSource],
    personal_source: DataSource,
) -> list[DataSource]:
    basename = _source_basename(personal_source)
    if not basename:
        return []
    return [
        source
        for source in project_sources
        if source.type == personal_source.type and _source_basename(source).lower() == basename.lower()
    ]


def _source_basename(source: DataSource) -> str:
    locator = (source.pathOrUrl or source.path or source.url or "").strip()
    if not locator:
        return ""
    parsed = urlparse(locator)
    path = parsed.path if parsed.scheme else locator
    normalized = path.replace("\\", "/").rstrip("/")
    return normalized.rsplit("/", 1)[-1]


def _is_same_source_locator(left: DataSource, right: DataSource) -> bool:
    return (
        left.type == right.type
        and _normalize_locator(left) == _normalize_locator(right)
    )


def _normalize_locator(source: DataSource) -> str:
    return (source.pathOrUrl or source.path or source.url or "").strip().replace("\\", "/").lower()


def _resolve_identifier(
    requested_value: str,
    available_values: list[str],
    *,
    label: str,
    context: str,
) -> str:
    if requested_value in available_values:
        return requested_value
    normalized_requested = (requested_value or "").strip()
    if not normalized_requested:
        raise ValueError(f"{context}缺少{label}。")
    matched_values = [
        candidate
        for candidate in available_values
        if candidate.strip() == normalized_requested
    ]
    if len(matched_values) == 1:
        return matched_values[0]
    if len(matched_values) > 1:
        raise ValueError(
            f"{context}中的{label}“{requested_value}”在忽略首尾空白后匹配到多个候选。"
        )
    raise ValueError(f"{context}中未找到{label}“{requested_value}”。")


def _resolve_identifier_or_none(requested_value: str, available_values: list[str]) -> str | None:
    try:
        return _resolve_identifier(
            requested_value,
            available_values,
            label="字段",
            context="项目变量",
        )
    except ValueError:
        return None


def _get_sheet_columns(metadata: dict[str, Any], sheet_name: str) -> list[str]:
    for sheet in metadata.get("sheets", []):
        if sheet.get("name") == sheet_name:
            return [str(column) for column in sheet.get("columns", [])]
    return []


def _safe_resolve_column(
    column: str,
    metadata: dict[str, Any],
    sheet_name: str,
) -> str | None:
    try:
        resolved_sheet = _resolve_identifier(
            sheet_name,
            [str(sheet["name"]) for sheet in metadata.get("sheets", [])],
            label="Sheet",
            context="项目变量",
        )
        return _resolve_identifier(
            column,
            _get_sheet_columns(metadata, resolved_sheet),
            label="列名",
            context="项目变量",
        )
    except ValueError:
        return None


def _unique_sources(items: Any) -> list[DataSource]:
    result: list[DataSource] = []
    seen: set[str] = set()
    for item in items:
        if item is None or item.id in seen:
            continue
        result.append(item)
        seen.add(item.id)
    return result


def _unique_variables(items: Any) -> list[VariableTag]:
    result: list[VariableTag] = []
    seen: set[str] = set()
    for item in items:
        if item is None or item.tag in seen:
            continue
        result.append(item)
        seen.add(item.tag)
    return result


def _unique_strings(items: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = str(item or "")
        if not normalized or normalized in seen:
            continue
        result.append(normalized)
        seen.add(normalized)
    return result


def _suggest_import_tag(base_tag: str, unavailable_tags: set[str]) -> str:
    normalized = str(base_tag or "").strip() or "import_variable"
    wrapped = normalized.startswith("[") and normalized.endswith("]") and len(normalized) > 2
    stem = normalized[1:-1] if wrapped else normalized
    candidate = f"{stem}_import"
    suffix = 2
    while (f"[{candidate}]" if wrapped else candidate) in unavailable_tags:
        candidate = f"{stem}_import{suffix}"
        suffix += 1
    return f"[{candidate}]" if wrapped else candidate


def _new_entity_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}"

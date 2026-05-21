"""Preview builder for workbench-to-fixed-rules import."""

from __future__ import annotations

from backend.app.api.fixed_rules_schemas import FixedRulesConfig
from backend.app.api.schemas import DataSource, VariableTag
from backend.app.fixed_rules.config_loader import load_fixed_rules_config_with_issues
from backend.app.fixed_rules.importer.rule_mapper import (
    build_effective_scope,
    collect_rule_variable_tags,
    map_groups,
    map_rules,
    select_rules_by_scope,
)
from backend.app.fixed_rules.importer.schemas import (
    ImportItemResult,
    ImportSummary,
    VariablePreviewResult,
    WorkbenchImportPreview,
    WorkbenchImportPreviewRequest,
)
from backend.app.fixed_rules.importer.source_mapper import (
    make_unique_source_id,
    resolve_source_mappings,
    sources_same_definition,
)
from backend.app.fixed_rules.importer.variable_mapper import map_variables
from backend.app.loaders.local_reader import (
    preview_composite_variable,
    preview_source_column,
    read_source_metadata,
)


def build_import_preview(
    *,
    personal_config: FixedRulesConfig,
    project_config: FixedRulesConfig,
    request: WorkbenchImportPreviewRequest,
) -> WorkbenchImportPreview:
    """Build a non-persisted import preview."""
    blocking_errors: list[str] = []
    scope = build_effective_scope(request)
    blocking_errors.extend(_validate_scope(scope))

    selected_rules = select_rules_by_scope(personal_config.rules, scope)
    selected_rules, duplicate_skip_results = _split_duplicate_skipped_rules(
        selected_rules,
        project_config,
        request,
    )
    referenced_tags: set[str] = set()
    for rule in selected_rules:
        referenced_tags.update(collect_rule_variable_tags(rule))

    personal_variable_map = {variable.tag: variable for variable in personal_config.variables}
    selected_variables = [
        variable
        for tag, variable in personal_variable_map.items()
        if tag in referenced_tags
    ]
    selected_source_ids = {variable.source_id for variable in selected_variables}
    selected_sources = [
        source
        for source in personal_config.sources
        if source.id in selected_source_ids
    ]

    source_results: list[ImportItemResult] = []
    variable_previews: list[VariablePreviewResult] = []
    # 高风险同 ID 不同路径数据源默认采用 draft 推荐的 replace 映射，
    # 后续 metadata 校验仍会阻断不可读取或字段缺失的配置。

    resolved_sources, skipped_source_ids, conflicts = resolve_source_mappings(
        selected_sources,
        project_config.sources,
        request.source_mappings,
    )

    next_sources = list(project_config.sources)
    project_source_by_id = {source.id: source for source in project_config.sources}
    existing_source_ids = {source.id for source in next_sources}
    source_id_map: dict[str, str] = {}

    for personal_source in selected_sources:
        if personal_source.id in skipped_source_ids:
            source_results.append(
                ImportItemResult(
                    item_id=personal_source.id,
                    status="skipped",
                    message="数据源已按映射选择跳过。",
                )
            )
            continue

        mapped_source = resolved_sources.get(personal_source.id)
        if mapped_source is None:
            blocking_errors.append(f"数据源“{personal_source.id}”缺少有效映射。")
            source_results.append(
                ImportItemResult(
                    item_id=personal_source.id,
                    status="error",
                    message="数据源缺少有效映射。",
                )
            )
            continue

        existing_source = project_source_by_id.get(mapped_source.id)
        if existing_source and sources_same_definition(mapped_source, existing_source):
            source_id_map[personal_source.id] = existing_source.id
            source_results.append(
                ImportItemResult(
                    item_id=personal_source.id,
                    status="reuse",
                    message="复用项目已有数据源。",
                    next_id=existing_source.id,
                )
            )
            continue

        next_source_id = make_unique_source_id(mapped_source.id, existing_source_ids)
        imported_source = mapped_source.model_copy(update={"id": next_source_id})
        existing_source_ids.add(next_source_id)
        source_id_map[personal_source.id] = next_source_id
        next_sources.append(imported_source)
        source_results.append(
            ImportItemResult(
                item_id=personal_source.id,
                status="new",
                message="新增数据源。" if next_source_id == mapped_source.id else "新增数据源并重命名 ID。",
                next_id=next_source_id,
            )
        )

    next_source_by_id = {source.id: source for source in next_sources}
    imported_variables, tag_map, variable_results, variable_conflicts, skipped_tags = map_variables(
        selected_variables,
        project_config.variables,
        source_id_map=source_id_map,
        skipped_source_ids=skipped_source_ids,
        tag_resolutions=request.conflict_resolutions.variable_tags,
    )
    conflicts.extend(variable_conflicts)

    preview_failed_tags = _validate_variable_previews(
        imported_variables,
        next_source_by_id,
        variable_previews,
        blocking_errors,
    )
    skipped_tags.update(preview_failed_tags)

    imported_groups, group_id_map, group_results = map_groups(
        selected_rules,
        personal_config.groups,
        project_config.groups,
        group_name_resolutions=request.conflict_resolutions.group_names,
    )
    imported_rules, mapped_rule_results, rule_conflicts, _ = map_rules(
        selected_rules,
        project_config.rules,
        group_id_map=group_id_map,
        tag_map=tag_map,
        skipped_tags=skipped_tags,
        rule_name_resolutions=request.conflict_resolutions.rule_names,
        duplicate_rule_actions=request.duplicate_rule_actions,
    )
    rule_results = [*duplicate_skip_results, *mapped_rule_results]
    conflicts.extend(rule_conflicts)

    next_config = FixedRulesConfig(
        version=6,
        configured=True,
        sources=next_sources,
        variables=[*project_config.variables, *imported_variables],
        groups=[*project_config.groups, *imported_groups],
        rules=[*project_config.rules, *imported_rules],
        local_path_replacement_presets=project_config.local_path_replacement_presets,
        selected_local_path_replacement_preset=project_config.selected_local_path_replacement_preset,
        svn_path_replacement_presets=project_config.svn_path_replacement_presets,
        selected_svn_path_replacement_preset=project_config.selected_svn_path_replacement_preset,
    )

    try:
        next_config, _ = load_fixed_rules_config_with_issues(
            next_config,
            allow_unsupported_csv=False,
        )
    except (FileNotFoundError, ValueError, ImportError) as exc:
        blocking_errors.append(str(exc))

    blocking_errors.extend(conflict.message for conflict in conflicts if conflict.level == "error")
    summary = _build_summary(
        source_results=source_results,
        variable_results=variable_results,
        group_results=group_results,
        rule_results=rule_results,
        blocking_error_count=len(blocking_errors),
    )

    return WorkbenchImportPreview(
        summary=summary,
        source_results=source_results,
        variable_results=variable_results,
        group_results=group_results,
        rule_results=rule_results,
        variable_previews=variable_previews,
        conflicts=conflicts,
        blocking_errors=blocking_errors,
        next_config_preview=next_config,
    )


def _validate_scope(scope) -> list[str]:
    if scope.mode == "groups" and not scope.group_ids:
        return ["按规则组导入时至少需要选择一个规则组。"]
    if scope.mode == "rules" and not scope.rule_ids:
        return ["按规则导入时至少需要选择一条规则。"]
    return []


def _split_duplicate_skipped_rules(
    selected_rules,
    project_config: FixedRulesConfig,
    request: WorkbenchImportPreviewRequest,
) -> tuple[list, list[ImportItemResult]]:
    """Remove duplicate rules explicitly marked as skipped before dependency mapping."""
    existing_rule_names = {rule.rule_name for rule in project_config.rules}
    active_rules = []
    skipped_results: list[ImportItemResult] = []
    for rule in selected_rules:
        requested_name = request.conflict_resolutions.rule_names.get(rule.rule_id, rule.rule_name).strip()
        rule_name = requested_name or rule.rule_name
        if rule_name in existing_rule_names and request.duplicate_rule_actions.get(rule.rule_id) == "skip":
            skipped_results.append(
                ImportItemResult(
                    item_id=rule.rule_id,
                    status="skipped",
                    message="项目校验已存在同名规则，已按选择跳过。",
                    details={
                        "rule_name": rule_name,
                        "duplicate_rule": True,
                        "duplicate_action": "skip",
                        "existing_rule_name": rule_name,
                    },
                )
            )
            continue
        active_rules.append(rule)
    return active_rules, skipped_results


def _validate_variable_previews(
    variables: list[VariableTag],
    source_by_id: dict[str, DataSource],
    preview_results: list[VariablePreviewResult],
    blocking_errors: list[str],
) -> set[str]:
    failed_tags: set[str] = set()
    metadata_cache: dict[str, dict] = {}

    for variable in variables:
        source = source_by_id.get(variable.source_id)
        if source is None:
            failed_tags.add(variable.tag)
            blocking_errors.append(f"变量“{variable.tag}”引用的数据源不存在。")
            continue
        try:
            if source.id not in metadata_cache:
                metadata_cache[source.id] = read_source_metadata(source)
            if (variable.variable_kind or "single") == "composite":
                preview = preview_composite_variable(
                    source,
                    sheet_name=variable.sheet,
                    columns=variable.columns or [],
                    key_column=variable.key_column or "",
                    append_index_to_key=variable.append_index_to_key,
                )
                status = "warning" if preview.get("has_duplicate_keys") else "ok"
                message = "存在重复 key 风险。" if status == "warning" else "组合变量预览通过。"
            else:
                preview = preview_source_column(
                    source,
                    sheet_name=variable.sheet,
                    column_name=variable.column or "",
                    limit=20,
                )
                empty_count = sum(
                    1
                    for row in preview.get("preview_rows", [])
                    if str(row.get("value", "")).strip() == ""
                )
                status = "warning" if empty_count else "ok"
                message = f"前 20 行存在 {empty_count} 个空值风险。" if empty_count else "单变量预览通过。"
            preview_results.append(
                VariablePreviewResult(
                    tag=variable.tag,
                    status=status,  # type: ignore[arg-type]
                    message=message,
                    preview=preview,
                )
            )
        except (FileNotFoundError, ValueError, ImportError) as exc:
            failed_tags.add(variable.tag)
            message = f"变量“{variable.tag}”预览失败：{exc}"
            blocking_errors.append(message)
            preview_results.append(
                VariablePreviewResult(
                    tag=variable.tag,
                    status="error",
                    message=message,
                    preview=None,
                )
            )

    return failed_tags


def _build_summary(
    *,
    source_results: list[ImportItemResult],
    variable_results: list[ImportItemResult],
    group_results: list[ImportItemResult],
    rule_results: list[ImportItemResult],
    blocking_error_count: int,
) -> ImportSummary:
    return ImportSummary(
        sources_new=sum(1 for item in source_results if item.status in {"new", "renamed"}),
        sources_reused=sum(1 for item in source_results if item.status == "reuse"),
        sources_skipped=sum(1 for item in source_results if item.status in {"skipped", "error"}),
        variables_new=sum(1 for item in variable_results if item.status in {"new", "renamed"}),
        variables_reused=sum(1 for item in variable_results if item.status == "reuse"),
        variables_skipped=sum(1 for item in variable_results if item.status in {"skipped", "error"}),
        groups_new=sum(1 for item in group_results if item.status in {"new", "renamed"}),
        groups_reused=sum(1 for item in group_results if item.status == "reuse"),
        rules_new=sum(1 for item in rule_results if item.status == "new"),
        rules_renamed=sum(1 for item in rule_results if item.status == "renamed"),
        rules_skipped=sum(1 for item in rule_results if item.status in {"skipped", "error"}),
        blocking_errors=blocking_error_count,
    )

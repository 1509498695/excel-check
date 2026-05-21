"""Rule and group mapping helpers for workbench-to-fixed-rules import."""

from __future__ import annotations

from copy import deepcopy

from backend.app.api.fixed_rules_schemas import FixedRuleDefinition, FixedRuleGroup, UNGROUPED_GROUP_ID
from backend.app.fixed_rules.config_common import _build_default_group
from backend.app.fixed_rules.importer.schemas import (
    ImportConflict,
    ImportItemResult,
    ImportScope,
    WorkbenchImportPreviewRequest,
)


def build_effective_scope(request: WorkbenchImportPreviewRequest) -> ImportScope:
    """Merge legacy scope payload with top-level selected ids."""
    if request.selected_rule_ids is not None:
        return ImportScope(mode="rules", rule_ids=request.selected_rule_ids)
    if request.selected_group_ids is not None:
        return ImportScope(mode="groups", group_ids=request.selected_group_ids)
    return request.scope


def select_rules_by_scope(
    rules: list[FixedRuleDefinition],
    scope: ImportScope,
) -> list[FixedRuleDefinition]:
    """Filter personal rules by import scope."""
    if scope.mode == "groups":
        selected_group_ids = set(scope.group_ids)
        return [rule for rule in rules if rule.group_id in selected_group_ids]
    if scope.mode == "rules":
        selected_rule_ids = set(scope.rule_ids)
        return [rule for rule in rules if rule.rule_id in selected_rule_ids]
    return list(rules)


def collect_rule_variable_tags(rule: FixedRuleDefinition) -> set[str]:
    """Collect all variable tags referenced by a fixed rule definition."""
    tags: set[str] = set()
    if rule.target_variable_tag:
        tags.add(rule.target_variable_tag)
    if rule.reference_variable_tag:
        tags.add(rule.reference_variable_tag)
    if rule.pipeline_config:
        tags.update(node.variable_tag for node in rule.pipeline_config.nodes if node.variable_tag)
    if rule.mapping_config:
        tags.update(node.variable_tag for node in rule.mapping_config.nodes if node.variable_tag)
    return tags


def remap_rule_variable_tags(
    rule: FixedRuleDefinition,
    tag_map: dict[str, str],
) -> FixedRuleDefinition:
    """Copy a rule and remap every supported variable tag reference."""
    next_rule = deepcopy(rule)
    if next_rule.target_variable_tag in tag_map:
        next_rule.target_variable_tag = tag_map[next_rule.target_variable_tag]
    if next_rule.reference_variable_tag in tag_map:
        next_rule.reference_variable_tag = tag_map[next_rule.reference_variable_tag]
    if next_rule.pipeline_config:
        for node in next_rule.pipeline_config.nodes:
            if node.variable_tag in tag_map:
                node.variable_tag = tag_map[node.variable_tag]
    if next_rule.mapping_config:
        for node in next_rule.mapping_config.nodes:
            if node.variable_tag in tag_map:
                node.variable_tag = tag_map[node.variable_tag]
    return next_rule


def map_groups(
    selected_rules: list[FixedRuleDefinition],
    personal_groups: list[FixedRuleGroup],
    project_groups: list[FixedRuleGroup],
    *,
    group_name_resolutions: dict[str, str],
) -> tuple[list[FixedRuleGroup], dict[str, str], list[ImportItemResult]]:
    """Map personal rule groups to project groups by group name."""
    personal_group_ids = {rule.group_id or UNGROUPED_GROUP_ID for rule in selected_rules}
    personal_by_id = {group.group_id: group for group in personal_groups}
    project_by_name = {group.group_name: group for group in project_groups}
    existing_ids = {group.group_id for group in project_groups}
    existing_names = {group.group_name for group in project_groups}
    imported_groups: list[FixedRuleGroup] = []
    group_id_map: dict[str, str] = {}
    results: list[ImportItemResult] = []

    for group_id in personal_group_ids:
        if group_id == UNGROUPED_GROUP_ID:
            group_id_map[group_id] = UNGROUPED_GROUP_ID
            results.append(
                ImportItemResult(
                    item_id=group_id,
                    status="reuse",
                    message="未分组规则映射到项目未分组。",
                    next_id=UNGROUPED_GROUP_ID,
                )
            )
            continue

        group = personal_by_id.get(group_id) or _build_default_group()
        has_resolution = group_id in group_name_resolutions
        group_name = group_name_resolutions.get(group_id, group.group_name).strip() or group.group_name
        existing = project_by_name.get(group_name)
        if existing and has_resolution:
            group_id_map[group_id] = existing.group_id
            results.append(
                ImportItemResult(
                    item_id=group_id,
                    status="reuse",
                    message="项目校验已存在同名规则组，复用。",
                    next_id=existing.group_id,
                )
            )
            continue
        if existing:
            group_name = make_unique_import_name(group_name, existing_names)

        next_group_id = make_unique_id(group.group_id, existing_ids, suffix="import")
        existing_ids.add(next_group_id)
        existing_names.add(group_name)
        group_id_map[group_id] = next_group_id
        imported_groups.append(
            FixedRuleGroup(
                group_id=next_group_id,
                group_name=group_name,
                builtin=False,
            )
        )
        results.append(
            ImportItemResult(
                item_id=group_id,
                status="new",
                message="规则组名称冲突，已自动追加“-导入”后缀。"
                if existing
                else "新增规则组。",
                next_id=next_group_id,
                details={"group_name": group_name},
            )
        )

    return imported_groups, group_id_map, results


def map_rules(
    selected_rules: list[FixedRuleDefinition],
    project_rules: list[FixedRuleDefinition],
    *,
    group_id_map: dict[str, str],
    tag_map: dict[str, str],
    skipped_tags: set[str],
    rule_name_resolutions: dict[str, str],
    duplicate_rule_actions: dict[str, str] | None = None,
) -> tuple[list[FixedRuleDefinition], list[ImportItemResult], list[ImportConflict], set[str]]:
    """Map selected personal rules into project config."""
    existing_rule_ids = {rule.rule_id for rule in project_rules}
    existing_rule_names = {rule.rule_name for rule in project_rules}
    imported_rules: list[FixedRuleDefinition] = []
    results: list[ImportItemResult] = []
    conflicts: list[ImportConflict] = []
    skipped_rule_ids: set[str] = set()
    duplicate_actions = duplicate_rule_actions or {}

    for rule in selected_rules:
        referenced_tags = collect_rule_variable_tags(rule)
        missing_tags = sorted(tag for tag in referenced_tags if tag in skipped_tags or tag not in tag_map)
        if missing_tags:
            skipped_rule_ids.add(rule.rule_id)
            message = f"规则引用的变量不可导入：{', '.join(missing_tags)}。"
            conflicts.append(
                ImportConflict(
                    kind="rule_variable_reference",
                    level="error",
                    item_id=rule.rule_id,
                    message=message,
                    candidates=missing_tags,
                )
            )
            results.append(
                ImportItemResult(
                    item_id=rule.rule_id,
                    status="error",
                    message=message,
                )
            )
            continue

        next_rule = remap_rule_variable_tags(rule, tag_map)
        next_rule.group_id = group_id_map.get(rule.group_id, UNGROUPED_GROUP_ID)
        requested_name = rule_name_resolutions.get(rule.rule_id, next_rule.rule_name).strip()
        next_rule.rule_name = requested_name or next_rule.rule_name
        is_duplicate_name = next_rule.rule_name in existing_rule_names
        duplicate_action = duplicate_actions.get(rule.rule_id, "rename")
        if is_duplicate_name and duplicate_action == "skip":
            skipped_rule_ids.add(rule.rule_id)
            results.append(
                ImportItemResult(
                    item_id=rule.rule_id,
                    status="skipped",
                    message="项目校验已存在同名规则，已按选择跳过。",
                    details={
                        "rule_name": next_rule.rule_name,
                        "duplicate_rule": True,
                        "duplicate_action": "skip",
                        "existing_rule_name": next_rule.rule_name,
                    },
                )
            )
            continue

        next_rule.rule_id = make_unique_id(rule.rule_id, existing_rule_ids, suffix="import")
        existing_rule_ids.add(next_rule.rule_id)

        status: str = "new"
        message = "新增规则。"
        details = {"rule_name": next_rule.rule_name}
        if is_duplicate_name:
            original_rule_name = next_rule.rule_name
            next_rule.rule_name = make_unique_rule_name(next_rule.rule_name, existing_rule_names)
            status = "renamed"
            message = "规则名称冲突，已追加“导入”后缀。"
            details.update(
                {
                    "rule_name": next_rule.rule_name,
                    "duplicate_rule": True,
                    "duplicate_action": "rename",
                    "existing_rule_name": original_rule_name,
                }
            )
        existing_rule_names.add(next_rule.rule_name)
        imported_rules.append(next_rule)
        results.append(
            ImportItemResult(
                item_id=rule.rule_id,
                status=status,  # type: ignore[arg-type]
                message=message,
                next_id=next_rule.rule_id,
                details=details,
            )
        )

    return imported_rules, results, conflicts, skipped_rule_ids


def make_unique_id(base_id: str, existing_ids: set[str], *, suffix: str) -> str:
    """Create a unique imported id."""
    normalized_base = base_id.strip() or "item"
    if normalized_base not in existing_ids:
        return normalized_base
    index = 2
    while f"{normalized_base}-{suffix}-{index}" in existing_ids:
        index += 1
    return f"{normalized_base}-{suffix}-{index}"


def make_unique_rule_name(rule_name: str, existing_names: set[str]) -> str:
    """Create a user-facing imported rule name without collisions."""
    return make_unique_import_name(rule_name, existing_names)


def make_unique_import_name(name: str, existing_names: set[str]) -> str:
    """Create a user-facing imported name with a -导入 suffix."""
    base_name = f"{name}-导入"
    if base_name not in existing_names:
        return base_name
    index = 2
    while f"{base_name}-{index}" in existing_names:
        index += 1
    return f"{base_name}-{index}"

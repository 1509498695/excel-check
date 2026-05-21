"""Source mapping helpers for workbench-to-fixed-rules import."""

from __future__ import annotations

from pathlib import PurePath

from backend.app.api.schemas import DataSource
from backend.app.fixed_rules.importer.schemas import (
    ImportConflict,
    SourceMapping,
    SourceMappingDraft,
)


def source_locator(source: DataSource) -> str:
    """Return the persisted path/url locator used for equality checks."""
    return (source.pathOrUrl or source.path or source.url or "").strip()


def source_basename(source: DataSource) -> str:
    """Return a comparable file name from local or SVN source locators."""
    locator = source_locator(source).rstrip("/\\")
    if not locator:
        return ""
    if "/" in locator:
        return locator.rsplit("/", 1)[-1].lower()
    return PurePath(locator).name.lower()


def sources_same_definition(left: DataSource, right: DataSource) -> bool:
    """Check whether two sources can be safely treated as the same input."""
    return left.type == right.type and source_locator(left).lower() == source_locator(right).lower()


def normalize_source_locator(source: DataSource) -> DataSource:
    """Keep path/pathOrUrl/url aligned after a user edits the import locator."""
    locator = source_locator(source)
    if not locator:
        return source
    if source.type == "feishu":
        return source.model_copy(update={"url": locator, "pathOrUrl": locator})
    return source.model_copy(update={"path": locator, "pathOrUrl": locator})


def build_source_mapping_drafts(
    personal_sources: list[DataSource],
    project_sources: list[DataSource],
) -> tuple[list[SourceMappingDraft], list[ImportConflict]]:
    """Build initial mapping recommendations shown by the import wizard."""
    project_by_id = {source.id: source for source in project_sources}
    drafts: list[SourceMappingDraft] = []
    conflicts: list[ImportConflict] = []

    for personal_source in personal_sources:
        same_id_source = project_by_id.get(personal_source.id)
        basename = source_basename(personal_source)
        basename_candidates = [
            source
            for source in project_sources
            if source.id != personal_source.id and basename and source_basename(source) == basename
        ]
        if same_id_source and sources_same_definition(personal_source, same_id_source):
            drafts.append(
                SourceMappingDraft(
                    personal_source=personal_source,
                    recommended_action="reuse",
                    project_source_id=same_id_source.id,
                    reason="项目校验已存在同 ID 且路径一致的数据源，建议复用。",
                    candidates=basename_candidates,
                )
            )
            continue

        if same_id_source:
            conflicts.append(
                ImportConflict(
                    kind="source_id_path",
                    level="warning",
                    item_id=personal_source.id,
                    message="项目校验已存在同 ID 但路径或 URL 不同的数据源，需要选择复用、修改后新建或跳过。",
                    candidates=[same_id_source.id],
                )
            )
            drafts.append(
                SourceMappingDraft(
                    personal_source=personal_source,
                    recommended_action="replace",
                    project_source_id=same_id_source.id,
                    next_source=personal_source,
                    reason="同 ID 数据源路径不同，默认建议修改路径/URL 后作为导入来源。",
                    candidates=[same_id_source, *basename_candidates],
                    requires_confirmation=True,
                )
            )
            continue

        drafts.append(
            SourceMappingDraft(
                personal_source=personal_source,
                recommended_action="new",
                next_source=personal_source,
                reason="项目校验中不存在同 ID 数据源，建议新增。",
                candidates=basename_candidates,
            )
        )
        if basename_candidates:
            conflicts.append(
                ImportConflict(
                    kind="source_basename_candidate",
                    level="info",
                    item_id=personal_source.id,
                    message="项目校验中存在文件名相同但 ID 不同的数据源，可按需手动选择复用。",
                    candidates=[source.id for source in basename_candidates],
                )
            )

    return drafts, conflicts


def resolve_source_mappings(
    personal_sources: list[DataSource],
    project_sources: list[DataSource],
    mappings: list[SourceMapping],
) -> tuple[dict[str, DataSource], set[str], list[ImportConflict]]:
    """Resolve request mappings to concrete imported or reused project sources."""
    project_by_id = {source.id: source for source in project_sources}
    personal_by_id = {source.id: source for source in personal_sources}
    mapping_by_id = {mapping.personal_source_id: mapping for mapping in mappings}
    drafts, draft_conflicts = build_source_mapping_drafts(personal_sources, project_sources)
    default_by_id = {
        draft.personal_source.id: SourceMapping(
            personal_source_id=draft.personal_source.id,
            action=draft.recommended_action,
            project_source_id=draft.project_source_id,
            next_source=draft.next_source,
        )
        for draft in drafts
    }

    resolved: dict[str, DataSource] = {}
    skipped: set[str] = set()
    conflicts: list[ImportConflict] = [*draft_conflicts]

    for personal_id, personal_source in personal_by_id.items():
        mapping = mapping_by_id.get(personal_id) or default_by_id[personal_id]
        if mapping.action == "skip":
            skipped.add(personal_id)
            continue
        if mapping.action == "reuse":
            project_id = (mapping.project_source_id or "").strip()
            project_source = project_by_id.get(project_id)
            if project_source is None:
                conflicts.append(
                    ImportConflict(
                        kind="source_mapping",
                        level="error",
                        item_id=personal_id,
                        message=f"数据源“{personal_id}”选择复用，但项目数据源“{project_id}”不存在。",
                    )
                )
                skipped.add(personal_id)
                continue
            resolved[personal_id] = project_source
            continue

        next_source = normalize_source_locator(mapping.next_source or personal_source)
        if not source_locator(next_source):
            conflicts.append(
                ImportConflict(
                    kind="source_mapping",
                    level="error",
                    item_id=personal_id,
                    message=f"数据源“{personal_id}”缺少导入路径或 URL。",
                )
            )
            skipped.add(personal_id)
            continue
        resolved[personal_id] = next_source

    return resolved, skipped, conflicts


def make_unique_source_id(source_id: str, existing_ids: set[str]) -> str:
    """Generate a stable import source id without overwriting project sources."""
    base_id = source_id.strip() or "source"
    if base_id not in existing_ids:
        return base_id
    index = 2
    while f"{base_id}-import-{index}" in existing_ids:
        index += 1
    return f"{base_id}-import-{index}"

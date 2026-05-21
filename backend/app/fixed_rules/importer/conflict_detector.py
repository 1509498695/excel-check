"""Conflict detector facade for workbench-to-fixed-rules import."""

from __future__ import annotations

from backend.app.api.fixed_rules_schemas import FixedRulesConfig
from backend.app.fixed_rules.importer.schemas import ImportConflict
from backend.app.fixed_rules.importer.source_mapper import build_source_mapping_drafts


def detect_initial_conflicts(
    personal_config: FixedRulesConfig,
    project_config: FixedRulesConfig,
) -> list[ImportConflict]:
    """Return source-level initial conflicts and recommendations."""
    _, conflicts = build_source_mapping_drafts(
        personal_config.sources,
        project_config.sources,
    )
    return conflicts

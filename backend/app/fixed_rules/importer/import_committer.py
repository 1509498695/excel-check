"""Commit helper for workbench-to-fixed-rules import."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.fixed_rules.db_service import save_fixed_rules_config_to_db
from backend.app.fixed_rules.importer.import_preview import build_import_preview
from backend.app.fixed_rules.importer.schemas import (
    WorkbenchImportCommitResult,
    WorkbenchImportPreviewRequest,
)
from backend.app.api.fixed_rules_schemas import FixedRulesConfig


async def commit_import_preview(
    *,
    db: AsyncSession,
    project_id: int,
    personal_config: FixedRulesConfig,
    project_config: FixedRulesConfig,
    request: WorkbenchImportPreviewRequest,
) -> WorkbenchImportCommitResult:
    """Rebuild preview, validate it, then persist the merged fixed-rules config."""
    preview = build_import_preview(
        personal_config=personal_config,
        project_config=project_config,
        request=request,
    )
    if preview.blocking_errors:
        raise ValueError("\n".join(preview.blocking_errors))

    await save_fixed_rules_config_to_db(
        db,
        project_id,
        preview.next_config_preview.model_dump(mode="json", exclude_none=True),
    )
    return WorkbenchImportCommitResult(
        config=preview.next_config_preview,
        import_summary=preview.summary,
        source_results=preview.source_results,
        variable_results=preview.variable_results,
        group_results=preview.group_results,
        rule_results=preview.rule_results,
    )

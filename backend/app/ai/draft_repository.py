"""Persistence helpers for AI rule draft history."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.ai.schemas import RuleDraftResponse
from backend.app.models import AiRuleDraftRecord


DRAFT_HISTORY_LIMIT = 20


async def list_rule_drafts(
    *,
    db: AsyncSession,
    project_id: int,
    user_id: int,
    limit: int = DRAFT_HISTORY_LIMIT,
) -> list[RuleDraftResponse]:
    """读取当前用户当前项目最近的 AI 草稿历史。"""
    normalized_limit = max(1, min(DRAFT_HISTORY_LIMIT, limit))
    result = await db.execute(
        select(AiRuleDraftRecord)
        .where(
            AiRuleDraftRecord.project_id == project_id,
            AiRuleDraftRecord.user_id == user_id,
        )
        .order_by(AiRuleDraftRecord.created_at.desc(), AiRuleDraftRecord.id.desc())
        .limit(normalized_limit)
    )
    records = result.scalars().all()
    items: list[RuleDraftResponse] = []
    for record in records:
        try:
            payload = json.loads(record.response_json)
            item = RuleDraftResponse.model_validate(payload)
        except (json.JSONDecodeError, ValidationError):
            item = RuleDraftResponse(
                verdict=record.verdict,  # type: ignore[arg-type]
                rule_type=record.rule_type,  # type: ignore[arg-type]
                reasoning_summary="历史草稿格式已过期，无法完整展示。",
                rejection_reason="历史草稿格式已过期。",
            )
        item.draft_id = record.id
        item.description = record.description
        item.applied = record.applied
        item.created_at = _format_dt(record.created_at)
        items.append(item)
    return items


async def mark_draft_applied(
    *,
    db: AsyncSession,
    project_id: int,
    user_id: int,
    draft_id: int,
) -> bool:
    """把某条草稿标记为已应用。"""
    record = await get_owned_draft(db, project_id, user_id, draft_id)
    if record is None:
        return False
    record.applied = True
    record.applied_at = datetime.now(timezone.utc)
    db.add(record)
    await db.commit()
    return True


async def delete_draft(
    *,
    db: AsyncSession,
    project_id: int,
    user_id: int,
    draft_id: int,
) -> bool:
    """删除某条草稿历史。"""
    record = await get_owned_draft(db, project_id, user_id, draft_id)
    if record is None:
        return False
    await db.delete(record)
    await db.commit()
    return True


async def clear_drafts(
    *,
    db: AsyncSession,
    project_id: int,
    user_id: int,
) -> int:
    """清空当前用户当前项目草稿历史。"""
    result = await db.execute(
        delete(AiRuleDraftRecord).where(
            AiRuleDraftRecord.project_id == project_id,
            AiRuleDraftRecord.user_id == user_id,
        )
    )
    await db.commit()
    return int(result.rowcount or 0)


async def persist_draft_history(
    db: AsyncSession,
    *,
    project_id: int,
    user_id: int,
    description: str,
    response: RuleDraftResponse,
) -> AiRuleDraftRecord:
    """Persist one AI draft response and enforce the per-user history limit."""
    record = AiRuleDraftRecord(
        project_id=project_id,
        user_id=user_id,
        description=description,
        verdict=response.verdict,
        rule_type=response.rule_type,
        response_json=response.model_dump_json(exclude={"draft_id", "created_at"}),
        applied=response.applied,
    )
    db.add(record)
    await db.flush()
    await trim_draft_history(db, project_id=project_id, user_id=user_id)
    await db.commit()
    await db.refresh(record)
    return record


async def trim_draft_history(db: AsyncSession, *, project_id: int, user_id: int) -> None:
    """Delete stale draft history records beyond the configured limit."""
    result = await db.execute(
        select(AiRuleDraftRecord.id)
        .where(
            AiRuleDraftRecord.project_id == project_id,
            AiRuleDraftRecord.user_id == user_id,
        )
        .order_by(AiRuleDraftRecord.created_at.desc(), AiRuleDraftRecord.id.desc())
        .offset(DRAFT_HISTORY_LIMIT)
    )
    stale_ids = [row[0] for row in result.all()]
    if stale_ids:
        await db.execute(delete(AiRuleDraftRecord).where(AiRuleDraftRecord.id.in_(stale_ids)))


async def get_owned_draft(
    db: AsyncSession,
    project_id: int,
    user_id: int,
    draft_id: int,
) -> AiRuleDraftRecord | None:
    """Return one draft if it belongs to the current project and user."""
    result = await db.execute(
        select(AiRuleDraftRecord).where(
            AiRuleDraftRecord.id == draft_id,
            AiRuleDraftRecord.project_id == project_id,
            AiRuleDraftRecord.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


def _format_dt(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None

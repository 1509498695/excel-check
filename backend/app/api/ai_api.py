"""AI 规则助手接口。"""

from __future__ import annotations

import json
import time
from collections import defaultdict, deque
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.ai.agent_service import (
    AiProviderInvalid,
    AiProviderNotConfigured,
    clear_drafts,
    delete_draft,
    generate_rule_draft,
    list_rule_drafts,
    mark_draft_applied,
    optimize_rule_prompt,
)
from backend.app.ai.providers import (
    ProviderConnectionError,
    get_provider_protocol,
    mask_api_key,
    resolve_provider_defaults,
    test_provider_connection,
)
from backend.app.ai.schemas import (
    AiProviderConfigIn,
    AiProviderConfigOut,
    AiProviderTestResult,
    RulePromptOptimizeRequest,
    RuleDraftRequest,
)
from backend.app.auth.dependencies import CurrentUserContext, get_current_user
from backend.app.database import get_db
from backend.app.models import AiProviderCredentialRecord
from backend.app.security.crypto import decrypt_secret, encrypt_secret


router = APIRouter(prefix="/ai", tags=["ai"])

_RATE_LIMIT_WINDOW_SECONDS = 60
_RATE_LIMIT_MAX_CALLS = 10
_draft_call_times: dict[int, deque[float]] = defaultdict(deque)


def _enforce_rule_draft_rate_limit(user_id: int) -> None:
    """简易内存速率限制，避免单用户短时间刷 token。"""
    now = time.monotonic()
    bucket = _draft_call_times[user_id]
    while bucket and now - bucket[0] > _RATE_LIMIT_WINDOW_SECONDS:
        bucket.popleft()
    if len(bucket) >= _RATE_LIMIT_MAX_CALLS:
        raise HTTPException(status_code=429, detail="调用过于频繁，请稍后再试。")
    bucket.append(now)


@router.get("/providers/me")
async def get_my_ai_provider(
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """读取当前用户的 AI 配置，不返回明文 API Key。"""
    result = await db.execute(
        select(AiProviderCredentialRecord).where(
            AiProviderCredentialRecord.user_id == ctx.user_id
        )
    )
    record = result.scalar_one_or_none()
    return {"code": 200, "msg": "ok", "data": _provider_out(record) if record else None}


@router.put("/providers/me")
async def save_my_ai_provider(
    payload: AiProviderConfigIn,
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """保存当前用户 AI 配置；API Key 为空时保留旧密文。"""
    base_url, model = resolve_provider_defaults(
        payload.provider_preset,
        payload.base_url,
        payload.model,
    )
    if not base_url or not model:
        raise HTTPException(status_code=400, detail="请填写 Base URL 和模型名称。")

    result = await db.execute(
        select(AiProviderCredentialRecord).where(
            AiProviderCredentialRecord.user_id == ctx.user_id
        )
    )
    record = result.scalar_one_or_none()
    if record is None and not payload.api_key:
        raise HTTPException(status_code=400, detail="首次保存 AI 配置时必须填写 API Key。")

    encrypted_key = record.encrypted_api_key if record else ""
    if payload.api_key:
        encrypted_key = encrypt_secret(payload.api_key)

    extra_headers_json = json.dumps(payload.extra_headers, ensure_ascii=False)
    if record is None:
        record = AiProviderCredentialRecord(
            user_id=ctx.user_id,
            provider_preset=payload.provider_preset,
            base_url=base_url,
            model=model,
            encrypted_api_key=encrypted_key,
            extra_headers_json=extra_headers_json,
        )
    else:
        record.provider_preset = payload.provider_preset
        record.base_url = base_url
        record.model = model
        record.encrypted_api_key = encrypted_key
        record.extra_headers_json = extra_headers_json

    db.add(record)
    await db.commit()
    await db.refresh(record)
    return {"code": 200, "msg": "ok", "data": _provider_out(record)}


@router.delete("/providers/me")
async def delete_my_ai_provider(
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """删除当前用户 AI 配置。"""
    result = await db.execute(
        select(AiProviderCredentialRecord).where(
            AiProviderCredentialRecord.user_id == ctx.user_id
        )
    )
    record = result.scalar_one_or_none()
    if record is not None:
        await db.delete(record)
        await db.commit()
    return {"code": 200, "msg": "ok"}


@router.post("/providers/test")
async def test_ai_provider(
    payload: AiProviderConfigIn,
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """测试 AI 配置连通性，不落库。"""
    base_url, model = resolve_provider_defaults(
        payload.provider_preset,
        payload.base_url,
        payload.model,
    )
    api_key = await _resolve_provider_test_api_key(payload, ctx, db)
    try:
        latency_ms = await test_provider_connection(
            provider_preset=payload.provider_preset,
            base_url=base_url,
            model=model,
            api_key=api_key,
            extra_headers=payload.extra_headers,
        )
    except ProviderConnectionError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.status_code, "msg": exc.message, "category": exc.category},
        ) from exc

    return {
        "code": 200,
        "msg": "ok",
        "data": AiProviderTestResult(ok=True, latency_ms=latency_ms).model_dump(),
    }


@router.post("/agents/rule-draft")
async def create_rule_draft(
    payload: RuleDraftRequest,
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """根据自然语言描述生成个人校验规则草稿。"""
    project_id = ctx.require_project_member()
    _enforce_rule_draft_rate_limit(ctx.user_id)
    try:
        draft = await generate_rule_draft(
            db=db,
            project_id=project_id,
            user_id=ctx.user_id,
            description=payload.description,
            extra_hints=payload.extra_hints,
            workflow_hints=payload.workflow_hints,
            input_mode=payload.input_mode,
            allow_auto_complete=payload.allow_auto_complete,
            selected_variable_tags=payload.selected_variable_tags,
        )
    except AiProviderNotConfigured as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AiProviderInvalid as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"code": 200, "msg": "ok", "data": draft.model_dump()}


@router.post("/agents/rule-prompt-optimize")
async def optimize_rule_prompt_input(
    payload: RulePromptOptimizeRequest,
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """优化智能添加规则的自然语言描述，不生成草稿、不保存规则。"""
    project_id = ctx.require_project_member()
    _enforce_rule_draft_rate_limit(ctx.user_id)
    result = await optimize_rule_prompt(
        db=db,
        project_id=project_id,
        user_id=ctx.user_id,
        raw_description=payload.raw_description,
        selected_variable_tags=payload.selected_variable_tags,
        allow_auto_complete=payload.allow_auto_complete,
        context=payload.context,
    )
    return {"code": 200, "msg": "ok", "data": result.model_dump()}


@router.get("/drafts")
async def get_rule_drafts(
    limit: int = Query(default=20, ge=1, le=20),
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """读取当前用户当前项目的 AI 草稿历史。"""
    project_id = ctx.require_project_member()
    items = await list_rule_drafts(
        db=db,
        project_id=project_id,
        user_id=ctx.user_id,
        limit=limit,
    )
    return {
        "code": 200,
        "msg": "ok",
        "data": {"items": [item.model_dump() for item in items], "total": len(items)},
    }


@router.delete("/drafts/{draft_id}")
async def delete_rule_draft(
    draft_id: int,
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """删除某条 AI 草稿历史。"""
    project_id = ctx.require_project_member()
    deleted = await delete_draft(
        db=db,
        project_id=project_id,
        user_id=ctx.user_id,
        draft_id=draft_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="未找到对应 AI 草稿。")
    return {"code": 200, "msg": "ok"}


@router.delete("/drafts")
async def clear_rule_drafts(
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """清空当前用户当前项目的 AI 草稿历史。"""
    project_id = ctx.require_project_member()
    deleted_count = await clear_drafts(db=db, project_id=project_id, user_id=ctx.user_id)
    return {"code": 200, "msg": "ok", "data": {"deleted": deleted_count}}


@router.post("/drafts/{draft_id}/apply")
async def mark_rule_draft_applied(
    draft_id: int,
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """标记某条 AI 草稿已被用户采用。"""
    project_id = ctx.require_project_member()
    updated = await mark_draft_applied(
        db=db,
        project_id=project_id,
        user_id=ctx.user_id,
        draft_id=draft_id,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="未找到对应 AI 草稿。")
    return {"code": 200, "msg": "ok"}


async def _resolve_provider_test_api_key(
    payload: AiProviderConfigIn,
    ctx: CurrentUserContext,
    db: AsyncSession,
) -> str:
    """测试连接时允许沿用已保存的个人 API Key。"""
    if payload.api_key:
        return payload.api_key

    result = await db.execute(
        select(AiProviderCredentialRecord).where(
            AiProviderCredentialRecord.user_id == ctx.user_id
        )
    )
    record = result.scalar_one_or_none()
    if record is None or not record.encrypted_api_key:
        raise HTTPException(status_code=400, detail="请填写 API Key 或重新保存 AI 配置。")

    try:
        api_key = decrypt_secret(record.encrypted_api_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="请填写 API Key 或重新保存 AI 配置。") from exc

    if not api_key:
        raise HTTPException(status_code=400, detail="请填写 API Key 或重新保存 AI 配置。")
    return api_key


def _provider_out(record: AiProviderCredentialRecord | None) -> dict[str, Any] | None:
    if record is None:
        return None
    try:
        api_key = decrypt_secret(record.encrypted_api_key)
    except ValueError:
        api_key = ""
    extra_headers = _parse_extra_headers(record.extra_headers_json)
    return AiProviderConfigOut(
        provider_preset=record.provider_preset,  # type: ignore[arg-type]
        protocol=get_provider_protocol(record.provider_preset),  # type: ignore[arg-type]
        base_url=record.base_url,
        model=record.model,
        api_key_masked=mask_api_key(api_key),
        has_extra_headers=bool(extra_headers),
        updated_at=record.updated_at.isoformat() if record.updated_at else None,
    ).model_dump()


def _parse_extra_headers(raw_json: str) -> dict[str, str]:
    try:
        parsed = json.loads(raw_json or "{}")
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(value) for key, value in parsed.items()}

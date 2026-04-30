"""工作台持久化接口：按 project_id + user_id 隔离。"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.fixed_rules_schemas import FixedRulesConfig
from backend.app.auth.dependencies import CurrentUserContext, get_current_user
from backend.app.database import get_db
from backend.app.fixed_rules.service import run_saved_fixed_rules_svn_update
from backend.app.models import WorkbenchConfigRecord

router = APIRouter(prefix="/workbench", tags=["workbench"])


def _build_workbench_svn_update_config(payload: object) -> FixedRulesConfig:
    """从个人校验持久化配置中提取 SVN 更新需要的最小配置。"""
    if not isinstance(payload, dict):
        raise ValueError("个人校验配置格式不正确。")

    raw_sources = payload.get("sources")
    raw_svn_presets = payload.get("svn_path_replacement_presets")
    raw_selected_svn_preset = payload.get("selected_svn_path_replacement_preset")
    config_payload = {
        "version": 6,
        "configured": bool(payload),
        "sources": raw_sources if isinstance(raw_sources, list) else [],
        "svn_path_replacement_presets": raw_svn_presets
        if isinstance(raw_svn_presets, list)
        else [],
        "selected_svn_path_replacement_preset": raw_selected_svn_preset
        if isinstance(raw_selected_svn_preset, str)
        else None,
    }
    return FixedRulesConfig.model_validate(config_payload)


@router.get("/config")
async def get_workbench_config(
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """读取当前用户在当前项目下的工作台配置。"""
    project_id = ctx.require_project_member()

    result = await db.execute(
        select(WorkbenchConfigRecord).where(
            WorkbenchConfigRecord.project_id == project_id,
            WorkbenchConfigRecord.user_id == ctx.user_id,
        )
    )
    record = result.scalar_one_or_none()

    config = json.loads(record.config_json) if record else {}
    return {"code": 200, "msg": "ok", "data": config}


@router.put("/config")
async def save_workbench_config(
    payload: dict[str, Any],
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """保存工作台配置（前端 2 秒防抖自动调用）。"""
    project_id = ctx.require_project_member()

    result = await db.execute(
        select(WorkbenchConfigRecord).where(
            WorkbenchConfigRecord.project_id == project_id,
            WorkbenchConfigRecord.user_id == ctx.user_id,
        )
    )
    record = result.scalar_one_or_none()

    config_str = json.dumps(payload, ensure_ascii=False)

    if record:
        record.config_json = config_str
    else:
        record = WorkbenchConfigRecord(
            project_id=project_id,
            user_id=ctx.user_id,
            config_json=config_str,
        )
    db.add(record)
    await db.commit()

    return {"code": 200, "msg": "ok"}


@router.post("/svn-update")
async def trigger_workbench_svn_update(
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """对当前用户个人校验配置中的 SVN 数据源执行更新。"""
    project_id = ctx.require_project_member()

    result = await db.execute(
        select(WorkbenchConfigRecord).where(
            WorkbenchConfigRecord.project_id == project_id,
            WorkbenchConfigRecord.user_id == ctx.user_id,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=400, detail="当前个人校验尚未配置工作台")

    try:
        raw_config = json.loads(record.config_json)
        config = _build_workbench_svn_update_config(raw_config)
        update_result = run_saved_fixed_rules_svn_update(
            config,
            user_scope=ctx.user.username,
        )
    except (
        json.JSONDecodeError,
        FileNotFoundError,
        ValueError,
        ImportError,
        NotImplementedError,
    ) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "code": 200,
        "msg": "ok",
        "data": update_result,
    }

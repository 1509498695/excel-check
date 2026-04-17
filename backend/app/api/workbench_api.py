"""工作台持久化接口：按 project_id + user_id 隔离。"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import CurrentUserContext, get_current_user
from backend.app.database import get_db
from backend.app.models import WorkbenchConfigRecord

router = APIRouter(prefix="/workbench", tags=["workbench"])


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

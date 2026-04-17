"""固定规则模块接口。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.fixed_rules_schemas import FixedRulesConfig
from backend.app.auth.dependencies import CurrentUserContext, get_current_user
from backend.app.database import get_db
from backend.app.fixed_rules.db_service import (
    load_fixed_rules_config_from_db,
    save_fixed_rules_config_to_db,
)
from backend.app.fixed_rules.service import (
    build_default_fixed_rules_config,
    execute_saved_fixed_rules,
    load_fixed_rules_config_with_issues,
    parse_raw_fixed_rules_config,
    run_saved_fixed_rules_svn_update,
    save_fixed_rules_config,
    validate_and_normalize_fixed_rules_config,
)


router = APIRouter(prefix="/fixed-rules", tags=["fixed-rules"])


@router.get("/config")
async def get_fixed_rules_config(
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """读取当前固定规则配置（按 project_id 隔离）。"""
    project_id = ctx.require_project_member()

    try:
        raw = await load_fixed_rules_config_from_db(db, project_id)
        if raw is None:
            config = build_default_fixed_rules_config()
            config_issues = []
        else:
            parsed = parse_raw_fixed_rules_config(raw)
            config, config_issues = load_fixed_rules_config_with_issues(parsed)
    except (FileNotFoundError, ValueError, ImportError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response: dict[str, Any] = {
        "code": 200,
        "msg": "ok",
        "data": config.model_dump(mode="json", exclude_none=True),
    }
    if config_issues:
        response["meta"] = {
            "config_issues": [
                issue.model_dump(mode="json", exclude_none=True)
                for issue in config_issues
            ]
        }

    return response


@router.put("/config")
async def put_fixed_rules_config(
    payload: FixedRulesConfig,
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """整体保存固定规则配置（按 project_id 隔离）。"""
    project_id = ctx.require_project_member()

    try:
        config = validate_and_normalize_fixed_rules_config(payload)
    except (FileNotFoundError, ValueError, ImportError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await save_fixed_rules_config_to_db(
        db,
        project_id,
        config.model_dump(mode="json", exclude_none=True),
    )

    return {
        "code": 200,
        "msg": "ok",
        "data": config.model_dump(mode="json", exclude_none=True),
    }


@router.post("/svn-update")
async def trigger_fixed_rules_svn_update(
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """对当前固定规则配置中的数据源目录执行 SVN 更新。"""
    project_id = ctx.require_project_member()

    raw = await load_fixed_rules_config_from_db(db, project_id)
    if raw is None:
        raise HTTPException(status_code=400, detail="当前项目尚未配置固定规则")

    try:
        parsed = parse_raw_fixed_rules_config(raw)
        config = validate_and_normalize_fixed_rules_config(parsed)
    except (FileNotFoundError, ValueError, ImportError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        update_result = run_saved_fixed_rules_svn_update(config)
    except (FileNotFoundError, ValueError, ImportError, NotImplementedError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "code": 200,
        "msg": "ok",
        "data": update_result,
    }


@router.post("/execute")
async def execute_fixed_rules_endpoint(
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """执行当前项目的固定规则配置。"""
    project_id = ctx.require_project_member()

    raw = await load_fixed_rules_config_from_db(db, project_id)
    if raw is None:
        raise HTTPException(status_code=400, detail="当前项目尚未配置固定规则")

    try:
        parsed = parse_raw_fixed_rules_config(raw)
        config = validate_and_normalize_fixed_rules_config(parsed)
        return execute_saved_fixed_rules(config)
    except (FileNotFoundError, ValueError, ImportError, NotImplementedError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

"""固定规则模块接口。"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.fixed_rules_schemas import FixedRulesConfig, FixedRulesExecuteRequest
from backend.app.auth.dependencies import CurrentUserContext, get_current_user
from backend.app.database import get_db
from backend.app.execution_pipeline import run_execution_pipeline
from backend.app.fixed_rules.db_service import (
    load_fixed_rules_config_from_db,
    save_fixed_rules_config_to_db,
)
from backend.app.fixed_rules.service import (
    build_default_fixed_rules_config,
    build_fixed_rules_task_tree,
    load_fixed_rules_config_with_issues,
    parse_raw_fixed_rules_config,
    run_saved_fixed_rules_svn_update,
    save_fixed_rules_config,
    validate_and_normalize_fixed_rules_config,
)
from backend.app.result_store import (
    fetch_execution_result_page,
    normalize_result_page,
    paginate_abnormal_results,
    persist_execution_result,
)
from backend.app.utils.formatter import build_execution_response


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
    payload: FixedRulesExecuteRequest | None = Body(default=None),
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """执行当前项目的固定规则配置。"""
    project_id = ctx.require_project_member()

    raw = await load_fixed_rules_config_from_db(db, project_id)
    if raw is None:
        raise HTTPException(status_code=400, detail="当前项目尚未配置固定规则")

    page, size = normalize_result_page(
        payload.page if payload else None,
        payload.size if payload else None,
    )

    try:
        parsed = parse_raw_fixed_rules_config(raw)
        config = validate_and_normalize_fixed_rules_config(parsed)
        task_tree = build_fixed_rules_task_tree(
            config,
            selected_rule_ids=payload.selected_rule_ids if payload else None,
        )
        start = time.perf_counter()
        execution_artifacts = run_execution_pipeline(task_tree)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        abnormal_results = execution_artifacts["abnormal_results"]
        total_rows_scanned = sum(
            len(frame) for frame in execution_artifacts["loaded_variables"].values()
        )
        failed_sources = execution_artifacts["failed_sources"]
        result_id = await persist_execution_result(
            db,
            scope_type="fixed_rules",
            project_id=project_id,
            user_id=None,
            abnormal_results=abnormal_results,
            execution_time_ms=elapsed_ms,
            total_rows_scanned=total_rows_scanned,
            failed_sources=failed_sources,
        )
        return build_execution_response(
            abnormal_results=abnormal_results,
            execution_time_ms=elapsed_ms,
            total_rows_scanned=total_rows_scanned,
            failed_sources=failed_sources,
            msg="Execution Completed",
            result_id=result_id,
            page=page,
            size=size,
            total=len(abnormal_results),
            result_list=paginate_abnormal_results(abnormal_results, page, size),
        )
    except (FileNotFoundError, ValueError, ImportError, NotImplementedError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/results/{result_id}")
async def get_fixed_rules_result_page(
    result_id: int,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """分页读取当前项目最近一次项目校验结果。"""
    project_id = ctx.require_project_member()
    normalized_page, normalized_size = normalize_result_page(page, size)
    payload = await fetch_execution_result_page(
        db,
        scope_type="fixed_rules",
        result_id=result_id,
        project_id=project_id,
        user_id=None,
        page=normalized_page,
        size=normalized_size,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="未找到对应的执行结果")

    return build_execution_response(
        abnormal_results=payload["list"],
        execution_time_ms=payload["execution_time_ms"],
        total_rows_scanned=payload["total_rows_scanned"],
        failed_sources=payload["failed_sources"],
        msg="Execution Completed",
        result_id=payload["result_id"],
        page=payload["page"],
        size=payload["size"],
        total=payload["total"],
        result_list=payload["list"],
    )

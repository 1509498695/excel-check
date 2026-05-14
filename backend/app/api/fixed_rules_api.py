"""固定规则模块接口。"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.fixed_rules_schemas import (
    FixedRulesConfig,
    FixedRulesExecuteRequest,
    FixedRulesImportRequest,
)
from backend.app.auth.dependencies import CurrentUserContext, get_current_user
from backend.app.database import get_db
from backend.app.fixed_rules.db_service import (
    load_fixed_rules_config_from_db,
    save_fixed_rules_config_to_db,
)
from backend.app.fixed_rules.import_service import (
    build_import_preview,
    build_imported_config,
)
from backend.app.fixed_rules.service import (
    build_default_fixed_rules_config,
    execute_fixed_rules_for_project,
    load_fixed_rules_config_with_issues,
    parse_raw_fixed_rules_config,
    run_saved_fixed_rules_svn_update,
    validate_and_normalize_fixed_rules_config,
)
from backend.app.result_store import (
    fetch_execution_result_export,
    fetch_execution_result_page,
    normalize_result_page,
    paginate_abnormal_results,
)
from backend.app.result_exporter import (
    RESULT_EXPORT_MIME_TYPE,
    build_execution_result_workbook,
)
from backend.app.utils.formatter import build_execution_response
from backend.app.models import WorkbenchConfigRecord


router = APIRouter(prefix="/fixed-rules", tags=["fixed-rules"])


async def _load_current_fixed_config(
    db: AsyncSession,
    project_id: int,
) -> FixedRulesConfig:
    raw = await load_fixed_rules_config_from_db(db, project_id)
    if raw is None:
        return build_default_fixed_rules_config()
    parsed = parse_raw_fixed_rules_config(raw)
    config, _issues = load_fixed_rules_config_with_issues(
        parsed,
        allow_legacy_mapping_config=True,
    )
    return config


async def _load_current_workbench_payload(
    db: AsyncSession,
    project_id: int,
    user_id: int,
) -> dict[str, Any]:
    result = await db.execute(
        select(WorkbenchConfigRecord).where(
            WorkbenchConfigRecord.project_id == project_id,
            WorkbenchConfigRecord.user_id == user_id,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise ValueError("当前个人校验尚未配置可导入规则。")
    return json.loads(record.config_json)


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
            config, config_issues = load_fixed_rules_config_with_issues(
                parsed,
                allow_legacy_mapping_config=True,
            )
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
        config, config_issues = load_fixed_rules_config_with_issues(
            payload,
            allow_unsupported_csv=False,
        )
    except (FileNotFoundError, ValueError, ImportError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await save_fixed_rules_config_to_db(
        db,
        project_id,
        config.model_dump(mode="json", exclude_none=True),
    )

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


@router.post("/import-preview")
async def preview_import_from_workbench(
    payload: FixedRulesImportRequest,
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """预检：将当前用户个人校验中勾选的规则导入项目校验。"""
    project_id = ctx.require_project_member()

    try:
        workbench_payload = await _load_current_workbench_payload(
            db,
            project_id,
            ctx.user_id,
        )
        fixed_config = await _load_current_fixed_config(db, project_id)
        preview = build_import_preview(
            workbench_payload=workbench_payload,
            fixed_config=fixed_config,
            selected_rule_ids=payload.selected_rule_ids,
            source_overrides=payload.source_overrides,
            variable_tag_overrides=payload.variable_tag_overrides,
        )
    except (json.JSONDecodeError, FileNotFoundError, ValueError, ImportError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "code": 200,
        "msg": "ok",
        "data": preview.response,
    }


@router.post("/import-from-workbench")
async def import_from_workbench(
    payload: FixedRulesImportRequest,
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """提交：从当前用户个人校验导入兼容规则到项目校验。"""
    project_id = ctx.require_project_member()

    try:
        workbench_payload = await _load_current_workbench_payload(
            db,
            project_id,
            ctx.user_id,
        )
        fixed_config = await _load_current_fixed_config(db, project_id)
        preview = build_import_preview(
            workbench_payload=workbench_payload,
            fixed_config=fixed_config,
            selected_rule_ids=payload.selected_rule_ids,
            source_overrides=payload.source_overrides,
            variable_tag_overrides=payload.variable_tag_overrides,
        )
        if preview.rules_to_add:
            imported_config = build_imported_config(preview)
            await save_fixed_rules_config_to_db(
                db,
                project_id,
                imported_config.model_dump(mode="json", exclude_none=True),
            )
        else:
            imported_config = fixed_config
    except (json.JSONDecodeError, FileNotFoundError, ValueError, ImportError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "code": 200,
        "msg": "ok",
        "data": imported_config.model_dump(mode="json", exclude_none=True),
        "meta": {
            "import_result": preview.response,
        },
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
        update_result = run_saved_fixed_rules_svn_update(
            config,
            user_scope=ctx.user.username,
        )
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

    page, size = normalize_result_page(
        payload.page if payload else None,
        payload.size if payload else None,
    )

    try:
        execution_summary = await execute_fixed_rules_for_project(
            db,
            project_id,
            user_scope=ctx.user.username,
            selected_rule_ids=payload.selected_rule_ids if payload else None,
        )
    except (FileNotFoundError, ValueError, ImportError, NotImplementedError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    abnormal_results = execution_summary["abnormal_results"]
    return build_execution_response(
        abnormal_results=abnormal_results,
        execution_time_ms=execution_summary["execution_time_ms"],
        total_rows_scanned=execution_summary["total_rows_scanned"],
        failed_sources=execution_summary["failed_sources"],
        msg="Execution Completed",
        result_id=execution_summary["result_id"],
        page=page,
        size=size,
        total=len(abnormal_results),
        result_list=paginate_abnormal_results(abnormal_results, page, size),
    )


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


@router.get("/results/{result_id}/export")
async def export_fixed_rules_result(
    result_id: int,
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """导出当前项目的项目校验执行结果为 Excel。"""
    project_id = ctx.require_project_member()
    payload = await fetch_execution_result_export(
        db,
        scope_type="fixed_rules",
        result_id=result_id,
        project_id=project_id,
        user_id=None,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="未找到对应的执行结果")

    workbook = build_execution_result_workbook(payload, scope_label="项目校验")
    filename = f"project-check-results-{result_id}.xlsx"
    return StreamingResponse(
        workbook,
        media_type=RESULT_EXPORT_MIME_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

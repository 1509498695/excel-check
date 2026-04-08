"""固定规则模块接口。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from backend.app.api.fixed_rules_schemas import FixedRulesConfig
from backend.app.fixed_rules.service import (
    execute_saved_fixed_rules,
    load_fixed_rules_config,
    run_saved_fixed_rules_svn_update,
    save_fixed_rules_config,
)


router = APIRouter(prefix="/fixed-rules", tags=["fixed-rules"])


@router.get("/config")
def get_fixed_rules_config() -> dict[str, Any]:
    """读取当前固定规则配置。"""
    try:
        config = load_fixed_rules_config()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "code": 200,
        "msg": "ok",
        "data": config.model_dump(mode="json"),
    }


@router.put("/config")
def put_fixed_rules_config(payload: FixedRulesConfig) -> dict[str, Any]:
    """整体保存固定规则配置。"""
    try:
        config = save_fixed_rules_config(payload)
    except (FileNotFoundError, ValueError, ImportError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "code": 200,
        "msg": "ok",
        "data": config.model_dump(mode="json"),
    }


@router.post("/svn-update")
def trigger_fixed_rules_svn_update() -> dict[str, Any]:
    """对当前固定规则文件所在目录执行一次 SVN 更新。"""
    try:
        update_result = run_saved_fixed_rules_svn_update()
    except (FileNotFoundError, ValueError, ImportError, NotImplementedError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "code": 200,
        "msg": "ok",
        "data": update_result,
    }


@router.post("/execute")
def execute_fixed_rules() -> dict[str, Any]:
    """执行当前已保存的固定规则配置。"""
    try:
        return execute_saved_fixed_rules()
    except (FileNotFoundError, ValueError, ImportError, NotImplementedError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

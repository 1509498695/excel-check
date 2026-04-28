"""认证路由：注册、登录、获取用户信息、修改密码、切换项目。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import CurrentUserContext, get_current_user
from backend.app.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    UserInfo,
    UserProjectInfo,
)
from backend.app.auth.service import (
    authenticate_user,
    create_access_token,
    get_default_project_id,
    hash_password,
    register_user,
    resolve_active_project_id,
    verify_password,
)
from backend.app.database import ensure_default_auth_bootstrap, get_db
from backend.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


def _build_user_info(
    user: Any,
    current_project_id: int | None = None,
) -> UserInfo:
    """从 ORM User 实例构造前端所需的 UserInfo。"""
    projects = [
        UserProjectInfo(
            project_id=r.project_id,
            project_name=r.project.name,
            role=r.role,
        )
        for r in user.roles
    ]
    current_role = None
    if current_project_id is not None:
        for r in user.roles:
            if r.project_id == current_project_id:
                current_role = r.role
                break

    return UserInfo(
        id=user.id,
        username=user.username,
        is_super_admin=user.is_super_admin,
        current_project_id=current_project_id,
        current_role=current_role,
        projects=projects,
    )


@router.post("/register")
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """用户注册，注册后立即可用。"""
    try:
        user = await register_user(
            db,
            username=payload.username,
            password=payload.password,
            project_id=payload.project_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    default_project_id = get_default_project_id(user)
    token = create_access_token(user.id, project_id=default_project_id)
    return {
        "code": 200,
        "msg": "注册成功",
        "data": {
            "token": token,
            "user": _build_user_info(user, default_project_id).model_dump(),
        },
    }


@router.post("/login")
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """用户登录。"""
    try:
        # 保留原有业务逻辑：优先按原认证链路校验用户名和密码。
        user = await authenticate_user(db, payload.username, payload.password)
    except ValueError as exc:
        if payload.username.strip() != settings.default_super_admin_username:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

        await ensure_default_auth_bootstrap()
        try:
            # 保留原有业务逻辑：仅在默认管理员缺失时做一次受控自修复并重试。
            user = await authenticate_user(db, payload.username, payload.password)
        except ValueError as retry_exc:
            raise HTTPException(status_code=401, detail=str(retry_exc)) from retry_exc

    default_project_id = get_default_project_id(user)
    token = create_access_token(user.id, project_id=default_project_id)
    return {
        "code": 200,
        "msg": "登录成功",
        "data": {
            "token": token,
            "user": _build_user_info(user, default_project_id).model_dump(),
        },
    }


@router.get("/me")
async def get_me(
    ctx: CurrentUserContext = Depends(get_current_user),
) -> dict[str, Any]:
    """获取当前用户信息。"""
    return {
        "code": 200,
        "msg": "ok",
        "data": _build_user_info(
            ctx.user,
            resolve_active_project_id(ctx.user, ctx.project_id),
        ).model_dump(),
    }


@router.post("/switch-project/{project_id}")
async def switch_project(
    project_id: int,
    ctx: CurrentUserContext = Depends(get_current_user),
) -> dict[str, Any]:
    """切换当前项目，返回新的 Token。"""
    if not ctx.is_super_admin:
        role = ctx.role_in_project(project_id)
        if role is None:
            raise HTTPException(status_code=403, detail="您不属于该项目")

    token = create_access_token(ctx.user_id, project_id=project_id)
    return {
        "code": 200,
        "msg": "ok",
        "data": {
            "token": token,
            "user": _build_user_info(
                ctx.user,
                resolve_active_project_id(ctx.user, project_id),
            ).model_dump(),
        },
    }


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """修改当前用户密码。"""
    if not verify_password(payload.old_password, ctx.user.hashed_password):
        raise HTTPException(status_code=400, detail="原密码不正确")

    ctx.user.hashed_password = hash_password(payload.new_password)
    db.add(ctx.user)
    await db.commit()

    return {"code": 200, "msg": "密码修改成功"}

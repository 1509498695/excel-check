"""管理后台路由：项目 CRUD、成员管理。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.admin.schemas import (
    ProjectCreateRequest,
    ProjectUpdateRequest,
    ResetUserPasswordRequest,
    SetMemberRoleRequest,
)
from backend.app.auth.dependencies import CurrentUserContext, get_current_user
from backend.app.auth.service import hash_password
from backend.app.database import get_db
from backend.app.models import Project, User, UserProjectRole

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/projects")
async def list_projects(
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """列出所有项目（仅管理员可用）。"""
    ctx.require_super_admin()
    result = await db.execute(
        select(Project).options(selectinload(Project.members)).order_by(Project.id)
    )
    projects = result.scalars().all()
    return {
        "code": 200,
        "msg": "ok",
        "data": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "member_count": len(p.members),
            }
            for p in projects
        ],
    }


@router.post("/projects")
async def create_project(
    payload: ProjectCreateRequest,
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """创建新项目（仅超级管理员）。"""
    ctx.require_super_admin()

    existing = await db.execute(select(Project).where(Project.name == payload.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"项目名 '{payload.name}' 已存在")

    project = Project(name=payload.name, description=payload.description)
    db.add(project)
    await db.commit()
    await db.refresh(project)

    return {
        "code": 200,
        "msg": "项目创建成功",
        "data": {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "created_at": project.created_at.isoformat() if project.created_at else None,
        },
    }


@router.put("/projects/{project_id}")
async def update_project(
    project_id: int,
    payload: ProjectUpdateRequest,
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """更新项目信息。"""
    ctx.require_super_admin()

    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if payload.name is not None:
        project.name = payload.name
    if payload.description is not None:
        project.description = payload.description

    db.add(project)
    await db.commit()
    await db.refresh(project)

    return {
        "code": 200,
        "msg": "项目更新成功",
        "data": {
            "id": project.id,
            "name": project.name,
            "description": project.description,
        },
    }


@router.get("/projects/{project_id}/members")
async def list_project_members(
    project_id: int,
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """查看项目成员列表。超级管理员或项目管理员可用。"""
    if not ctx.is_super_admin:
        role = ctx.role_in_project(project_id)
        if role != "admin":
            raise HTTPException(status_code=403, detail="需要管理员权限")

    result = await db.execute(
        select(UserProjectRole)
        .where(UserProjectRole.project_id == project_id)
        .options(selectinload(UserProjectRole.user))
        .order_by(UserProjectRole.joined_at)
    )
    members = result.scalars().all()

    return {
        "code": 200,
        "msg": "ok",
        "data": [
            {
                "user_id": m.user.id,
                "username": m.user.username,
                "role": m.role,
                "is_super_admin": m.user.is_super_admin,
                "joined_at": m.joined_at.isoformat() if m.joined_at else None,
            }
            for m in members
        ],
    }


@router.put("/projects/{project_id}/members/{user_id}/role")
async def set_member_role(
    project_id: int,
    user_id: int,
    payload: SetMemberRoleRequest,
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """设置成员角色（设为管理员 / 普通用户）。"""
    if not ctx.is_super_admin:
        role = ctx.role_in_project(project_id)
        if role != "admin":
            raise HTTPException(status_code=403, detail="需要管理员权限")

    result = await db.execute(
        select(UserProjectRole).where(
            UserProjectRole.project_id == project_id,
            UserProjectRole.user_id == user_id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="该用户不属于此项目")

    membership.role = payload.role
    db.add(membership)
    await db.commit()

    return {"code": 200, "msg": f"已将用户角色设为 {payload.role}"}


@router.delete("/projects/{project_id}/members/{user_id}")
async def remove_member(
    project_id: int,
    user_id: int,
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """将成员从项目中移除。"""
    if not ctx.is_super_admin:
        role = ctx.role_in_project(project_id)
        if role != "admin":
            raise HTTPException(status_code=403, detail="需要管理员权限")

    if user_id == ctx.user_id:
        raise HTTPException(status_code=400, detail="不能移除自己")

    result = await db.execute(
        delete(UserProjectRole).where(
            UserProjectRole.project_id == project_id,
            UserProjectRole.user_id == user_id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="该用户不属于此项目")

    await db.commit()
    return {"code": 200, "msg": "成员已移除"}


@router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    payload: ResetUserPasswordRequest,
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """由超级管理员重置任意用户的登录密码（用于用户忘记密码等场景）。"""
    ctx.require_super_admin()

    if user_id == ctx.user_id:
        raise HTTPException(status_code=400, detail="不能在此处重置自己的密码，请使用个人中心「修改密码」")

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.hashed_password = hash_password(payload.new_password)
    db.add(user)
    await db.commit()

    return {"code": 200, "msg": "密码已重置"}


@router.get("/projects-public")
async def list_projects_public(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """公开接口：返回项目列表（仅 id + name），供注册页下拉选择。"""
    result = await db.execute(select(Project).order_by(Project.id))
    projects = result.scalars().all()
    return {
        "code": 200,
        "msg": "ok",
        "data": [{"id": p.id, "name": p.name} for p in projects],
    }

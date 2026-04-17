"""管理后台路由：项目 CRUD、成员管理。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
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
from backend.app.models import (
    FixedRulesConfigRecord,
    Project,
    User,
    UserProjectRole,
    WorkbenchConfigRecord,
)

router = APIRouter(prefix="/admin", tags=["admin"])

DEFAULT_PROJECT_NAME = "默认项目"


async def _get_project_or_404(db: AsyncSession, project_id: int) -> Project:
    """按项目 ID 获取项目，不存在时抛出 404。"""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


async def _get_default_project_or_500(db: AsyncSession) -> Project:
    """获取系统默认项目，不存在时视为服务端配置异常。"""
    result = await db.execute(
        select(Project).where(Project.name == DEFAULT_PROJECT_NAME)
    )
    default_project = result.scalar_one_or_none()
    if default_project is None:
        raise HTTPException(status_code=500, detail="默认项目不存在，请先初始化系统默认项目")
    return default_project


def _ensure_project_deletable(project: Project) -> None:
    """默认项目不可删除，避免破坏系统默认空间。"""
    if project.name == DEFAULT_PROJECT_NAME:
        raise HTTPException(status_code=400, detail="默认项目不可删除")


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

    normalized_name = payload.name.strip()
    existing = await db.execute(select(Project).where(Project.name == normalized_name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"项目名 '{normalized_name}' 已存在")

    project = Project(name=normalized_name, description=payload.description)
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

    project = await _get_project_or_404(db, project_id)

    if payload.name is not None:
        normalized_name = payload.name.strip()
        existing = await db.execute(
            select(Project).where(
                Project.name == normalized_name,
                Project.id != project_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"项目名 '{normalized_name}' 已存在")
        project.name = normalized_name
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


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(
    project_id: int,
    ctx: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """删除普通项目前先迁移成员到默认项目，再清理项目级数据。"""
    ctx.require_super_admin()

    project = await _get_project_or_404(db, project_id)
    _ensure_project_deletable(project)
    default_project = await _get_default_project_or_500(db)

    memberships_result = await db.execute(
        select(UserProjectRole).where(UserProjectRole.project_id == project_id)
    )
    memberships = memberships_result.scalars().all()

    default_memberships_result = await db.execute(
        select(UserProjectRole).where(UserProjectRole.project_id == default_project.id)
    )
    existing_default_memberships = {
        membership.user_id: membership
        for membership in default_memberships_result.scalars().all()
    }

    for membership in memberships:
        if membership.user_id in existing_default_memberships:
            continue
        db.add(
            UserProjectRole(
                user_id=membership.user_id,
                project_id=default_project.id,
                role="user",
            )
        )

    # SQLite 测试环境默认不会可靠触发所有外键级联，这里显式清理项目级记录，
    # 保证删除行为与业务预期一致。
    await db.execute(
        delete(FixedRulesConfigRecord).where(
            FixedRulesConfigRecord.project_id == project_id
        )
    )
    await db.execute(
        delete(WorkbenchConfigRecord).where(
            WorkbenchConfigRecord.project_id == project_id
        )
    )
    await db.delete(project)
    await db.commit()
    return Response(status_code=204)


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
        raise HTTPException(status_code=400, detail="不能删除自己")

    project = await _get_project_or_404(db, project_id)
    result = await db.execute(
        select(UserProjectRole)
        .where(
            UserProjectRole.project_id == project_id,
            UserProjectRole.user_id == user_id,
        )
        .options(selectinload(UserProjectRole.user))
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=404, detail="该用户不属于此项目")

    if project.name == DEFAULT_PROJECT_NAME:
        if membership.user.is_super_admin:
            raise HTTPException(status_code=400, detail="默认项目中的超级管理员不可删除")
        await db.execute(
            delete(WorkbenchConfigRecord).where(WorkbenchConfigRecord.user_id == user_id)
        )
        await db.delete(membership.user)
        await db.commit()
        return {"code": 200, "msg": "用户账号已删除"}

    default_project = await _get_default_project_or_500(db)
    default_membership_result = await db.execute(
        select(UserProjectRole).where(
            UserProjectRole.project_id == default_project.id,
            UserProjectRole.user_id == user_id,
        )
    )
    default_membership = default_membership_result.scalar_one_or_none()
    if default_membership is None:
        db.add(
            UserProjectRole(
                user_id=user_id,
                project_id=default_project.id,
                role="user",
            )
        )

    await db.delete(membership)
    await db.commit()
    return {"code": 200, "msg": "成员已移入默认项目"}


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

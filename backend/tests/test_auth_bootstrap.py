"""认证初始化与默认管理员收口测试。"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.app.auth.service import hash_password, verify_password
from backend.app.database import (
    async_session_factory,
    ensure_default_auth_bootstrap,
    init_db,
    _seed_default_project,
    _seed_default_super_admin,
)
from backend.app.models import Project, User, UserProjectRole
from backend.config import settings
from backend.run import app


@pytest.mark.anyio
async def test_init_db_seeds_default_super_admin(test_db) -> None:
    """启动初始化后应自动创建默认项目与唯一默认超级管理员。"""
    await init_db()

    async with async_session_factory() as session:
        project_result = await session.execute(select(Project).order_by(Project.id))
        projects = project_result.scalars().all()
        user_result = await session.execute(
            select(User).where(User.username == settings.default_super_admin_username)
        )
        admin_user = user_result.scalar_one()
        role_result = await session.execute(
            select(UserProjectRole).where(UserProjectRole.user_id == admin_user.id)
        )
        admin_roles = role_result.scalars().all()

    assert len(projects) == 1
    assert projects[0].name == "默认项目"
    assert admin_user.is_super_admin is True
    assert admin_user.primary_project_id == projects[0].id
    assert verify_password(settings.default_super_admin_password, admin_user.hashed_password)
    assert len(admin_roles) == 1
    assert admin_roles[0].project_id == projects[0].id
    assert admin_roles[0].role == "admin"


@pytest.mark.anyio
async def test_seed_default_super_admin_repairs_existing_state(test_db) -> None:
    """已有库中若存在多个超管，应被修复为 admin 唯一超管。"""
    async with async_session_factory() as session:
        project = Project(name="existing-project", description="")
        session.add(project)
        await session.flush()

        admin_user = User(
            username=settings.default_super_admin_username,
            hashed_password="old_hash",
            is_super_admin=False,
        )
        other_super_admin = User(
            username="legacy_super_admin",
            hashed_password="legacy_hash",
            is_super_admin=True,
        )
        session.add_all([admin_user, other_super_admin])
        await session.flush()
        session.add(
            UserProjectRole(user_id=other_super_admin.id, project_id=project.id, role="admin")
        )
        await session.commit()
        project_id = project.id

    await _seed_default_super_admin(project_id)

    async with async_session_factory() as session:
        result = await session.execute(select(User).order_by(User.id))
        users = result.scalars().all()
        role_result = await session.execute(
            select(UserProjectRole).where(
                UserProjectRole.project_id == project_id,
                UserProjectRole.role == "admin",
            )
        )
        admin_roles = role_result.scalars().all()

    admin_user = next(
        user for user in users if user.username == settings.default_super_admin_username
    )
    legacy_user = next(user for user in users if user.username == "legacy_super_admin")

    assert admin_user.is_super_admin is True
    assert verify_password(settings.default_super_admin_password, admin_user.hashed_password)
    assert legacy_user.is_super_admin is False
    assert any(role.user_id == admin_user.id for role in admin_roles)


@pytest.mark.anyio
async def test_register_user_never_becomes_super_admin(test_db) -> None:
    """普通注册用户不应再因首个注册而自动变成超级管理员。"""
    await init_db()

    async with async_session_factory() as session:
        result = await session.execute(select(Project).order_by(Project.id))
        default_project = result.scalar_one()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "normal_user",
                "password": "userpass123",
                "project_id": default_project.id,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["user"]["username"] == "normal_user"
    assert payload["data"]["user"]["is_super_admin"] is False
    assert payload["data"]["user"]["current_project_id"] == default_project.id
    assert payload["data"]["user"]["current_role"] == "user"

    async with async_session_factory() as session:
        user_result = await session.execute(select(User).where(User.username == "normal_user"))
        user = user_result.scalar_one()
        role_result = await session.execute(
            select(UserProjectRole).where(UserProjectRole.user_id == user.id)
        )
        role = role_result.scalar_one()

    assert user.is_super_admin is False
    assert user.primary_project_id == default_project.id
    assert role.role == "user"


@pytest.mark.anyio
async def test_seed_default_project_creates_named_default_project(test_db) -> None:
    """即使库里已有普通项目，也应补齐名为“默认项目”的系统项目。"""
    async with async_session_factory() as session:
        session.add(Project(name="业务项目", description="普通项目"))
        await session.commit()

    default_project = await _seed_default_project()

    async with async_session_factory() as session:
        result = await session.execute(select(Project).order_by(Project.id))
        projects = result.scalars().all()

    assert default_project.name == "默认项目"
    assert {project.name for project in projects} == {"业务项目", "默认项目"}


@pytest.mark.anyio
async def test_login_admin_after_init_db_on_empty_database(test_db) -> None:
    """空库执行初始化后，默认超级管理员应能直接登录。"""
    await init_db()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "username": settings.default_super_admin_username,
                "password": settings.default_super_admin_password,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["user"]["username"] == settings.default_super_admin_username
    assert payload["data"]["user"]["is_super_admin"] is True
    assert payload["data"]["user"]["current_project_id"] is not None


@pytest.mark.anyio
async def test_login_self_heals_missing_default_admin(test_db) -> None:
    """默认管理员缺失时，登录接口应触发一次受控自修复并恢复登录。"""
    await ensure_default_auth_bootstrap()

    async with async_session_factory() as session:
        admin_result = await session.execute(
            select(User).where(User.username == settings.default_super_admin_username)
        )
        admin_user = admin_result.scalar_one()
        await session.delete(admin_user)
        await session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "username": settings.default_super_admin_username,
                "password": settings.default_super_admin_password,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["user"]["username"] == settings.default_super_admin_username
    assert payload["data"]["user"]["is_super_admin"] is True

    async with async_session_factory() as session:
        repaired_user_result = await session.execute(
            select(User).where(User.username == settings.default_super_admin_username)
        )
        repaired_user = repaired_user_result.scalar_one()
        role_result = await session.execute(
            select(UserProjectRole).where(UserProjectRole.user_id == repaired_user.id)
        )
        repaired_roles = role_result.scalars().all()

    assert repaired_user.primary_project_id is not None
    assert verify_password(
        settings.default_super_admin_password,
        repaired_user.hashed_password,
    )
    assert repaired_roles


@pytest.mark.anyio
async def test_login_uses_primary_project_instead_of_first_role(test_db) -> None:
    """登录默认项目应按主归属项目返回，而不是依赖第一条角色记录。"""
    async with async_session_factory() as session:
        project_a = Project(name="project-a", description="项目 A")
        project_b = Project(name="project-b", description="项目 B")
        session.add_all([project_a, project_b])
        await session.flush()

        user = User(
            username="primary-project-user",
            hashed_password=hash_password("userpass"),
            is_super_admin=False,
            primary_project_id=project_b.id,
        )
        session.add(user)
        await session.flush()
        session.add_all(
            [
                UserProjectRole(user_id=user.id, project_id=project_a.id, role="user"),
                UserProjectRole(user_id=user.id, project_id=project_b.id, role="user"),
            ]
        )
        await session.commit()
        project_b_id = project_b.id

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "primary-project-user", "password": "userpass"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["user"]["current_project_id"] == project_b_id

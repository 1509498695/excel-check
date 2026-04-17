"""管理后台：超级管理员重置用户密码。"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.app.auth.service import hash_password
from backend.app.database import async_session_factory
from backend.app.models import Project, User, UserProjectRole
from backend.run import app


@pytest.mark.anyio
async def test_super_admin_can_reset_other_user_password(
    auth_client: AsyncClient,
    test_db,
) -> None:
    """超级管理员可将另一用户的密码重置为指定值，随后该用户可用新密码登录。"""
    async with async_session_factory() as session:
        project2 = Project(name="proj-reset-pw", description="")
        session.add(project2)
        await session.flush()
        pid2 = project2.id

        victim = User(
            username="victim_user",
            hashed_password=hash_password("old_secret"),
            is_super_admin=False,
        )
        session.add(victim)
        await session.flush()
        session.add(
            UserProjectRole(user_id=victim.id, project_id=pid2, role="user"),
        )
        await session.commit()
        victim_id = victim.id

    r = await auth_client.post(
        f"/api/v1/admin/users/{victim_id}/reset-password",
        json={"new_password": "newpass123"},
    )
    assert r.status_code == 200
    assert r.json()["code"] == 200

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as anon:
        login = await anon.post(
            "/api/v1/auth/login",
            json={"username": "victim_user", "password": "newpass123"},
        )
    assert login.status_code == 200
    assert login.json()["data"]["user"]["username"] == "victim_user"


@pytest.mark.anyio
async def test_reset_password_cannot_target_self(
    auth_client: AsyncClient,
    test_db,
) -> None:
    """不能通过该接口重置自己的密码。"""
    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.username == "testuser"))
        admin_user = result.scalar_one()
        admin_id = admin_user.id

    r = await auth_client.post(
        f"/api/v1/admin/users/{admin_id}/reset-password",
        json={"new_password": "whatever12"},
    )
    assert r.status_code == 400

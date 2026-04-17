"""管理后台：项目编辑与删除。"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.app.auth.service import create_access_token, hash_password
from backend.app.database import async_session_factory
from backend.app.models import (
    FixedRulesConfigRecord,
    Project,
    User,
    UserProjectRole,
    WorkbenchConfigRecord,
)
from backend.run import app


async def _create_non_admin_headers(project_id: int) -> dict[str, str]:
    """创建一个普通用户并返回其认证头。"""
    async with async_session_factory() as session:
        user = User(
            username="plain_user",
            hashed_password=hash_password("plainpass"),
            is_super_admin=False,
        )
        session.add(user)
        await session.flush()
        session.add(
            UserProjectRole(
                user_id=user.id,
                project_id=project_id,
                role="user",
            )
        )
        await session.commit()
        token = create_access_token(user.id, project_id=project_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_super_admin_can_update_project(
    auth_client: AsyncClient,
    test_project_id: int,
    test_db,
) -> None:
    """超级管理员可以修改项目名称和描述。"""
    response = await auth_client.put(
        f"/api/v1/admin/projects/{test_project_id}",
        json={"name": "project-updated", "description": "新的项目描述"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["name"] == "project-updated"
    assert payload["data"]["description"] == "新的项目描述"


@pytest.mark.anyio
async def test_super_admin_can_delete_regular_project_and_cascade_records(
    auth_client: AsyncClient,
    test_db,
) -> None:
    """删除普通项目时，应迁移成员到默认项目并清理项目级关联记录。"""
    async with async_session_factory() as session:
        default_project = Project(name="默认项目", description="系统默认项目")
        session.add(default_project)
        await session.flush()

        project = Project(name="project-to-delete", description="待删除项目")
        session.add(project)
        await session.flush()

        migrated_user = User(
            username="delete_target_member",
            hashed_password=hash_password("memberpass"),
            is_super_admin=False,
        )
        retained_user = User(
            username="already_in_default",
            hashed_password=hash_password("memberpass"),
            is_super_admin=False,
        )
        session.add_all([migrated_user, retained_user])
        await session.flush()

        session.add_all(
            [
                UserProjectRole(
                    user_id=migrated_user.id, project_id=project.id, role="user"
                ),
                UserProjectRole(
                    user_id=retained_user.id, project_id=project.id, role="admin"
                ),
                UserProjectRole(
                    user_id=retained_user.id,
                    project_id=default_project.id,
                    role="admin",
                ),
            ]
        )
        session.add(
            FixedRulesConfigRecord(
                project_id=project.id,
                config_json='{"configured": true}',
            )
        )
        session.add(
            WorkbenchConfigRecord(
                project_id=project.id,
                user_id=migrated_user.id,
                config_json='{"sources": []}',
            )
        )
        await session.commit()
        project_id = project.id
        default_project_id = default_project.id
        migrated_user_id = migrated_user.id
        retained_user_id = retained_user.id

    response = await auth_client.delete(f"/api/v1/admin/projects/{project_id}")
    assert response.status_code == 204

    async with async_session_factory() as session:
        project_result = await session.execute(
            select(Project).where(Project.id == project_id)
        )
        member_result = await session.execute(
            select(UserProjectRole).where(UserProjectRole.project_id == project_id)
        )
        migrated_default_role_result = await session.execute(
            select(UserProjectRole).where(
                UserProjectRole.project_id == default_project_id,
                UserProjectRole.user_id == migrated_user_id,
            )
        )
        retained_default_roles_result = await session.execute(
            select(UserProjectRole).where(
                UserProjectRole.project_id == default_project_id,
                UserProjectRole.user_id == retained_user_id,
            )
        )
        fixed_rules_result = await session.execute(
            select(FixedRulesConfigRecord).where(
                FixedRulesConfigRecord.project_id == project_id
            )
        )
        workbench_result = await session.execute(
            select(WorkbenchConfigRecord).where(
                WorkbenchConfigRecord.project_id == project_id
            )
        )

        assert project_result.scalar_one_or_none() is None
        assert member_result.scalars().all() == []
        migrated_default_role = migrated_default_role_result.scalar_one_or_none()
        retained_default_roles = retained_default_roles_result.scalars().all()
        assert migrated_default_role is not None
        assert migrated_default_role.role == "user"
        assert len(retained_default_roles) == 1
        assert retained_default_roles[0].role == "admin"
        assert fixed_rules_result.scalars().all() == []
        assert workbench_result.scalars().all() == []


@pytest.mark.anyio
async def test_delete_default_project_returns_400(
    auth_client: AsyncClient,
    test_db,
) -> None:
    """默认项目不可删除。"""
    async with async_session_factory() as session:
        default_project = Project(name="默认项目", description="系统默认项目")
        session.add(default_project)
        await session.commit()
        project_id = default_project.id

    response = await auth_client.delete(f"/api/v1/admin/projects/{project_id}")
    assert response.status_code == 400
    assert response.json()["detail"] == "默认项目不可删除"


@pytest.mark.anyio
async def test_non_super_admin_cannot_update_or_delete_project(
    test_db,
    test_project_id: int,
) -> None:
    """非超级管理员不能修改或删除项目。"""
    headers = await _create_non_admin_headers(test_project_id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers=headers,
    ) as client:
        update_response = await client.put(
            f"/api/v1/admin/projects/{test_project_id}",
            json={"name": "should-fail"},
        )
        delete_response = await client.delete(
            f"/api/v1/admin/projects/{test_project_id}"
        )

    assert update_response.status_code == 403
    assert delete_response.status_code == 403


@pytest.mark.anyio
async def test_remove_member_from_non_default_project_moves_user_to_default_project(
    auth_client: AsyncClient,
    test_db,
) -> None:
    """普通项目删除成员时，应迁移到默认项目并保留账号。"""
    async with async_session_factory() as session:
        default_project = Project(name="默认项目", description="系统默认项目")
        source_project = Project(name="member-move-project", description="成员迁移测试")
        session.add_all([default_project, source_project])
        await session.flush()

        user = User(
            username="move_member_user",
            hashed_password=hash_password("memberpass"),
            is_super_admin=False,
        )
        session.add(user)
        await session.flush()

        source_membership = UserProjectRole(
            user_id=user.id,
            project_id=source_project.id,
            role="admin",
        )
        session.add(source_membership)
        await session.commit()

        project_id = source_project.id
        default_project_id = default_project.id
        user_id = user.id

    response = await auth_client.delete(
        f"/api/v1/admin/projects/{project_id}/members/{user_id}"
    )
    assert response.status_code == 200
    assert response.json()["msg"] == "成员已移入默认项目"

    async with async_session_factory() as session:
        user_result = await session.execute(select(User).where(User.id == user_id))
        source_membership_result = await session.execute(
            select(UserProjectRole).where(
                UserProjectRole.project_id == project_id,
                UserProjectRole.user_id == user_id,
            )
        )
        default_membership_result = await session.execute(
            select(UserProjectRole).where(
                UserProjectRole.project_id == default_project_id,
                UserProjectRole.user_id == user_id,
            )
        )

        assert user_result.scalar_one_or_none() is not None
        assert source_membership_result.scalar_one_or_none() is None
        default_membership = default_membership_result.scalar_one_or_none()
        assert default_membership is not None
        assert default_membership.role == "user"


@pytest.mark.anyio
async def test_remove_member_from_non_default_project_keeps_existing_default_role(
    auth_client: AsyncClient,
    test_db,
) -> None:
    """若成员已在默认项目中存在角色记录，不重复插入且不覆盖原角色。"""
    async with async_session_factory() as session:
        default_project = Project(name="默认项目", description="系统默认项目")
        source_project = Project(name="member-retain-project", description="成员迁移测试")
        session.add_all([default_project, source_project])
        await session.flush()

        user = User(
            username="member_with_default_role",
            hashed_password=hash_password("memberpass"),
            is_super_admin=False,
        )
        session.add(user)
        await session.flush()

        session.add_all(
            [
                UserProjectRole(
                    user_id=user.id,
                    project_id=default_project.id,
                    role="admin",
                ),
                UserProjectRole(
                    user_id=user.id,
                    project_id=source_project.id,
                    role="user",
                ),
            ]
        )
        await session.commit()

        project_id = source_project.id
        default_project_id = default_project.id
        user_id = user.id

    response = await auth_client.delete(
        f"/api/v1/admin/projects/{project_id}/members/{user_id}"
    )
    assert response.status_code == 200

    async with async_session_factory() as session:
        default_memberships_result = await session.execute(
            select(UserProjectRole).where(
                UserProjectRole.project_id == default_project_id,
                UserProjectRole.user_id == user_id,
            )
        )
        default_memberships = default_memberships_result.scalars().all()
        assert len(default_memberships) == 1
        assert default_memberships[0].role == "admin"


@pytest.mark.anyio
async def test_remove_member_from_default_project_deletes_user_account(
    auth_client: AsyncClient,
    test_db,
) -> None:
    """默认项目删除普通成员时，应直接删除该用户账号。"""
    async with async_session_factory() as session:
        default_project = Project(name="默认项目", description="系统默认项目")
        other_project = Project(name="other-project", description="其他项目")
        session.add_all([default_project, other_project])
        await session.flush()

        user = User(
            username="default_project_member",
            hashed_password=hash_password("memberpass"),
            is_super_admin=False,
        )
        session.add(user)
        await session.flush()

        session.add_all(
            [
                UserProjectRole(
                    user_id=user.id,
                    project_id=default_project.id,
                    role="user",
                ),
                UserProjectRole(
                    user_id=user.id,
                    project_id=other_project.id,
                    role="admin",
                ),
                WorkbenchConfigRecord(
                    project_id=other_project.id,
                    user_id=user.id,
                    config_json='{"sources": []}',
                ),
            ]
        )
        await session.commit()
        default_project_id = default_project.id
        user_id = user.id

    response = await auth_client.delete(
        f"/api/v1/admin/projects/{default_project_id}/members/{user_id}"
    )
    assert response.status_code == 200
    assert response.json()["msg"] == "用户账号已删除"

    async with async_session_factory() as session:
        user_result = await session.execute(select(User).where(User.id == user_id))
        role_result = await session.execute(
            select(UserProjectRole).where(UserProjectRole.user_id == user_id)
        )
        workbench_result = await session.execute(
            select(WorkbenchConfigRecord).where(WorkbenchConfigRecord.user_id == user_id)
        )
        assert user_result.scalar_one_or_none() is None
        assert role_result.scalars().all() == []
        assert workbench_result.scalars().all() == []


@pytest.mark.anyio
async def test_remove_super_admin_from_default_project_returns_400(
    auth_client: AsyncClient,
    test_db,
) -> None:
    """默认项目中的超级管理员不可删除。"""
    async with async_session_factory() as session:
        default_project = Project(name="默认项目", description="系统默认项目")
        session.add(default_project)
        await session.flush()

        user = User(
            username="other_super_admin",
            hashed_password=hash_password("memberpass"),
            is_super_admin=True,
        )
        session.add(user)
        await session.flush()
        session.add(
            UserProjectRole(
                user_id=user.id,
                project_id=default_project.id,
                role="admin",
            )
        )
        await session.commit()

        project_id = default_project.id
        user_id = user.id

    response = await auth_client.delete(
        f"/api/v1/admin/projects/{project_id}/members/{user_id}"
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "默认项目中的超级管理员不可删除"


@pytest.mark.anyio
async def test_remove_current_user_returns_400(
    auth_client: AsyncClient,
    test_project_id: int,
    test_db,
) -> None:
    """当前登录用户本人不可删除。"""
    async with async_session_factory() as session:
        current_user = (
            await session.execute(select(User).where(User.username == "testuser"))
        ).scalar_one()

    response = await auth_client.delete(
        f"/api/v1/admin/projects/{test_project_id}/members/{current_user.id}"
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "不能删除自己"

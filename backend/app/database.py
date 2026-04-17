"""异步 SQLAlchemy 引擎与会话工厂，供全局复用。"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.config import settings

engine = create_async_engine(settings.db_url, echo=settings.debug)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """ORM 基类。"""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：每次请求分配一个独立的数据库会话。"""
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    """应用启动时创建所有表结构（幂等操作），并确保默认项目与管理员存在。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    default_project = await _seed_default_project()
    await _seed_default_super_admin(default_project.id)


async def _seed_default_project():
    """若 projects 表为空，插入默认项目，并返回默认项目实例。"""
    from backend.app.models import Project  # 延迟导入，避免循环依赖

    async with async_session_factory() as session:
        result = await session.execute(select(Project).order_by(Project.id).limit(1))
        project = result.scalar_one_or_none()
        if project is None:
            project = Project(name="默认项目", description="系统自动创建的默认项目")
            session.add(project)
            await session.commit()
            await session.refresh(project)
        return project


async def _seed_default_super_admin(default_project_id: int) -> None:
    """确保系统始终存在且仅存在一个默认超级管理员。"""
    from backend.app.auth.service import hash_password
    from backend.app.models import User, UserProjectRole

    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.username == settings.default_super_admin_username)
        )
        admin_user = result.scalar_one_or_none()

        if admin_user is None:
            admin_user = User(
                username=settings.default_super_admin_username,
                hashed_password=hash_password(settings.default_super_admin_password),
                is_super_admin=True,
            )
            session.add(admin_user)
            await session.flush()
        else:
            admin_user.hashed_password = hash_password(
                settings.default_super_admin_password
            )
            admin_user.is_super_admin = True
            session.add(admin_user)
            await session.flush()

        await session.execute(
            update(User)
            .where(
                User.id != admin_user.id,
                User.is_super_admin.is_(True),
            )
            .values(is_super_admin=False)
        )

        role_result = await session.execute(
            select(UserProjectRole).where(
                UserProjectRole.user_id == admin_user.id,
                UserProjectRole.project_id == default_project_id,
            )
        )
        role = role_result.scalar_one_or_none()
        if role is None:
            session.add(
                UserProjectRole(
                    user_id=admin_user.id,
                    project_id=default_project_id,
                    role="admin",
                )
            )
        else:
            role.role = "admin"
            session.add(role)

        await session.commit()

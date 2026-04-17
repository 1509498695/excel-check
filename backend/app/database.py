"""异步 SQLAlchemy 引擎与会话工厂，供全局复用。"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import select
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
    """应用启动时创建所有表结构（幂等操作），并确保默认项目存在。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _seed_default_project()


async def _seed_default_project() -> None:
    """若 projects 表为空，插入默认项目。"""
    from backend.app.models import Project  # 延迟导入，避免循环依赖

    async with async_session_factory() as session:
        result = await session.execute(select(Project).limit(1))
        if result.scalar_one_or_none() is None:
            session.add(Project(name="默认项目", description="系统自动创建的默认项目"))
            await session.commit()

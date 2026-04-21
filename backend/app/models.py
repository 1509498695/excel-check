"""ORM 模型定义：用户、项目、角色关联、业务数据记录。"""

from __future__ import annotations

import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base


class Project(Base):
    """项目表。"""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    members: Mapped[list[UserProjectRole]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class User(Base):
    """用户表。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    is_super_admin: Mapped[bool] = mapped_column(default=False)
    primary_project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    roles: Mapped[list[UserProjectRole]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserProjectRole(Base):
    """用户-项目-角色关联表。"""

    __tablename__ = "user_project_roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(32), default="user")
    joined_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="roles")
    project: Mapped[Project] = relationship(back_populates="members")


class FixedRulesConfigRecord(Base):
    """固定规则配置持久化记录（按 project_id 隔离）。"""

    __tablename__ = "fixed_rules_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WorkbenchConfigRecord(Base):
    """工作台配置持久化记录（按 project_id + user_id 隔离）。"""

    __tablename__ = "workbench_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ExecutionRunRecord(Base):
    """最近一次执行结果记录。"""

    __tablename__ = "execution_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    total_results: Mapped[int] = mapped_column(default=0)
    execution_time_ms: Mapped[int] = mapped_column(default=0)
    total_rows_scanned: Mapped[int] = mapped_column(default=0)
    failed_sources_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    items: Mapped[list["ExecutionResultItemRecord"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class ExecutionResultItemRecord(Base):
    """单条异常结果记录。"""

    __tablename__ = "execution_result_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("execution_runs.id", ondelete="CASCADE"), index=True
    )
    sort_index: Mapped[int] = mapped_column(index=True)
    level: Mapped[str] = mapped_column(String(32), default="info")
    rule_name: Mapped[str] = mapped_column(String(255), default="")
    location: Mapped[str] = mapped_column(Text, default="")
    row_index: Mapped[int] = mapped_column(default=0)
    raw_value_json: Mapped[str] = mapped_column(Text, default="null")
    message: Mapped[str] = mapped_column(Text, default="")

    run: Mapped[ExecutionRunRecord] = relationship(back_populates="items")

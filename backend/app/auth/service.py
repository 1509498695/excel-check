"""认证业务逻辑：注册、登录、令牌生成与验证。"""

from __future__ import annotations

import datetime

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models import Project, User, UserProjectRole
from backend.config import settings


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(
    user_id: int,
    project_id: int | None = None,
) -> str:
    """生成 JWT，载荷包含 user_id 和当前选中项目。"""
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        minutes=settings.jwt_expire_minutes
    )
    payload = {
        "sub": str(user_id),
        "pid": project_id,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """解析 JWT，返回载荷字典。"""
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise ValueError("无效或过期的令牌") from exc


async def register_user(
    db: AsyncSession,
    username: str,
    password: str,
    project_id: int,
) -> User:
    """注册新用户并关联到指定项目。"""
    username = username.strip()
    existing = await db.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none():
        raise ValueError(f"用户名 '{username}' 已被占用")

    project = await db.get(Project, project_id)
    if not project:
        raise ValueError(f"项目 ID {project_id} 不存在")

    is_first_user = False
    if settings.auto_promote_first_user:
        user_count = await db.scalar(select(func.count(User.id)))
        is_first_user = user_count == 0

    user = User(
        username=username,
        hashed_password=hash_password(password),
        is_super_admin=is_first_user,
    )
    db.add(user)
    await db.flush()

    role = UserProjectRole(
        user_id=user.id,
        project_id=project_id,
        role="admin" if is_first_user else "user",
    )
    db.add(role)
    await db.commit()

    result = await db.execute(
        select(User)
        .where(User.id == user.id)
        .options(selectinload(User.roles).selectinload(UserProjectRole.project))
    )
    return result.scalar_one()


async def authenticate_user(
    db: AsyncSession,
    username: str,
    password: str,
) -> User:
    """校验用户名和密码，返回用户实例。"""
    username = username.strip()
    result = await db.execute(
        select(User)
        .where(User.username == username)
        .options(selectinload(User.roles).selectinload(UserProjectRole.project))
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        raise ValueError("用户名或密码错误")
    return user


async def get_user_with_roles(db: AsyncSession, user_id: int) -> User | None:
    """加载用户及其所有项目-角色关联。"""
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.roles).selectinload(UserProjectRole.project))
    )
    return result.scalar_one_or_none()

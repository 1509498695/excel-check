"""管理后台请求/响应模型。"""

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreateRequest(BaseModel):
    """创建项目请求。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    description: str = ""


class ProjectUpdateRequest(BaseModel):
    """更新项目请求。"""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None


class SetMemberRoleRequest(BaseModel):
    """设置成员角色请求。"""

    model_config = ConfigDict(extra="forbid")

    role: str = Field(pattern="^(admin|user)$")


class MoveMemberProjectRequest(BaseModel):
    """调整普通用户归属项目请求。"""

    model_config = ConfigDict(extra="forbid")

    target_project_id: int


class ResetUserPasswordRequest(BaseModel):
    """超级管理员重置指定用户登录密码。"""

    model_config = ConfigDict(extra="forbid")

    new_password: str = Field(min_length=4, max_length=128)

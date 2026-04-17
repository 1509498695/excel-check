"""认证模块请求/响应模型。"""

from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    """注册请求。"""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=4, max_length=128)
    project_id: int


class LoginRequest(BaseModel):
    """登录请求。"""

    model_config = ConfigDict(extra="forbid")

    username: str
    password: str


class TokenResponse(BaseModel):
    """JWT 令牌响应。"""

    access_token: str
    token_type: str = "bearer"


class UserInfo(BaseModel):
    """用户基本信息（返回给前端）。"""

    id: int
    username: str
    is_super_admin: bool
    current_project_id: int | None = None
    current_role: str | None = None
    projects: list["UserProjectInfo"] = Field(default_factory=list)


class UserProjectInfo(BaseModel):
    """用户所属项目摘要。"""

    project_id: int
    project_name: str
    role: str


class ChangePasswordRequest(BaseModel):
    """修改密码请求。"""

    model_config = ConfigDict(extra="forbid")

    old_password: str
    new_password: str = Field(min_length=4, max_length=128)

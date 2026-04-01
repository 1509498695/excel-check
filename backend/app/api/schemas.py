"""接口请求模型定义。"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DataSource(BaseModel):
    """描述单个数据源的基础配置。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["local_excel", "local_csv", "feishu", "svn"]
    path: str | None = None
    url: str | None = None
    pathOrUrl: str | None = None
    token: str | None = None


class VariableTag(BaseModel):
    """描述变量标签与数据源字段之间的映射关系。"""

    model_config = ConfigDict(extra="forbid")

    tag: str
    source_id: str
    sheet: str
    column: str
    expected_type: Literal["int", "str", "json"] | None = None


class ValidationRule(BaseModel):
    """描述单条校验规则及其参数。"""

    model_config = ConfigDict(extra="forbid")

    rule_id: str | None = None
    rule_type: str
    params: dict[str, Any] = Field(default_factory=dict)


class TaskTree(BaseModel):
    """描述一次执行请求中包含的数据源、变量和规则集合。"""

    model_config = ConfigDict(extra="forbid")

    sources: list[DataSource] = Field(default_factory=list)
    variables: list[VariableTag] = Field(default_factory=list)
    rules: list[ValidationRule] = Field(default_factory=list)

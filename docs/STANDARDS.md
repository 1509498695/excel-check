# Excel Check 开发规范

本文档是 Excel Check 的规范源文件。后续重构、接口扩展、命名整理和文档同步都以本文档为准；如需调整规范，应先更新本文档，再按单模块单切片实施。

## 1. 基本原则

- 保持兼容优先：现有 API 路径、JSON 字段、`TaskTree`、统一执行结果结构不得在无迁移方案时破坏。
- 单模块单切片：一次只整理一个明确模块，避免把命名、接口、视觉、数据库迁移混在同一轮。
- 文档与代码同改：对外行为、部署方式、接口语义、占位能力发生变化时，同步更新 `README.md`、`docs/ARCHITECTURE.md`、`docs/MODULES.md`、`frontend/README.md` 或 `CHANGELOG.md`。
- 兼容字段不删除：历史配置字段、旧 shim、旧配置迁移逻辑保留到有明确迁移窗口后再清理。

## 2. 后端规范

- Python 文件、模块、函数、变量使用 `snake_case`；Pydantic 模型、SQLAlchemy ORM 模型、异常类使用 `PascalCase`。
- FastAPI 路由按业务模块拆分：认证、管理后台、数据源、个人校验、项目校验分别保持独立 router，再由 `backend/app/api/router.py` 聚合。
- Pydantic 入参模型默认 `extra="forbid"`，除兼容历史配置的模型外，不接收未知字段。
- 对外响应继续使用现有结构：普通业务响应为 `code/msg/data`，执行响应额外含 `meta`，文件下载使用 HTTP header 传递文件名。
- 新规则优先复用 `ValidationRule.rule_type` 与规则注册中心，不为新场景复制第二套执行入口或结果结构。
- 中文 docstring 只写在模块入口、公开函数、复杂分支和兼容逻辑处，避免逐行解释语法。

## 3. 前端规范

- Vue 组件文件使用 `PascalCase.vue`；组合函数使用 `useXxx`；普通工具函数和变量使用 `camelCase`。
- API 请求集中在 `frontend/src/api/`；接口类型集中在 `frontend/src/types/`；跨模块通用响应类型放在 `frontend/src/types/api.ts`。
- Pinia store 只维护业务状态和动作，不直接散落 fetch 逻辑；请求统一走 `apiFetch` / `apiDownloadFile`。
- 页面级布局优先复用 `components/shell/`；业务组件只处理当前业务模块，不复制全局按钮、表格、状态标签样式。
- 历史 wire 字段保持原样，例如 `pathOrUrl`、`source_id`、`rule_type`、`local_path_replacement_presets`，不得为了前端命名统一直接改为驼峰字段。

## 4. API 与类型规范

- API URL 统一以 `/api/v1` 开头，前端不得硬编码主机 IP。
- 统一执行入口保持：
  - 个人校验：`POST /api/v1/engine/execute`
  - 项目校验：`POST /api/v1/fixed-rules/execute`
- `TaskTree` 稳定结构保持 `sources / variables / rules`；分页和勾选执行字段继续作为兼容扩展字段存在。
- 前端新增接口类型时优先复用：
  - `ApiResponse<TData, TMeta>`
  - `ExecutionResponse<TItem>`
  - `ApiFileResponse`
- 如果需要新增规范字段，应先新增兼容别名并同步前后端，再规划清理旧字段。

## 5. 检查与测试

- 后端基础检查：`python -m ruff check backend`。
- 后端回归：`python -m pytest backend/tests -q`。
- 前端基础检查：`cd frontend && npm run lint`。
- 前端构建：`cd frontend && npm run build`。
- 一键检查：`.\scripts\check-standards.ps1`。

## 6. 文档口径

- `README.md`：项目总览、启动、部署、常用 API。
- `docs/ARCHITECTURE.md`：稳定 SDD，记录架构、数据模型、接口和已知限制。
- `docs/MODULES.md`：模块速查，记录文件职责和逻辑分层。
- `frontend/README.md`：前端启动、构建、组件规范和联调说明。
- `CHANGELOG.md`：版本级变化，不记录分钟级流水。

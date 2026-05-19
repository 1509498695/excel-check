# Excel Check 模块速查

> 本文档用于快速定位代码边界。架构和协议请看 [ARCHITECTURE.md](ARCHITECTURE.md)，启动和联调请看 [../README.md](../README.md)。

## 1. 产品路由

| 路由 | 视图 | 作用 |
|---|---|---|
| `/` | `frontend/src/views/MainBoard.vue` | 个人校验四步工作流：数据源、变量池、规则编排、结果。 |
| `/fixed-rules` | `frontend/src/views/FixedRulesBoard.vue` | 项目校验：项目级规则配置、执行、结果与导出。 |
| `/admin` | `frontend/src/views/AdminView.vue` | 项目、成员、角色、密码管理。 |
| `/profile` | `frontend/src/views/ProfileView.vue` | 账号信息、密码、项目切换、AI 模型配置。 |
| `/login` `/register` | `frontend/src/views/LoginView.vue` `RegisterView.vue` | 登录与注册。 |

## 2. 前端目录

| 路径 | 职责 |
|---|---|
| `frontend/src/api/` | HTTP 客户端：认证、管理后台、个人校验、项目校验、AI。 |
| `frontend/src/types/` | TypeScript 类型；跨模块响应类型在 `types/api.ts`。 |
| `frontend/src/store/` | Pinia 状态：`auth`、`workbench`、`fixedRules`、`ai`。 |
| `frontend/src/router/` | 路由表与认证守卫。 |
| `frontend/src/views/` | 页面入口。 |
| `frontend/src/components/shell/` | 共享 UI：页面头、卡片、按钮、状态、表格、空态。 |
| `frontend/src/components/workbench/` | 个人校验业务组件；AI 页签入口是 `WorkbenchAiRulePanel.vue`。 |
| `frontend/src/components/workbench/ai/` | 智能规则页签的预校验、应用、历史、模板、线索同步等 composable。 |
| `frontend/src/components/fixed-rules/` | 项目校验业务组件。 |
| `frontend/src/components/profile/` | 个人设置业务组件。 |
| `frontend/src/styles/` | 全局 token、Element Plus 校准、页面域样式。 |
| `frontend/src/utils/` | `TaskTree` 组装、规则模型、API fetch、AI 输入草稿序列化等通用工具。 |

## 3. 后端目录

| 路径 | 职责 |
|---|---|
| `backend/run.py` | FastAPI 启动入口；开发路由和生产静态托管兜底。 |
| `backend/config.py` | 应用配置、环境变量、SVN 可执行路径等。 |
| `backend/app/database.py` | 异步 SQLAlchemy、建表、默认项目和默认管理员播种。 |
| `backend/app/auth/` | JWT、密码哈希、当前用户/项目依赖、认证路由。 |
| `backend/app/admin/` | 项目、成员、角色和密码管理。 |
| `backend/app/api/` | `/api/v1` 聚合路由和业务 API：数据源、个人校验、执行、项目校验、AI。 |
| `backend/app/loaders/` | 本地 Excel、SVN、飞书占位读取。 |
| `backend/app/rules/` | 统一规则引擎、领域工具、规则 handler 注册与执行。 |
| `backend/app/fixed_rules/` | 项目校验配置读写、迁移、导入预检、执行整合。 |
| `backend/app/ai/` | AI 规则助手：上下文、凭据、线索抽取、字段解析、编译、materialize、草稿历史。 |
| `backend/app/utils/` | 响应格式化、数据清洗等通用工具。 |
| `backend/tests/` | 后端接口、引擎、AI 快照和纯函数测试。 |

## 4. AI 规则助手分层

| 模块 | 职责 |
|---|---|
| `agent_service.py` | 服务编排入口：预处理、候选批判、编译、模型补语义、历史。 |
| `credentials.py` | AI 凭据加载和解密。 |
| `workbench_context.py` | 个人校验上下文和安全元数据读取。 |
| `draft_repository.py` | 草稿历史 CRUD。 |
| `workflow_hints.py` | 规则线索模型、清洗、去重、完整性判断。 |
| `field_resolver.py` | 字段精确、trim、保守模糊匹配和字段纠偏。 |
| `template/` | 短 DSL、旧模板兼容和标签常量。 |
| `hint_extractor.py` `extractors/` | 自由文本和 DSL 线索抽取入口及纯 helper。 |
| `compilers/` | 按规则类型把标准线索编译为 `RuleIntent`。 |
| `materializers/` | 将 `RuleIntent` 转为最终规则草稿定义。 |
| `providers.py` | OpenAI-compatible、Anthropic、Gemini 协议适配。 |
| `schemas.py` `prompts.py` | AI API 模型和提示词。 |

## 5. 规则引擎分层

| 模块 | 职责 |
|---|---|
| `rules/engine_core.py` | `RuleSpec` 注册中心、依赖 tag 提取和调度。 |
| `rules/domain/` | 值规范化、operator 判断、异常结果结构。 |
| `rules/infrastructure/` | 规则依赖变量提取等基础设施。 |
| `rules/handlers/` | 当前规则 handler：基础规则、固定值/组合规则、跨表规则等。 |

当前支持规则类型见 [ARCHITECTURE.md](ARCHITECTURE.md#4-规则能力)。

## 6. 文档入口

| 文档 | 作用 |
|---|---|
| [../README.md](../README.md) | 项目总览、启动、联调、API 速览。 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 稳定 SDD：架构、数据模型、协议、限制。 |
| [MODULES.md](MODULES.md) | 本文档：模块和目录速查。 |
| [STANDARDS.md](STANDARDS.md) | 开发规范和文档维护规则。 |
| [../frontend/README.md](../frontend/README.md) | 前端子项目说明。 |
| [../CHANGELOG.md](../CHANGELOG.md) | 版本级变化。 |
| [archive/](archive/) | 历史快照和一次性重构方案，不再作为当前说明入口。 |

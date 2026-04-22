# 更新日志

本日志按 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/) 风格收口，按版本而不是分钟级流水维护。  
分钟级历史日记仍在 [docs/archive/PROJECT_RECORD.md](docs/archive/PROJECT_RECORD.md)，本文件不再追加。

## [Unreleased]

- 用户可见命名统一：侧边栏、页面头部、结果面板与稳定文档中的“工作台 / 固定规则”统一更名为“个人校验 / 项目校验”；路由路径与内部实现名保持不变。
- 文档重整：根 `README.md` 收口为 6 节骨架；新建 `docs/ARCHITECTURE.md`、`docs/MODULES.md` 集中沉淀稳定文档；`PROJECT_RECORD.md` 与 `需求文档.md` 归档到 `docs/archive/`。
- 管理后台修复：超级管理员在成员表中调整自己的归属项目后，前端会立即调用现有项目切换接口，同步 JWT 与当前项目上下文，不再停留在旧项目。
- 工作台规则弹窗新增单变量选项 `包含 (in)`；前端以变量池中的单个变量作为基础字典下拉，保存时复用现有 `cross_table_mapping` 执行语义。
- 个人校验 `/` 与项目校验 `/fixed-rules` 单变量规则新增 `顺序校验`：按原始行序校验数值连续性，支持升序 / 降序、步长、自首行自动起始或手动指定起始值。
- 个人校验 `/` 与项目校验 `/fixed-rules` 的“新增规则”弹窗现统一支持 3 类入口：`单变量校验`、`组合变量校验`、`双组合变量比对`；新规则 `dual_composite_compare` 可按外层 Key 关联两个组合变量，再对多个 Value 字段执行 AND 比较。
- `dual_composite_compare` 新增 `key_check_mode` 与多条字段比较配置：可选“基准变量为准”或“双向检查”，比对项支持 `等于 / 不等于 / 大于 / 小于 / 非空`，异常会明确标出 Key、左右字段和值。
- 工作台数据源弹窗修复：`POST /api/v1/sources/local-pick` 改为以独立子进程驱动 `tkinter` 文件选择框，避免在 uvicorn 主进程里残留 Tcl 解释器与窗口焦点资源；用户在选完本地配置表后立即修改「数据源标识」时，整页不再被卡住，连续多次选择文件也不会越用越慢。

## [0.5.0] - 2026-04-20

### 新增

- 共享展示组件层：`PageHeader / SectionHeader / StatPill / StatusDot / EmptyState / DataTable`，统一工作台 / 固定规则 / 管理后台 / 个人设置四页的视觉骨架。
- `docs/MODULES.md` 与本 `CHANGELOG.md` 由 `README.md` 在「相关文档」入口暴露。

### 变更

- 全站切到 Tailwind v3 + 单 accent (`#2563eb`) 色板；`frontend/src/style.css` 收口为冷静风 token，弃用旧的 Apple 玻璃质感样式。
- 主工作台改为 4 个始终展开的模块（数据源 / 变量池 / 规则 / 结果），结果区切换为参考稿式 4 统计块 + 异常表。
- 固定规则页与管理后台改为单列三模块全宽通栏；模块头统一 `01 / 02 / 03` 浅蓝序号 + 标题 + 状态胶囊；按钮收到模块头同行右侧。
- 个人设置页改为全宽 + 内部 `max-w-md` 表单 + 横向 4 列账号信息；项目表 4 列等宽。
- 管理后台所有边框收口到 `border-gray-100 / 200`，01 项目卡片化（选中态 `border-blue-500 + bg-blue-50`），02 字段值用只读容器包裹，03 成员表用极浅完整网格线。
- 工作台顶栏移除「载入样例数据」与「执行校验」两个按钮，仅保留 `pageError` 时出现的「清除错误」。
- 规则引擎完成 `domain / infrastructure / handlers` 三层物理分层；`RULE_REGISTRY` 升级为 `RuleSpec(handler + dependent_tags)`。

### 修复

- 固定规则页步骤 3 排版崩坏（旧 `fixed-rules.css` 已删除后 `WorkbenchRuleOrchestrationPanel.vue` 引用失效）。
- 默认管理员 `admin / 123456` 缺失场景下，`POST /api/v1/auth/login` 触发受控自修复并重试一次。

## [0.4.0] - 2026-04-17

### 新增

- 多用户认证体系：JWT、注册、登录、`/auth/me`、修改密码、切换项目。
- 三级角色：超级管理员、项目管理员、普通用户；默认超级管理员 `admin / 123456` 启动时固定播种。
- 用户表 `primary_project_id` 主归属项目语义；登录默认项目按主归属确定，不再依赖 `roles[0]`。
- 管理后台 `/admin`：项目 CRUD、成员角色与归属调整、密码重置；项目管理员获得受限版后台。
- 个人设置 `/profile`：账号信息、密码修改、项目切换。
- 数据持久化迁移到 SQLite（SQLAlchemy 异步引擎）：`Project / User / UserProjectRole / FixedRulesConfigRecord / WorkbenchConfigRecord` 五张 ORM 模型。
- 前端 `apiFetch` 统一 JWT 注入与 `401` 跳转；路由全局守卫；项目切换走 SPA 内 store 重置（不再整页刷新）。

### 变更

- 默认项目 `默认项目` 设为系统保留，禁止删除；删除自定义项目时成员自动迁移到默认项目并降为普通用户。
- 密码哈希从 `passlib[bcrypt]` 切到直接使用 `bcrypt`，兼容 `bcrypt 5.x`。
- 默认项目中删除成员等同删除账号；其他项目中删除成员自动迁移到默认项目；删除统一二次确认。

## [0.3.0] - 2026-04-13

### 新增

- 组合变量：`variable_kind = composite`，同一数据源同 Sheet 的多列组合，支持 `key_column` 与 JSON 映射预览。
- 规则类型 `composite_condition_check`：组合变量条件分支校验，支持「全局筛选 + 分支筛选 + 分支校验」结构，操作符覆盖 `eq / ne / gt / lt / not_null / unique / duplicate_required`。
- 主工作台步骤 3 与 `/fixed-rules` 同构的规则组编排：规则组 CRUD、当前组规则 CRUD、分页（`20 / 页`）。

### 变更

- 工作台规则状态由 `useWorkbenchStore` 维护；与 `fixedRules` store 完全隔离。
- 抽取共用规则模型工具 `frontend/src/utils/ruleOrchestrationModel.ts`。

## [0.2.0] - 2026-04-10

### 新增

- 固定规则模块独立持久化：`/fixed-rules` 拥有自己的 `sources / variables / groups / rules`，`version = 4` 配置写入 `backend/.runtime/fixed-rules/default.json`。
- 固定规则页变量池：与主工作台相同的「来源 → Sheet → 列名」下拉，并支持组合变量预览。
- 规则弹窗：从「文件路径 + Sheet + 列」改为直接绑定固定规则页变量池中的 `target_variable_tag`；规则名称按 `sheet-目标列-规则选择名称(+值)` 自动生成。
- 固定规则配置读取支持 `meta.config_issues` 非阻断告警：本地路径失效 / Sheet / 列不存在不再阻塞页面，仅在数据源行标 `路径失效`。

### 变更

- 旧版 `version = 2 / 3` 固定规则配置在读取时自动迁移至 `version = 4`。
- `/fixed-rules` 与主工作台数据源 / 变量池完全隔离，互不影响。

## [0.1.0] - 2026-04-08

### 新增

- 主工作台四步骨架（数据源 / 变量池 / 规则 / 结果）+ 统一执行引擎 `POST /api/v1/engine/execute`。
- 数据源能力：`/api/v1/sources/capabilities / local-pick / metadata / column-preview / composite-preview`。
- 规则注册表与 5 类规则：`not_null / unique / fixed_value_compare / cross_table_mapping / composite_condition_check`。
- 固定规则模块独立路由 `/fixed-rules` 与接口 `/api/v1/fixed-rules/{config,svn-update,execute}`。
- 本地文件选择走 `tkinter` 桌面对话框，避免浏览器拿不到本地绝对路径的问题。
- SVN CLI 自动探测：默认按 `SVN_EXECUTABLE` 环境变量、`PATH`、Windows 下 TortoiseSVN 安装路径顺序解析。

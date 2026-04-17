# 项目记录文档

项目目录：`D:\project\excel-check`

## 进度记录 2026-04-15 13:30

### 本次目标
- 修复切换项目后工作台和固定规则页数据不跟随切换的问题，防止空项目残留旧数据。

### 本次完成
- `frontend/src/store/workbench.ts`：`loadFromServer` 改为先重置所有状态（sources / variables / ruleGroups / orchestrationRules / abnormalResults / executionMeta / 缓存）再合并服务端返回，空 `{}` 不再沿用旧内存。
- `frontend/src/store/fixedRules.ts`：新增 `resetState()` action，将 config、UI 标志、执行结果和元数据缓存恢复到初始默认态。
- `frontend/src/App.vue` 和 `frontend/src/views/ProfileView.vue`：项目切换去掉 `window.location.reload()`，改为 `fixedRules.resetState()` + 并行 `workbench.loadFromServer()` / `fixedRules.loadConfig()` + `router.push('/')`。

### 回归结果
- `python -m pytest backend/tests -q` → `40 passed`
- `cd frontend && npm run build` → 通过
- API 隔离验证：项目 A 保存数据源 → 切换项目 B → 工作台为空 → 切回项目 A 数据恢复

### 当前项目进度

#### 已完成功能
- JWT 用户认证体系（注册 / 登录 / 令牌管理 / 首用户自动超管）
- 三级角色权限（超级管理员 / 项目管理员 / 普通用户）
- 多项目数据隔离（固定规则按 `project_id`，工作台按 `project_id + user_id`）
- 切换项目后工作台与固定规则数据自动同步（SPA 内 store 重载，无整页刷新）
- SQLite 数据持久化（SQLAlchemy 异步引擎）
- 管理后台（项目管理 + 成员管理）
- 个人中心（修改密码 + 切换项目）
- 四步工作台完整校验主流程
- 固定规则模块完整持久化与执行闭环
- 主工作台步骤 3 规则组编排

#### 已实现但未打通 / 占位功能
- `regex` 规则已注册但返回空结果
- `svn` 作为主工作台独立 source 类型的完整闭环未开放
- `feishu` 数据源为占位实现
- CSV 变量池下拉提取未开放
- Alembic 数据库迁移脚本未配置

#### 未开始功能
- 固定规则结果导出
- 固定规则多配置集切换
- 多用户协同编辑冲突处理

### 文档同步
- 更新 `README.md`
- 更新 `PROJECT_RECORD.md`
- 更新 `CHANGELOG.md`
- 更新 `frontend/README.md`
- 更新 `需求文档.md`

### 未完成项与风险
- 工作台自动保存的 2 秒防抖在多标签页同时编辑时可能产生覆盖。
- Alembic 迁移脚本尚未配置。

## 进度记录 2026-04-14 20:30

### 本次目标
- 将 Excel Check 从单用户文件存储架构升级为多用户 Web 应用：新增 JWT 认证、角色权限、项目隔离、数据库持久化、管理后台和个人中心。

### 本次完成
- 后端新增 `backend/app/database.py`（SQLAlchemy 异步引擎 + SQLite）和 `backend/app/models.py`（`Project`、`User`、`UserProjectRole`、`FixedRulesConfigRecord`、`WorkbenchConfigRecord` 五张表）。
- 后端新增 `backend/app/auth/` 模块：注册 / 登录 / JWT 令牌生成与验证 / `CurrentUserContext` 权限依赖注入。
- 后端新增 `backend/app/admin/` 模块：项目增删改查 + 项目成员管理 API。
- 后端新增 `backend/app/api/workbench_api.py`：工作台配置的数据库读写（按 `project_id + user_id` 隔离）。
- 固定规则 API 从文件 IO 迁移到数据库存储（`FixedRulesConfigRecord`），新增 `db_service.py` 和 `parse_raw_fixed_rules_config` 兼容遗留格式。
- 密码哈希从 `passlib[bcrypt]` 切换为直接使用 `bcrypt` 库，解决 `bcrypt 5.x` 兼容性问题。
- 前端新增 `apiFetch.ts`（JWT 注入 + 401 跳转）、`auth.ts` store、`LoginView.vue`、`RegisterView.vue`、`AdminView.vue`、`ProfileView.vue`。
- 前端路由新增 `/login`、`/register`、`/admin`、`/profile`，全局守卫保护需登录路由。
- 前端 `App.vue` 新增用户下拉菜单和管理后台入口。
- 后端测试 `conftest.py` 新增 `test_db`、`_auth_context`、`auth_headers`、`test_project_id`、`seed_fixed_rules_config` fixtures。
- `test_fixed_rules_api.py` 从文件预填充改为数据库预填充，所有 23 个测试通过认证。

### 回归结果
- `python -m pytest backend/tests -q` → `40 passed`
- `cd frontend && npm run build` → 通过
- `GET http://127.0.0.1:8000/health` → `200`
- `GET http://127.0.0.1:5173` → `200`

### 当前项目进度

#### 已完成功能
- JWT 用户认证体系（注册 / 登录 / 令牌管理 / 首用户自动超管）
- 三级角色权限（超级管理员 / 项目管理员 / 普通用户）
- 多项目数据隔离（固定规则按 `project_id`，工作台按 `project_id + user_id`）
- SQLite 数据持久化（SQLAlchemy 异步引擎）
- 管理后台（项目管理 + 成员管理）
- 个人中心（修改密码 + 切换项目）
- 四步工作台完整校验主流程
- 固定规则模块完整持久化与执行闭环
- 主工作台步骤 3 规则组编排

#### 已实现但未打通 / 占位功能
- `regex` 规则已注册但返回空结果
- `svn` 作为主工作台独立 source 类型的完整闭环未开放
- `feishu` 数据源为占位实现
- CSV 变量池下拉提取未开放
- Alembic 数据库迁移脚本未配置

#### 未开始功能
- 固定规则结果导出
- 固定规则多配置集切换
- 多用户协同编辑冲突处理

### 规范化调整
- 保持 `POST /api/v1/engine/execute` 不变
- 保持 `TaskTree -> sources / variables / rules` 不变
- 保持统一结果结构 `code / msg / meta / data.abnormal_results` 不变
- 固定规则 API 所有端点新增 `CurrentUserContext` 认证依赖

### 文档同步
- 更新 `README.md`
- 更新 `PROJECT_RECORD.md`
- 更新 `CHANGELOG.md`
- 更新 `frontend/README.md`
- 更新 `需求文档.md`

### 未完成项与风险
- 当前使用内存 SQLite 默认路径，生产部署需配置持久化数据库路径。
- Alembic 迁移脚本尚未配置，表结构变更需手动管理。
- 工作台自动保存的 2 秒防抖在多标签页同时编辑时可能产生覆盖。

### 下一步建议
1. 配置 Alembic 迁移框架，固化数据库 schema 变更管理。
2. 实现工作台自动保存的乐观并发控制。
3. 按需添加操作审计日志。

## 进度记录 2026-04-14 16:30

### 本次目标
- 将主工作台步骤 3 从「三卡片静态模板」升级为与固定规则页同构的规则组编排能力，并与 `/fixed-rules` 数据隔离。

### 本次完成
- 新增 `frontend/src/utils/ruleOrchestrationModel.ts` 与 `workbenchOrchestrationRules.ts`，`fixedRules` store 改为复用前者中的归一化与校验工具函数。
- `workbench` store 引入 `ruleGroups`、`orchestrationRules`、分页与 CRUD 动作；`buildTaskTreePayload` 改为消费映射后的引擎规则；`executeValidation` 增加无规则 / 待修复规则拦截。
- 扩展 `frontend/src/utils/taskTree.ts`：`not_null`/`unique` 保留可选 `rule_name`/`location`；新增 `fixed_value_compare` 与 `composite_condition_check` 归一化。
- 新增 `WorkbenchRuleOrchestrationPanel.vue`（自固定规则页交互裁剪而来），`MainBoard` 步骤 3 接入；删除 `RuleComposerPanel.vue`。
- 「加载样例」编排改为四条固定规则形态；`workbenchMeta` 中 `STATIC_RULE_TEMPLATES` 调整为与新引擎类型展示一致。
- 同步更新 `README.md`、`CHANGELOG.md`、`frontend/README.md`、`需求文档.md`、`MODULES.md`。

### 回归结果
- `python -m pytest backend/tests -q`：`40 passed`
- `cd frontend && npm run build`：通过
- 使用 `httpx` + `ASGITransport` 对 `minimal_rules.xlsx` 与样例等价 `TaskTree` 实测：`abnormal_results = 4`（`2 not_null + 2 unique`）

## 进度记录 2026-04-13 12:00

### 本次目标
- 将「Excel Check 项目模块作用一览」落实为仓库内可维护文档，便于新人与协作快速对照架构。

### 本次完成
- 新增根目录 `MODULES.md`，内容与已确认计划一致：产品双入口、前端 `src` 分层、后端 `app` 分层、文档索引及逻辑分层 mermaid 简图；文内链接统一为相对路径。
- 更新根目录 `README.md` 的「相关文档」小节，增加指向 `MODULES.md` 的链接。
- 同步更新 `CHANGELOG.md` 本条记录。

### 回归结果
- 本次为文档变更，未改运行时代码；未额外执行构建或 pytest。

## 进度记录 2026-04-13 10:59

### 本次目标
- 在不改首页结构和交互逻辑的前提下，优化工作台首页 `/` 的视觉质感与文案表达。
- 修复共享头部、步骤卡和首页引导区的中文乱码与提示冗余问题。

### 本次完成
- 已在 `frontend/src/views/MainBoard.vue` 中收口首页核心文案，统一为更短、更专业的操作导向表达。
- 已在 `frontend/src/components/workbench/SectionBlock.vue` 中统一步骤状态文案，首页步骤卡与后续复用区域保持一致。
- 已在 `frontend/src/App.vue` 中同步优化共享头部品牌副标题与导航表达。
- 已在 `frontend/src/style.css` 中完成首页与共享壳层的视觉精修：
  - 收敛背景层次、强调色、边框、阴影和圆角
  - 强化顶部品牌栏、概览区、流程引导条和步骤卡的留白与层级
  - 补充导航、按钮和卡片的柔和 hover 反馈
- 本次未改动 DOM 层级、Grid / Flex 布局骨架、类名、ID、Pinia store 字段和事件绑定。

### 回归结果
- `cd frontend && npm run build` -> 通过
- `GET http://127.0.0.1:8000/health` -> `200`
- `GET http://127.0.0.1:5173` -> `200`
- `GET http://127.0.0.1:5173/fixed-rules` -> `200`
- `POST http://127.0.0.1:8000/api/v1/engine/execute` -> `Execution Completed / total_rows_scanned = 8 / failed_sources = [] / abnormal_results = 5`

## 进度记录 2026-04-13 10:29

### 本次目标
- 继续完成固定规则页的组合变量规则能力，让组合变量不再只停留在预览和持久化层，而是能真正参与固定规则执行。
- 把固定规则弹窗收口成“双模式”：
  - 单变量走简单规则
  - 组合变量走条件分支校验
- 补齐后端测试、前端回填、规则摘要和本地联调验证。

### 本次完成
- 固定规则前端类型与后端 schema 正式引入 `composite_condition_check` 与 `composite_config`。
- 固定规则弹窗已支持按目标变量类型切换编辑器：
  - 单变量：比较 / 非空 / 唯一
  - 组合变量：全局筛选、分支筛选、分支校验
- 组合变量规则支持 `Key` 作为 JSON 映射键字段参与条件判断；执行期内部映射为 `__key__`。
- 组合变量规则支持：
  - 筛选条件：`eq / ne / gt / lt / not_null`
  - 校验条件：`eq / ne / gt / lt / not_null / unique / duplicate_required`
  - 比较类右值来源：固定值或字段
- 固定规则页规则列表摘要已能展示组合变量规则的全局筛选、分支命中条件和分支校验条件。
- 本地 Excel 组合变量装载已改为可执行行集，执行期会展开为：`__key__ + 成员列 + _row_index`。
- 新增并通过固定规则 API 回归测试，覆盖：
  - 组合变量规则保存与回填
  - 单变量/组合变量绑定约束
  - 非法组合规则配置拦截
  - 示例场景执行结果
- 回归验证：
  - `python -m pytest backend/tests -q` -> `40 passed`
  - `cd frontend && npm run build` -> 通过
  - `GET http://127.0.0.1:8000/health` -> `200`
  - `GET http://127.0.0.1:5173` -> `200`
  - `GET http://127.0.0.1:5173/fixed-rules` -> `200`

## 进度记录 2026-04-11 13:06

### 本次目标
- 修复固定规则页在读取已保存但本地路径失效的配置时出现 `500 Internal Server Error` 的问题。
- 保证固定规则页仍能正常打开、保留配置，并给出可直接修复的中文提示。

### 本次完成
- 后端将固定规则配置读取拆分为“结构校验”和“运行时路径校验”两层：
  - 结构性非法配置继续严格失败
  - 运行时可修复问题降级返回 `200 + meta.config_issues`
- 新增固定规则配置问题返回结构 `config_issues`，当前已覆盖：
  - 本地路径失效
  - 变量引用的 Sheet 不存在
  - 变量引用的列不存在
- 修复了此前遗漏的来源级运行时校验：即使固定规则页当前只有数据源、还没创建变量或规则，也能在读取时发现失效路径。
- 固定规则页前端现在会：
  - 保留已加载配置
  - 在页面顶部展示中文 warning
  - 在数据源接入管理中把对应数据源标记为 `路径失效`
  - 在存在阻断问题时禁用执行入口
- `PUT /api/v1/fixed-rules/config` 与 `POST /api/v1/fixed-rules/execute` 继续保持严格校验；失效路径未修复时会返回明确中文 `400`。
- 顺手修正当前 `backend/.runtime/fixed-rules/default.json` 中残留的历史乱码分组名称。
- 完成回归验证：
  - `python -m pytest backend/tests -q` -> `33 passed`
  - `cd frontend && npm run build` -> 通过
  - `GET http://127.0.0.1:8000/health` -> `200`
  - `GET http://127.0.0.1:5173/fixed-rules` -> `200`
  - 失效路径专项回归：
    - `GET /api/v1/fixed-rules/config` -> `200 + meta.config_issues`
    - `PUT /api/v1/fixed-rules/config` -> `400`
    - `POST /api/v1/fixed-rules/execute` -> `400`

### 当前项目进度

#### 已完成功能
- 四步工作台仍可完成本地 Excel 校验主流程。
- 固定规则模块 `/fixed-rules` 已支持独立持久化的数据源、变量池、规则组和固定规则配置。
- 固定规则页当前已具备：
  - 数据源接入管理
  - 变量池构建
  - 单变量选规
  - 比较 / 非空 / 唯一校验
  - 统一结果看板
  - `SVN 更新`
- 固定规则配置读取现在对运行时失效路径具备容错能力，页面不再因为旧配置失效而整体打不开。

#### 已实现但未打通 / 占位功能
- 固定规则页变量提取与预览能力优先稳定支持本地 Excel；CSV、飞书和更复杂来源暂未提供同等体验。
- 组合变量已支持在固定规则页持久化和预览，但当前固定规则执行仍只消费单变量。
- `svn` 作为主工作台独立 `source` 类型的完整闭环仍未开放；当前已打通的是固定规则模块的工作副本更新能力。
- 飞书数据源仍为占位实现。
- 动态规则平台仍未重新开放；步骤 3 继续是纯静态规则工作区。

#### 未开始功能
- 固定规则结果导出
- 固定规则多配置集切换
- `regex` 规则闭环
- 结果筛选、高级搜索与报告导出

### 规范化调整
- 保持 `POST /api/v1/engine/execute` 不变。
- 保持 `POST /api/v1/fixed-rules/execute` 不变。
- 保持 `TaskTree -> sources / variables / rules` 不变。
- 保持统一结果结构 `code / msg / meta / data.abnormal_results` 不变。
- 固定规则页的 `config_issues` 仅作为 `GET /api/v1/fixed-rules/config` 的读取态扩展，不扩散到主工作台接口。

### 文档同步
- 更新 `README.md`
- 更新 `PROJECT_RECORD.md`
- 更新 `CHANGELOG.md`
- 更新 `frontend/README.md`
- 更新 `需求文档.md`

### 未完成项与风险
- 当前终端环境没有浏览器自动化回放能力，本轮对固定规则页的验收以接口回归、前端构建、页面可访问性与代码路径检查为主。
- 固定规则页当前配置问题提示已能覆盖路径失效、Sheet 失效和列失效，但仍依赖用户手动进入数据源/变量模块完成修复。
- 历史文档记录会保留早期演进说明；本轮只补充当前真实行为，不删除历史阶段性记录。

### 下一步建议
1. 如果后续还会出现“历史配置拖垮页面”的问题，优先沿用 `读取可降级、保存和执行继续严格` 这条策略，不再回到整页 500。
2. 如果继续增强固定规则模块，建议优先考虑“结果导出”或“多配置集切换”其中一个独立切片。

## 进度记录 2026-04-11 12:10

### 本次目标
- 修复界面上可见的 `????` 乱码文案。
- 优先处理主工作台和固定规则页共用的变量池面板，避免两个页面同时出现显示异常。

### 本次完成
- 确认乱码根因不是浏览器编码问题，而是 `frontend/src/components/workbench/VariablePoolPanel.vue` 中残留了大量 `????` 占位文案。
- 已恢复该复用组件中的正常中文文案，覆盖：
  - 顶部按钮
  - 表格表头与操作按钮
  - 单变量弹窗
  - 组合变量弹窗
  - JSON 预览区
  - 变量详情弹窗
- 顺手修复了一处 `Sheet` 选择占位乱码。
- 本次没有改动接口、状态模型、`TaskTree` 或固定规则 `version = 4` 配置结构。
- 完成回归验证：
  - `cd frontend && npm run build` -> 通过
  - `http://127.0.0.1:8000/health` -> `200`
  - `http://127.0.0.1:5173` -> `200`
  - `http://127.0.0.1:5173/fixed-rules` -> `200`

### 当前项目进度

#### 已完成功能
- 四步工作台仍可完成本地 Excel 校验主流程。
- 固定规则模块 `/fixed-rules` 仍保持独立持久化的数据源、变量池与规则配置。
- 主工作台步骤 2 与固定规则页变量池模块的中文界面文案已经恢复正常显示。

#### 已实现但未打通 / 占位功能
- 固定规则页当前变量提取与预览能力先稳定支持本地 Excel；CSV、飞书与更复杂来源暂未提供同等体验。
- 组合变量已支持在固定规则页持久化和预览，但当前固定规则执行只消费单变量。
- `svn` 作为主工作台独立 `source` 类型的完整闭环仍未开放；当前已打通的是固定规则模块的工作副本更新能力。
- 飞书数据源仍为占位实现。
- 动态规则平台能力仍未重新开放；步骤 3 继续是纯静态规则工作区。

#### 未开始功能
- 固定规则结果导出
- 固定规则多配置集切换
- `regex` 规则闭环
- 结果筛选、高级搜索与报告导出

### 规范化调整
- 保持 `POST /api/v1/engine/execute` 不变。
- 保持 `POST /api/v1/fixed-rules/execute` 不变。
- 保持 `TaskTree -> sources / variables / rules` 不变。
- 保持统一结果结构 `code / msg / meta / data.abnormal_results` 不变。

### 文档同步
- 更新 `README.md`
- 更新 `PROJECT_RECORD.md`
- 更新 `CHANGELOG.md`
- 更新 `frontend/README.md`
- 更新 `需求文档.md`

### 未完成项与风险
- 本次只修复当前已定位到的界面文案乱码，不扩展到历史文档中的旧记录。
- 当前环境没有浏览器自动化截图回放，本轮页面验收以源码扫描、前端构建和运行中的页面可访问性检查为主。

### 下一步建议
1. 如果后续还发现零散乱码，优先继续扫描复用组件和近期重写过的页面模板。
2. 若要彻底规避类似问题，建议后续避免在终端里用错误编码批量回写 `.vue` 文件。

## 进度记录 2026-04-10 21:07

### 本次目标
- 继续完成固定规则页 `/fixed-rules` 的独立持久化切片，不回退已经进入 `version = 4` 的后端结构。
- 把固定规则页收口为“固定规则页自己的数据源接入管理 + 变量池构建 + 变量选规”模型。
- 保证 `/fixed-rules` 与主工作台 `/` 的数据源、变量池彻底隔离，并完成完整联调与文档同步。

### 本次完成
- `FixedRulesBoard.vue` 已完成固定规则页主界面收口：
  - 在规则组导航上方新增 `数据源接入管理` 与 `变量池构建`
  - 两个模块直接复用工作台 UI，但底层连接固定规则页自己的 `useFixedRulesStore()`
  - 变更后会立即调用 `/api/v1/fixed-rules/config` 持久化保存
- 固定规则弹窗已移除旧的路径绑定字段：
  - `规则文件路径`
  - `读取结构`
  - `Sheet`
  - `目标列`
- 固定规则弹窗现改为从固定规则页变量池选择 `目标变量`，并展示只读摘要：
  - 来源数据源
  - Sheet
  - 列名
  - 路径
- 固定规则前端状态模型继续沿用并收口到 `version = 4`：
  - `sources`
  - `variables`
  - `groups`
  - `rules`
- 固定规则绑定模型已改为 `target_variable_tag`；当前固定规则执行只允许绑定单变量，组合变量继续支持持久化、编辑和预览，但不进入当前规则执行链路。
- 固定规则页已补齐级联清理行为：
  - 删除数据源时，自动删除其下变量与依赖规则
  - 删除变量时，自动删除依赖它的规则
  - 变量改名时，同步替换规则里的目标变量引用
- 固定规则页与主工作台页的数据源、变量池已经隔离，两边新增内容不会互相显示。
- 完成运行态真实联调：
  - 固定规则页保存 `1` 个数据源、`3` 个变量（含 `1` 个组合变量）、`3` 条规则后刷新仍可回填
  - `/fixed-rules` 执行结果：`Execution Completed / total_rows_scanned = 6 / failed_sources = [] / abnormal_results = 4`
  - `/api/v1/engine/execute` 主工作台最小链路保持：`Execution Completed / total_rows_scanned = 8 / failed_sources = [] / abnormal_results = 5`
- 完成回归验证：
  - `python -m pytest backend/tests -q` -> `30 passed`
  - `cd frontend && npm run build` -> 通过
  - `http://127.0.0.1:8000/health` -> `200`
  - `http://127.0.0.1:5173` -> `200`
  - `http://127.0.0.1:5173/fixed-rules` -> `200`

### 当前项目进度

#### 已完成功能
- 四步工作台仍可完成本地 Excel 校验主流程。
- 固定规则模块 `/fixed-rules` 当前已支持：
  - 固定规则页自己的数据源接入管理
  - 固定规则页自己的变量池构建
  - 单变量与组合变量持久化、编辑与预览
  - `version = 4` 固定规则配置持久化与旧版 `version = 3` 自动迁移
  - 比较 / 非空 / 唯一三类固定规则
  - 目标变量选规、规则组与规则 CRUD
  - 聚合执行与统一结果看板
  - `SVN 更新`

#### 已实现但未打通 / 占位功能
- 固定规则页当前变量提取与预览能力先稳定支持本地 Excel；CSV、飞书与更复杂来源暂未提供同等体验。
- 组合变量已支持在固定规则页持久化和预览，但当前固定规则执行只消费单变量。
- `svn` 作为主工作台独立 `source` 类型的完整闭环仍未开放；当前已打通的是固定规则模块的工作副本更新能力。
- 飞书数据源仍为占位实现。
- 动态规则平台能力仍未重新开放；步骤 3 继续是纯静态规则工作区。

#### 未开始功能
- 固定规则结果导出
- 固定规则多配置集切换
- `regex` 规则闭环
- 结果筛选、高级搜索与报告导出

### 规范化调整
- 保持 `POST /api/v1/engine/execute` 不变。
- 保持 `POST /api/v1/fixed-rules/execute` 不变。
- 保持 `TaskTree -> sources / variables / rules` 不变。
- 保持统一结果结构 `code / msg / meta / data.abnormal_results` 不变。
- 固定规则页通过 `/api/v1/fixed-rules/config` 统一持久化 `sources / variables / groups / rules`，不新增独立的 source/variable 持久化接口。

### 文档同步
- 更新 `README.md`
- 更新 `PROJECT_RECORD.md`
- 更新 `CHANGELOG.md`
- 更新 `frontend/README.md`
- 更新 `需求文档.md`

### 未完成项与风险
- 当前终端环境没有浏览器自动化回放能力，本轮对固定规则页的前端验收以代码路径检查、前端构建、HTTP 联调和页面可访问性为主。
- 固定规则页当前只让单变量进入规则执行；若后续要支持组合变量规则，需要单独定义规则语义和执行协议。
- 现有历史文档中仍保留早期 `version = 2 / version = 3 / 规则级文件绑定` 演进记录，本轮已补充最新现状说明，但历史记录不会被删除。

### 下一步建议
1. 如果继续扩展固定规则模块，优先考虑“固定规则结果导出”或“多配置集切换”其中一个切片。
2. 如果后续需要让组合变量参与固定规则执行，建议先单独定义一类以 JSON 映射为输入的规则类型，而不是直接复用当前单列规则。

## 进度记录 2026-04-10 16:21

### 本次目标
- 补齐 `/fixed-rules` 规则弹窗的默认规则名生成逻辑。
- 把 `unique` 的用户可见文案统一收口为 `唯一校验`。
- 在不修改固定规则后端协议的前提下，完成一次前端交互切片回归和文档同步。

### 本次完成
- `FixedRulesBoard.vue` 现在会按表单自动生成默认规则名：
  - 比较类：`sheet-目标列-规则选择名称+值`
  - 非比较类：`sheet-目标列-规则选择名称`
- 默认规则名只在“用户未手动改名”时自动同步；如果用户主动修改或清空规则名称，后续字段变化不再自动覆盖。
- 保存前继续保留 `规则名称不能为空` 的前端校验；由于有默认名称，正常新增流程无需手填，但用户主动清空后仍无法保存。
- `unique` 的用户可见文案已统一改为 `唯一校验`，覆盖：
  - 规则选择下拉
  - 规则摘要
  - 规则名称占位提示
  - 默认规则名
- 本次未改动固定规则后端协议和执行链路，`rule_type = unique` 保持不变。
- 完成回归验证：
  - `python -m pytest backend/tests -q` -> `29 passed`
  - `cd frontend && npm run build` -> 通过
- 运行中的本地服务继续可访问：
  - `http://127.0.0.1:8000/health` -> `200`
  - `http://127.0.0.1:5173` -> `200`
  - `http://127.0.0.1:5173/fixed-rules` -> `200`
- 固定规则与主工作台联调链路保持不变：
  - `/fixed-rules` -> `Execution Completed / total_rows_scanned = 3 / failed_sources = [] / abnormal_results = 3`
  - `/api/v1/engine/execute` -> `Execution Completed / total_rows_scanned = 8 / failed_sources = [] / abnormal_results = 5`

### 当前项目进度

#### 已完成功能
- 四步工作台仍可完成本地 Excel 校验主流程。
- 固定规则模块 `/fixed-rules` 当前已支持：
  - 规则级文件绑定
  - 规则组与规则 CRUD
  - `version = 3` 配置持久化与旧版迁移
  - 比较 / 非空 / 唯一三类固定规则
  - 默认规则名自动生成与手动改名保护
  - 聚合执行与统一结果看板
  - `SVN 更新`

#### 已实现但未打通 / 占位功能
- `svn` 作为主工作台独立 `source` 类型的完整闭环仍未开放；当前已打通的是固定规则模块的工作副本更新能力。
- 飞书数据源仍为占位实现。
- 动态规则平台能力仍未重新开放；步骤 3 继续是纯静态规则工作区。

#### 未开始功能
- 固定规则结果导出
- 固定规则多配置集切换
- `regex` 规则闭环
- 结果筛选、高级搜索与报告导出

### 规范化调整
- 保持 `POST /api/v1/engine/execute` 不变。
- 保持 `TaskTree -> sources / variables / rules` 不变。
- 保持统一结果结构 `code / msg / meta / data.abnormal_results` 不变。
- 固定规则模块继续通过 `/api/v1/fixed-rules/*` 和后端内部临时 `TaskTree` 复用已有执行引擎。

### 文档同步
- 更新 `README.md`
- 更新 `PROJECT_RECORD.md`
- 更新 `CHANGELOG.md`
- 更新 `frontend/README.md`
- 更新 `需求文档.md`

### 未完成项与风险
- 当前终端环境没有浏览器自动化回放能力，本轮对“默认规则名自动同步”的验收以代码逻辑校验、前端构建和运行态服务可访问性为主。
- 固定规则模块当前仍只支持本地 Excel 文件，不扩展到 CSV、飞书或多配置集。

### 下一步建议
1. 如果继续增强固定规则模块，优先考虑“结果导出”或“多配置集切换”其中一个切片。
2. 如果后续继续扩展固定规则类型，建议继续沿用“默认规则名可自动生成，但用户手动改名优先”的交互约束。

## 进度记录 2026-04-10 15:57

### 本次目标
- 扩展 `/fixed-rules` 的“新增固定规则”弹窗，把 `比较符` 收口为 `规则选择`，并新增 `非空校验`、`唯一校验`。
- 升级固定规则配置协议，使固定规则模块不再只支持比较型规则。
- 完成前后端联调回归，并同步更新主 README、前端 README、变更日志和需求文档。

### 本次完成
- 前端 `FixedRulesBoard` 已将弹窗标签改为 `规则选择`，下拉当前固定为 6 项：
  - `等于 (=)`
  - `不等于 (!=)`
  - `大于 (>)`
  - `小于 (<)`
  - `非空校验`
  - `唯一校验`
- 比较类规则仍使用 `operator + expected_value`；非空和唯一规则会隐藏 `比较值`，保存时自动清理残留比较值。
- 固定规则前端状态和后端协议已升级为显式 `rule_type`：
  - `fixed_value_compare`
  - `not_null`
  - `unique`
- 固定规则持久化结构已从 `version = 2` 升级为 `version = 3`；后端读取旧版比较型配置时会自动迁移，不要求手工清空旧数据。
- 固定规则转临时 `TaskTree` 时已按 `rule_type` 分发到对应执行规则；`/fixed-rules` 结果中的 `rule_name` 和 `location` 也已补齐兼容读取。
- 新增并通过固定规则相关后端测试，覆盖：
  - `version = 3` 配置保存与读取
  - `version = 2` 比较型旧配置自动迁移
  - 比较 / 非空 / 唯一三类固定规则执行
  - 混合规则集执行
- 完成回归验证：
  - `python -m pytest backend/tests -q` -> `29 passed`
  - `cd frontend && npm run build` -> 通过
- 已重启本地前后端服务并确认：
  - `http://127.0.0.1:8000/health` -> `200`
  - `http://127.0.0.1:5173` -> `200`
  - `http://127.0.0.1:5173/fixed-rules` -> `200`
- 使用运行中的固定规则服务完成一次真实最小联调：
  - 规则：`INT_ID > 0`、`INT_ID 非空`、`INT_ID 唯一校验`
  - 结果：`Execution Completed / total_rows_scanned = 3 / failed_sources = [] / abnormal_results = 3`
- 主工作台最小链路再次回归：
  - `POST /api/v1/engine/execute`
  - `Execution Completed / total_rows_scanned = 8 / failed_sources = [] / abnormal_results = 5`

### 当前项目进度

#### 已完成功能
- 四步工作台仍可完成本地 Excel 校验主流程。
- 固定规则模块 `/fixed-rules` 当前已支持：
  - 规则级文件绑定
  - 规则组与规则 CRUD
  - `version = 3` 配置持久化与旧版迁移
  - 比较 / 非空 / 唯一三类固定规则
  - 聚合执行与统一结果看板
  - `SVN 更新`

#### 已实现但未打通 / 占位功能
- `svn` 作为主工作台独立 `source` 类型的完整闭环仍未开放；当前已打通的是固定规则模块的工作副本更新能力。
- 飞书数据源仍为占位实现。
- 动态规则平台能力仍未重新开放；步骤 3 继续是纯静态规则工作区。

#### 未开始功能
- 固定规则结果导出
- 固定规则多配置集切换
- `regex` 规则闭环
- 结果筛选、高级搜索与报告导出

### 规范化调整
- 保持 `POST /api/v1/engine/execute` 不变。
- 保持 `TaskTree -> sources / variables / rules` 不变。
- 保持统一结果结构 `code / msg / meta / data.abnormal_results` 不变。
- 固定规则模块继续通过 `/api/v1/fixed-rules/*` 和后端内部临时 `TaskTree` 复用已有执行引擎。

### 文档同步
- 更新 `README.md`
- 更新 `PROJECT_RECORD.md`
- 更新 `CHANGELOG.md`
- 更新 `frontend/README.md`
- 更新 `需求文档.md`

### 未完成项与风险
- 当前终端环境仍没有浏览器自动化回放能力，本轮以前后端构建、运行态访问和真实接口回归作为联调依据。
- 固定规则模块当前仍只支持本地 Excel 文件，不扩展到 CSV、飞书或多配置集。

### 下一步建议
1. 如果继续增强固定规则模块，优先考虑“结果导出”或“多配置集切换”其中一个切片。
2. 如果后续需要让固定规则支持更多规则类型，建议继续沿用 `rule_type + 条件字段` 的协议方式，不再回到单一比较模型。

## 进度记录 2026-04-09 12:28

### 本次目标
- 修复固定规则模块在当前 Windows 环境下无法发现 `svn.exe` 的问题。
- 完成 `/fixed-rules` 的真实 `SVN 更新` 联调，并确认共享执行链路不受影响。
- 同步更新项目说明、前端说明、变更日志和需求文档。

### 本次完成
- 后端 `svn` 发现逻辑已改为分层解析：
  - 显式配置的 `svn_executable`
  - `PATH` 中的 `svn`
  - Windows 下 TortoiseSVN 常见安装路径与注册表信息
- `backend/config.py` 已支持环境变量 `SVN_EXECUTABLE` 覆盖默认值，未设置时仍回退到 `svn`。
- 新增 `backend/tests/test_svn_manager.py`，覆盖：
  - 显式绝对路径命中
  - `PATH` 命中
  - Windows 自动探测命中
  - 更新成功返回 `used_executable`
  - CLI 缺失时的明确中文错误
- 完成回归验证：
  - `python -m pytest backend/tests -q` -> `26 passed`
  - `cd frontend && npm run build` -> 通过
- 重启本地前后端服务并确认：
  - `http://127.0.0.1:8000/health` -> `200`
  - `http://127.0.0.1:5173` -> `200`
  - `http://127.0.0.1:5173/fixed-rules` -> `200`
- 使用运行中的固定规则服务完成真实 `SVN 更新` 联调：
  - 工作副本：`D:\projact_samo\GameDatas\datas_qa88`
  - `updated_paths = 1`
  - `used_executable = C:\Program Files\TortoiseSVN\bin\svn.exe`
  - `output = Updating '.' / At revision 449960.`
- 运行中的固定规则执行保持通过：
  - `items.xls -> items -> INT_ID > 0`
  - `Execution Completed / total_rows_scanned = 3917 / failed_sources = [] / abnormal_results = 0`
- 回归主工作台最小链路：
  - `POST /api/v1/engine/execute`
  - `Execution Completed / total_rows_scanned = 8 / failed_sources = [] / abnormal_results = 5`

### 当前项目进度

#### 已完成功能
- 四步工作台本地 Excel 校验主流程可用。
- 固定规则模块 `/fixed-rules` 已支持规则组、规则 CRUD、规则级文件绑定、配置持久化和一键执行全部规则。
- 固定规则模块的 `SVN 更新` 现在已能在当前 Windows 环境下真实执行工作副本更新。
- 后端继续保持统一执行入口、统一任务结构与统一结果结构稳定。

#### 已实现但未打通 / 占位功能
- `svn` 作为主工作台独立 `source` 类型的完整闭环仍未开放；当前已打通的是固定规则模块的工作副本更新能力。
- 飞书数据源仍为占位实现。
- 动态规则平台能力仍未重新开放；步骤 3 继续是纯静态规则工作区。

#### 未开始功能
- 固定规则结果导出
- 固定规则多配置集切换
- `regex` 规则闭环
- 结果筛选、高级搜索与报告导出

### 规范化调整
- 保持 `POST /api/v1/engine/execute` 不变。
- 保持 `TaskTree -> sources / variables / rules` 不变。
- 保持统一结果结构 `code / msg / meta / data.abnormal_results` 不变。
- 固定规则模块继续通过 `/api/v1/fixed-rules/*` 接口和后端内部临时 `TaskTree` 复用已有执行引擎。

### 文档同步
- 更新 `README.md`
- 更新 `PROJECT_RECORD.md`
- 更新 `CHANGELOG.md`
- 更新 `frontend/README.md`
- 更新 `需求文档.md`

### 未完成项与风险
- 当前终端环境没有浏览器自动化回放能力，本轮以运行中接口、路由可访问性和真实更新结果作为固定规则联调依据。
- 当前自动探测优先围绕 Windows + TortoiseSVN 场景实现；若后续环境更换为其他 SVN CLI 发行版，建议通过 `SVN_EXECUTABLE` 显式覆盖。
- 固定规则模块仍只支持本地 Excel 文件，不扩展到 CSV、飞书或多配置集。

### 下一步建议
1. 如果后续要推进 SVN 主流程，建议单独补“`svn` 作为 source 类型”这一切片，不与固定规则继续混做。
2. 如果继续增强固定规则模块，优先考虑“结果导出”或“多配置集切换”其中一个切片。

## 进度记录 2026-04-08 18:52

### 本次目标
- 把固定规则模块从“全局单文件配置”升级为“每条规则独立绑定文件路径”的模型。
- 将固定规则页面改为上方规则组导航、下方规则配置与结果区的纵向布局。
- 完成 qa88 真样例联调、本地服务重启验证，并同步更新中文文档。

### 本次完成
- 后端固定规则配置结构升级为 `version = 2`，每条规则新增 `binding.file_path / binding.sheet / binding.column`。
- 固定规则读取时支持旧版单文件配置自动迁移；执行时会按规则聚合数据源、按 `(file_path, sheet)` 去重数据源、按 `(source, column)` 去重变量。
- `POST /api/v1/fixed-rules/svn-update` 改为聚合当前所有已配置规则路径，并按父目录去重后统一更新。
- `/fixed-rules` 页面已调整为：
  - 顶部固定操作条：`保存配置` / `SVN 更新` / `执行全部规则`
  - 上方规则组搜索与横向导航
  - 下方规则列表、规则弹窗与结果看板
- 新增/编辑规则时必须逐条配置文件路径、Sheet、目标列和比较值；不再保留全局固定文件配置卡。
- 完成回归验证：
  - `python -m pytest backend/tests -q` -> `21 passed`
  - `cd frontend && npm run build` -> 通过
- 重启本地前后端服务并验证：
  - `http://127.0.0.1:8000/health` -> `200`
  - `http://127.0.0.1:5173` -> `200`
  - `http://127.0.0.1:5173/fixed-rules` -> `200`
- 使用 qa88 真样例完成固定规则验收：
  - `D:\projact_samo\GameDatas\datas_qa88\items.xls -> items -> INT_ID > 0`
  - `Execution Completed / total_rows_scanned = 3917 / failed_sources = [] / abnormal_results = 0`
- 完成反向压测：
  - `INT_ID > 10000`
  - `Execution Completed / total_rows_scanned = 3917 / failed_sources = [] / abnormal_results = 770`
- 回归旧工作台最小执行链路：
  - `POST /api/v1/engine/execute`
  - `Execution Completed / total_rows_scanned = 8 / failed_sources = [] / abnormal_results = 5`

### 当前项目进度

#### 已完成功能
- 四步工作台仍可完成本地 Excel 校验主流程。
- 固定规则模块已独立落地为 `/fixed-rules` 页面。
- 固定规则支持规则组、规则 CRUD、规则级文件绑定、配置持久化和一键执行全部规则。
- 固定规则支持固定显示的 `SVN 更新` 按钮，并按所有已配置路径聚合更新。
- 后端继续保持统一执行入口、统一任务结构与统一结果结构稳定。

#### 已实现但未打通 / 占位功能
- `svn` CLI 仍未安装到当前环境，真实工作副本更新只完成接口级降级提示和聚合逻辑，尚未在本机形成完整同步闭环。
- 飞书数据源与真实 SVN 数据源主流程仍为占位实现。
- 动态规则平台能力仍未重新开放；步骤 3 继续是纯静态规则工作区。

#### 未开始功能
- 固定规则结果导出
- 固定规则多配置集切换
- `regex` 规则闭环
- 结果筛选、高级搜索与报告导出

### 规范化调整
- 保持 `POST /api/v1/engine/execute` 不变。
- 保持 `TaskTree -> sources / variables / rules` 不变。
- 保持统一结果结构 `code / msg / meta / data.abnormal_results` 不变。
- 固定规则模块继续通过 `/api/v1/fixed-rules/*` 接口和后端内部临时 `TaskTree` 复用已有执行引擎。

### 文档同步
- 更新 `README.md`
- 更新 `PROJECT_RECORD.md`
- 更新 `CHANGELOG.md`
- 更新 `frontend/README.md`

### 未完成项与风险
- 当前没有浏览器自动化回放能力，固定规则页面的可见性交互仍以构建、接口回归和运行态访问为主。
- 当前固定规则模块只支持本地 Excel 文件，不扩展到 CSV、飞书或多配置集。
- 当前环境缺少 `svn` CLI，因此 `SVN 更新` 仍以明确降级提示为主。

### 下一步建议
1. 如果继续增强固定规则模块，建议单独规划“结果导出”或“多配置集切换”其中一个切片，不要与其他模块混做。
2. 如果要推进真实 SVN 联动，建议先补环境检测、可执行文件配置和多工作副本冲突提示，再补页面操作流。

## 进度记录 2026-04-08 18:02

### 本次目标
- 继续在 Codex worktree `C:\Users\chenzhen\.codex\worktrees\9ac8\excel-check` 收口固定规则模块，避免已有实现停留在 `detached HEAD`。
- 完成固定规则模块的文档同步、qa88 实测验收、本地服务启动与联调说明补齐。
- 保持四步工作台主流程、统一执行入口和统一结果结构稳定。

### 本次完成
- 在当前 worktree 创建本地分支 `feature/fixed-rules-module`，后续固定规则模块收尾都落在该分支。
- 固定规则模块当前已在 worktree 中落地：
  - 新增 `/fixed-rules` 前端页面
  - 新增固定规则配置读写、执行和 SVN 更新接口
  - 新增 `fixed_value_compare` 规则类型
  - 支持规则组导航、规则 CRUD、规则分页与固定配置持久化
- 重新执行固定规则模块回归验证：
  - `python -m pytest backend/tests -q` -> `18 passed`
  - `cd frontend && npm run build` -> 通过
- 使用 qa88 真样例完成固定规则验收：
  - 文件：`D:\projact_samo\GameDatas\datas_qa88\items.xls`
  - Sheet：`items`
  - 固定列：`INT_ID`
  - 规则：`INT_ID > 0`
  - 结果：`Execution Completed / total_rows_scanned = 3917 / failed_sources = [] / abnormal_results = 0`
- 追加完成反向压测：
  - `INT_ID > 10000`
  - 结果：`Execution Completed / total_rows_scanned = 3917 / failed_sources = [] / abnormal_results = 770`
- 确认当前环境在 `svn_enabled = true` 时会返回明确降级提示：
  - `当前环境未检测到 svn 命令，请先安装 SVN CLI，或在后端配置中指定 svn 可执行文件路径。`
- 同步更新 `README.md`、`frontend/README.md`、`CHANGELOG.md`、`CODEX_DEVELOPMENT_WORKFLOW.md`。

### 当前项目进度
- 原四步工作台继续保持可用：
  - 模块 1：本地数据源、单变量、组合变量、元数据读取与详情预览可用
  - 模块 4：`not_null`、`unique`、`cross_table_mapping` 三类静态规则可用
- 固定规则模块已新增为独立工作页：
  - 支持单个本地 Excel 文件、单个 Sheet、单份持久化配置
  - 支持规则组和规则的长期维护
  - 支持页面自动回填已保存配置
  - 支持默认执行全部规则组
- 动态规则主能力仍未重新开放；步骤 3 继续是纯静态规则工作区。

### 规范化调整
- 保持 `POST /api/v1/engine/execute` 不变。
- 保持 `TaskTree -> sources / variables / rules` 不变。
- 保持统一结果结构 `code / msg / meta / data.abnormal_results` 不变。
- 固定规则模块通过新增 `/api/v1/fixed-rules/*` 接口和后端内部临时 `TaskTree` 复用已有执行引擎，不复制第二套结果协议。

### 文档同步
- 更新 `README.md`
- 更新 `PROJECT_RECORD.md`
- 更新 `CHANGELOG.md`
- 更新 `frontend/README.md`
- 更新 `CODEX_DEVELOPMENT_WORKFLOW.md`

### 未完成项与风险
- 当前环境仍没有浏览器自动化能力，`/fixed-rules` 的页面可见性与交互验证仍以构建、接口回归和运行态服务检查为主。
- 固定规则模块第一版仍只支持单配置、单 Excel、单 Sheet，不支持多配置集、CSV、飞书或多文件固定规则。
- 当前环境缺少 `svn` CLI，因此 `SVN 更新` 只有降级提示，尚未形成真实可用的工作副本同步闭环。

### 下一步建议
1. 如果要继续增强固定规则模块，可单独规划“结果导出”或“多配置集切换”其中一个切片，不要和其他模块混做。
2. 如果要推进真实 SVN 联动，建议下一轮先补环境检测、可执行文件配置和工作副本冲突提示，再补页面操作流。

## 进度记录 2026-04-07 20:43

### 本次目标
- 收口步骤 3“规则编排”页面，只保留静态规则模板和静态规则配置区。
- 隐藏动态规则配置入口，并避免隐藏的动态规则继续进入执行请求。
- 完成前后端回归验证、启动项目并同步更新说明文档。

### 本次完成
- 收口 `frontend/src/components/workbench/RuleComposerPanel.vue`，删除动态规则可见区、`新增动态规则` 按钮和 JSON 编辑器。
- 步骤 3 页面文案统一改为“当前仅开放静态规则模板配置”，不再向界面用户暴露动态规则入口。
- 调整前端执行组包逻辑，执行时只提交静态规则；当前内存中的动态规则不会进入最终 `TaskTree.rules`。
- 完成回归验证：
  - `python -m pytest backend/tests -q` -> `12 passed`
  - `cd frontend && npm run build` -> 通过
- 重新启动本地前后端服务并确认：
  - `http://127.0.0.1:8000/health` 返回 `200`
  - `http://127.0.0.1:5173` 返回 `200`
- 使用最小样例再次完成执行链路回归，结果保持：
  - `msg = "Execution Completed"`
  - `total_rows_scanned = 8`
  - `failed_sources = []`
  - `abnormal_results = 5`
- 同步更新 `README.md`、`frontend/README.md`、`CHANGELOG.md`。

### 当前项目进度
- 模块 1 的本地数据源接入、单个变量、组合变量、详情预览和变量池仍保持可用。
- 模块 4 当前继续只开放三类静态规则：`not_null`、`unique`、`cross_table_mapping`。
- 动态规则底层类型兼容仍保留在前端状态和后端主契约中，但本轮已从步骤 3 页面隐藏，不再作为当前界面能力开放。

### 规范化调整
- 保持 `POST /api/v1/engine/execute` 不变。
- 保持 `TaskTree -> sources / variables / rules` 不变。
- 保持统一结果结构 `code / msg / meta / data.abnormal_results` 不变。
- 本次仅处理步骤 3 前端切片，不顺手扩展新的规则类型或第二个模块。

### 文档同步
- 更新 `README.md`
- 更新 `PROJECT_RECORD.md`
- 更新 `CHANGELOG.md`
- 更新 `frontend/README.md`

### 未完成项与风险
- 当前环境仍未提供浏览器自动化回放能力，步骤 3 页面可见性验证以代码变更、前端构建和运行态服务检查为主。
- 动态规则底层兼容仍保留在代码中，后续如要彻底移除，需要单独开切片处理状态模型与协议清理。

### 下一步建议
1. 如果后续要继续收口规则能力，可以单独规划 `regex` 规则闭环，而不是重新开放动态规则编辑器。
2. 若要进一步提升步骤 3 可用性，建议下一轮只做静态规则的筛选、排序或模板说明增强。

## 进度记录 2026-04-07 10:11

### 本次目标
- 在不改变步骤 2 总体结构、不增加新路由和新后端接口的前提下，收口“添加单个变量 / 添加组合变量”两个子页签的行为。
- 让两个按钮继续打开各自独立子页签，并在保存后关闭当前页签、回到 `变量列表`。
- 完成前后端回归验证、重启项目，并同步更新说明文档。

### 本次完成
- 恢复并重构 `frontend/src/components/workbench/VariablePoolPanel.vue`。
- 单个变量与组合变量现在分别拥有独立的编辑状态、元数据加载状态和错误提示，不再共用一套编辑器状态。
- 点击 `添加单个变量` 会打开单个变量子页签；点击 `添加组合变量` 会打开组合变量子页签。
- 点击“保存变量”后，会关闭当前对应子页签，并自动回到 `变量列表`。
- 点击“取消”时，也会关闭当前子页签，并回到 `变量列表`。
- 编辑已有变量时，会复用对应类型的子页签，不新开浏览器级页面。
- 回归验证通过：
  - `python -m pytest backend/tests -q` -> `12 passed`
  - `cd frontend && npm run build` -> 通过

### 当前项目进度
- 模块 1 的本地数据源接入、单个变量、组合变量、三类静态规则和结果看板仍保持可用。
- 本轮只是收口步骤 2 的子页签行为，没有扩展新的后端协议，也没有改变现有三类规则的兼容边界。
- 当前组合变量仍已进入 `TaskTree.variables`，但 `not_null`、`unique`、`cross_table_mapping` 继续只消费单个变量。

### 风险与说明
- 当前环境没有浏览器自动化回放能力，本轮对子页签行为的验证以组件重构、前端构建、后端测试和最小执行链路回归为主。
- 如果本地页面仍显示旧行为，通常是前端 dev server 还没重启或浏览器缓存了旧模块。

### 下一步建议
1. 如果后续继续完善步骤 2，可以补一条浏览器自动化用例，覆盖“打开子页签 -> 保存 -> 自动回到变量列表”的点击路径。
2. 如果要让组合变量真正参与校验，建议下一轮单独设计 JSON / 映射类规则，不与当前三类静态规则混做。

## 进度记录 2026-04-03

### 本次目标
- 把本地文件选择从“上传复制到 `.runtime_uploads`”改成“记录真实本地路径”。
- 收口前后端联调链路，确保本地仍能完成一次完整校验流程。
- 同步更新项目说明和变更记录。

### 本次完成
- 删除旧的 `POST /api/v1/sources/local-upload` 上传复制方案。
- 新增 `POST /api/v1/sources/local-pick`，由后端弹出 Windows 系统文件选择框，返回真实本地绝对路径。
- 前端数据源弹窗改为调用 `local-pick`，不再上传文件。
- 本地 `Excel / CSV` 的路径输入框现在保存的是真实本地文件路径。
- 保留 `数据源标识` 必填校验和扩展名校验。
- 更新后端测试，新增：
  - 成功返回真实路径
  - 用户取消选择
- 更新 `README.md`、`CHANGELOG.md`。

### 当前状态
- 后端仍保持：
  - `GET /health`
  - `GET /api/v1/sources/capabilities`
  - `POST /api/v1/engine/execute`
- 本地文件选择已切换为真实路径模式。
- 当前不再依赖 `backend/.runtime_uploads`。
- 本地最小联调样例仍使用：
  - `D:\project\excel-check\backend\tests\data\minimal_rules.xlsx`

### 联调说明
完整链路如下：
1. 新增数据源。
2. 点击“选择文件”。
3. 由后端弹出系统文件框并选择本地 Excel/CSV。
4. 保存数据源。
5. 添加变量。
6. 添加规则。
7. 执行校验并查看结果。

### 风险与说明
- 真实本地路径模式依赖 Windows 桌面环境；如果后端运行在无桌面的远程环境，系统文件框将无法使用。
- 浏览器本身不能直接拿到真实绝对路径，因此该能力必须通过本机后端桥接。
- 如果前端仍请求旧接口，通常是本地后端没有重启到新版本。

### 下一步建议
1. 给结果看板增加筛选和导出能力。
2. 补 `regex` 规则的真实实现。
3. 增加 `pytest.ini`、前端 lint/format 和 CI 配置。

## 进度记录 2026-04-03 16:45

### 本次目标
- 修复前端点击“选择文件”无反应的问题。
- 重新确认本地路径模式下的完整联调链路。
- 同步更新说明文档。

### 本次完成
- 将 `POST /api/v1/sources/local-pick` 的本机文件选择实现从 PowerShell 改为 `tkinter` 文件对话框。
- 保持前端“选择文件”按钮和真实本地路径写回逻辑不变，只替换后端弹窗实现。
- 更新本地文件选择相关测试，当前后端测试已通过。
- 更新 `README.md`、`CHANGELOG.md`。

### 当前状态
- 本机 `tkinter` 可用。
- `python -m pytest backend/tests -q` 当前结果为 `6 passed`。
- `cd frontend && npm run build` 通过。
- 前后端仍维持“真实本地路径”模式，不再复制文件到 `.runtime_uploads`。

### 联调说明
- 若前端点击“选择文件”仍无响应，优先检查后端是否已重启到最新版本。
- 当前默认链路依然是：
  1. 选择本地文件
  2. 保存数据源
  3. 添加变量
  4. 添加规则
  5. 执行校验

### 下一步建议
1. 补一条浏览器自动化用例，覆盖“点击选择文件 -> 返回路径 -> 保存数据源”。
2. 继续扩展结果看板筛选和导出能力。

## 进度记录 2026-04-03 12:52

### 本次目标
- 只处理模块 1“数据源读取和变量池”的一个切片，把步骤 2 从手工输入 `sheet` / `column` 升级为元数据驱动构建流程。
- 在不改 `POST /api/v1/engine/execute` 主结构的前提下，为变量池补充 Excel Sheet / 列名下拉提取和变量详情页签。
- 同步更新项目说明、前端说明、变更日志和分钟级项目记录。

### 本次完成
- 新增 `POST /api/v1/sources/metadata`，用于读取 Excel 数据源的 Sheet 与列结构。
- 新增 `POST /api/v1/sources/column-preview`，用于读取变量详情页签的列预览数据。
- 后端本地读取器新增 Excel 元数据读取与列预览能力，并统一对非 Excel 来源返回“变量池下拉提取第一版仅支持 Excel 数据源”提示。
- 步骤 2 变量池改为工作台内页签式交互，点击“添加首个变量”会打开“新增变量”页签。
- “来源数据”只展示已保存的数据源；选择 Excel 数据源后，可按“来源数据 -> Sheet -> 列名”逐级下拉选择。
- 变量标签默认按 `[sourceId-sheet-column]` 自动生成；若用户手工修改，后续不再自动覆盖。
- “期望类型”入口收敛为 `字符串(str)` 与 `JSON(json)`。
- 保存变量后，数据会进入右侧变量池；点击变量池按钮会在当前工作台内打开只读变量详情页签，展示来源数据、Sheet、列名、期望类型和前 20 条预览值。
- 更新前端状态管理，新增数据源元数据缓存和变量预览缓存。
- 后端测试与前端构建已通过：
  - `python -m pytest backend/tests -q`：`9 passed`
  - `cd frontend && npm run build`：通过

### 当前项目进度

#### 已完成功能
- 本地 Excel / CSV 数据源接入。
- 本机文件选择框桥接真实本地路径。
- 基于 Excel 元数据的变量池构建首版闭环。
- 工作台内变量详情页签与列预览。
- `not_null`、`unique`、`cross_table_mapping` 三类规则执行。
- 统一结果看板与最小联调闭环。

#### 已实现但未打通 / 占位功能
- `feishu` 数据源入口仍为占位实现。
- `svn` 数据源同步流程仍为占位实现。
- 动态规则入口已保留，但未形成企业级可用的动态规则平台能力。

#### 未开始功能
- CSV 数据源的变量池下拉提取。
- `regex` 规则端到端闭环。
- 导出报告。
- 结果筛选与高级搜索。
- 工程化规范配置、CI、权限与审计。

### 规范化调整
- 保持 `TaskTree -> sources / variables / rules` 不变。
- 保持 `code / msg / meta / data.abnormal_results` 统一结果结构不变。
- 保持 `POST /api/v1/engine/execute` 主执行入口不变，仅补充变量池所需的只读辅助接口。
- 将模块 1 的前端交互改为页签式流转，但不拆新路由、不复制第二套结果系统。

### 文档同步
- 更新 `README.md`，补充变量池元数据驱动流程、辅助接口和联调步骤。
- 更新 `frontend/README.md`，补充模块 1 当前落地状态与变量详情页签说明。
- 更新 `CHANGELOG.md`，记录变量池构建切片的接口、测试和限制。

### 未完成项与风险
- 当前变量池下拉提取只支持 Excel，CSV 来源仍会被明确拦截。
- 变量详情页签当前只读，不包含编辑、删除、批量导入等扩展操作。
- 本次只处理了模块 1 的一个切片，没有触碰模块 2 正则校验、模块 3 动态规则平台和模块 4 静态规则看板扩展。
- 项目仍缺少 `pyproject.toml`、`pytest.ini`、lint / format 等统一工程化配置。

### 下一步建议
1. 在模块 1 内继续补 CSV 数据源的变量池提取体验。
2. 按既定顺序推进模块 4，先稳定静态规则编排与看板体验。
3. 后续再单独开切片处理 `regex` 规则、导出报告和工程基线配置。

## 进度记录 2026-04-03 13:17

### 本次目标
- 使用 `D:\projact_samo\GameDatas\datas_qa88\IAPConfig.xls` 和 `D:\projact_samo\GameDatas\datas_qa88\items.xls` 检查一次真实的前后端联调流程。
- 找出影响 `.xls` 文件联调稳定性的项目级问题，并修复到仓库层面。
- 同步更新启动命令、默认访问地址和基于真实文件的联调说明。

### 本次完成
- 读取并检查了 qa88 目录下的两份 `.xls` 文件，确认文件存在且可被当前环境解析。
- 用真实文件跑通了 `POST /api/v1/sources/metadata` 与 `POST /api/v1/engine/execute` 链路。
- 确认了一条可复现的真实校验方案：
  - 字典列：`items.xls -> items -> INT_ID`
  - 目标列：`IAPConfig.xls -> Template -> INT_ItemId`
  - 规则：`not_null`、`unique`、`cross_table_mapping`
- 修复项目级 `.xls` 联调隐患：在 `backend/requirements.txt` 中显式加入 `xlrd`。
- 后端 Excel 读取改为按扩展名显式选择引擎：
  - `.xlsx` -> `openpyxl`
  - `.xls` -> `xlrd`
- 对 `.xls` / `.xlsx` 依赖缺失场景补充了明确中文错误提示，避免出现模糊读取失败。
- 重新执行仓库回归验证：
  - `python -m pytest backend/tests -q`：`9 passed`
  - `cd frontend && npm run build`：通过
- 用真实文件完成执行验证，当前结果为：
  - `Execution Completed`
  - `failed_sources = []`
  - `total_rows_scanned = 5410`
  - `abnormal_results = 11`

### 当前项目进度

#### 已完成功能
- 本地 Excel / CSV 数据源接入与真实路径桥接。
- 基于 Excel 元数据的变量池构建与变量详情页签。
- `.xls` 与 `.xlsx` 的项目级读取依赖与显式引擎选择。
- `not_null`、`unique`、`cross_table_mapping` 三类规则执行。
- 统一结果看板与本地完整联调闭环。

#### 已实现但未打通 / 占位功能
- `feishu` 数据源入口仍为占位实现。
- `svn` 数据源同步流程仍为占位实现。
- 动态规则入口已保留，但未形成企业级动态规则平台。

#### 未开始功能
- CSV 数据源的变量池下拉提取。
- `regex` 规则端到端闭环。
- 导出报告。
- 结果筛选、高级搜索、权限、审计与 CI。

### 规范化调整
- 保持 `POST /api/v1/engine/execute` 主结构不变。
- 保持 `TaskTree -> sources / variables / rules` 不变。
- 保持统一结果结构 `code / msg / meta / data.abnormal_results` 不变。
- 只补充了 `.xls` 联调所需的依赖和错误提示，没有扩展到第二个模块。

### 文档同步
- 更新 `README.md`，补充 qa88 真实文件联调步骤、启动命令、默认访问地址和结果说明。
- 更新 `CHANGELOG.md`，记录 `.xls` 项目级依赖、显式引擎选择和真实联调回归。
- 更新本文件，追加本次分钟级联调记录。

### 未完成项与风险
- 本次通过的是 API 真实执行链路和前端构建验证，未做浏览器端自动化点击回放。
- qa88 样例中的 `cross_table_mapping` 当前会返回 11 条异常，这属于真实业务数据结果，不是程序错误。
- 当前仓库仍缺少 `pytest.ini`、`pyproject.toml`、lint / format 等工程化配置。

### 下一步建议
1. 如果你要继续用 qa88 数据集演示，可以把 `src_items -> items / INT_ID` 和 `src_iap -> Template / INT_ItemId` 固化成一份联调模板。
2. 后续可单独补一条浏览器自动化用例，把“新增数据源 -> 添加变量 -> 添加规则 -> 执行校验”完整回放起来。
3. 下一轮建议按既定顺序推进模块 4 或工程基线，而不是混入第二个功能模块。

## 进度记录 2026-04-03 13:23

### 本次目标
- 在 qa88 真实 `.xls` 联调链路已跑通的基础上，实际启动本地前后端服务。
- 核对默认访问地址是否可访问，并把最终可复用的启动与联调说明写入项目文档。

### 本次完成
- 实际启动后端开发服务：`python backend/run.py`
- 实际启动前端开发服务：`cd frontend && npm run dev -- --host 127.0.0.1 --port 5173`
- 确认本机端口监听正常：
  - `127.0.0.1:8000`
  - `127.0.0.1:5173`
- 验证默认访问地址可用：
  - `http://127.0.0.1:8000/health` 返回健康状态
  - `http://127.0.0.1:5173` 前端首页可访问
- 更新 `README.md` 与 `CHANGELOG.md`，补充“已实际启动并验证默认地址”的说明。

### 当前项目进度

#### 已完成功能
- 本地 Excel / CSV 数据源接入与真实路径桥接。
- 基于 Excel 元数据的变量池构建与变量详情页签。
- `.xls` 与 `.xlsx` 的项目级读取依赖和显式引擎选择。
- qa88 两份 `.xls` 文件的真实执行链路验证。
- 本地前后端服务启动与默认地址可访问验证。

#### 已实现但未打通 / 占位功能
- `feishu` 数据源入口仍为占位实现。
- `svn` 数据源同步流程仍为占位实现。
- 动态规则入口已保留，但未形成企业级动态规则平台。

#### 未开始功能
- CSV 数据源的变量池下拉提取。
- `regex` 规则端到端闭环。
- 导出报告。
- 结果筛选、高级搜索、权限、审计与 CI。

### 规范化调整
- 保持 `POST /api/v1/engine/execute`、`TaskTree` 和统一结果看板不变。
- 本次仅补“启动验证 + 文档收尾”，没有扩展到第二个模块。

### 文档同步
- 更新 `README.md`，写明服务已实际启动并验证默认地址。
- 更新 `CHANGELOG.md`，记录本地前后端启动与默认地址访问验证。

### 未完成项与风险
- 当前虽然已验证前端首页可访问，但没有做浏览器自动化脚本回放。
- 当前前端服务以开发模式运行，适合联调，不代表生产部署形态。

### 下一步建议
1. 若你后续频繁演示 qa88 样例，可把这组 source、variable、rule 固化成联调预设。
2. 如需进一步降低人工操作成本，可补浏览器自动化用例覆盖完整点击路径。

## 进度记录 2026-04-03 13:42

### 本次目标
- 修复“新增数据源”弹窗中先点`选择文件`、后填`数据源标识`时容易误判为卡住的问题。
- 修复后重启前后端服务，并重新完成一次本地完整联调。

### 本次完成
- 在`frontend/src/components/workbench/DataSourcePanel.vue`中为`选择文件`按钮增加前置条件：
  - `数据源标识`为空时按钮禁用
  - 运行中文件选择时按钮禁用并显示进行中状态
- 在`chooseLocalFile()`入口增加同步校验：
  - 未填写`数据源标识`时直接拦截
  - 不发起`POST /api/v1/sources/local-pick`
  - 直接提示“请先填写数据源标识，再选择本地文件”
- 补充弹窗内的顺序式辅助文案，明确“先标识、后选文件、再保存”
- 重启本地后端与前端服务，并重新执行回归验证

### 当前项目进度

#### 已完成功能
- 本地 Excel / CSV 数据源接入与真实本地路径桥接
- Excel 元数据驱动的变量池构建
- `not_null`、`unique`、`cross_table_mapping` 三类规则执行
- 统一结果看板与最小本地联调闭环

#### 已实现但未打通 / 占位功能
- `feishu` 数据源入口仍为占位
- `svn` 数据源同步流程仍为占位
- 动态规则入口已保留，但尚未形成企业级规则平台能力

#### 未开始功能
- CSV 数据源的变量池下拉提取
- `regex` 规则闭环
- 结果导出、筛选与高级检索
- 统一工程化配置与 CI

### 规范化调整
- 保持`TaskTree -> sources / variables / rules`不变
- 保持`POST /api/v1/engine/execute`不变
- 保持统一结果结构`code / msg / meta / data.abnormal_results`不变
- 本次只修数据源弹窗的错误交互顺序，不扩展到第二个模块

### 文档同步
- 更新`README.md`
- 更新`CHANGELOG.md`
- 追加本次分钟级进度记录到`PROJECT_RECORD.md`
- 同步补充`frontend/README.md`中的交互顺序说明

### 未完成项与风险
- 本机文件选择仍依赖 Windows 桌面环境与`tkinter`对话框
- 当前没有浏览器自动化用例，交互回归仍以人工流程验证为主

### 下一步建议
1. 给“新增数据源 -> 选择文件 -> 保存”补一条浏览器自动化回归用例。
2. 继续推进结果看板筛选与导出能力。

## 进度记录 2026-04-03 14:03

### 本次目标
- 继续只处理模块 1“数据源读取和变量池”的单个交互切片。
- 把变量池详情从工作台内页签调整为子页面式弹窗，并同步优化新增变量的默认值与保存收口行为。

### 本次完成
- 将新增变量表单中的 `期望类型` 默认值改为 `字符串(str)`。
- 调整变量保存行为：保存成功后仅回写右侧变量池，不再自动打开变量详情。
- 将变量详情从工作台内页签改为大尺寸只读弹窗，列表中的“查看详情”和右侧变量池标签都会打开同一套详情窗口。
- 详情弹窗保留现有变量预览接口与缓存逻辑，预览表格支持滚动查看当前已加载的全部预览数据。
- 更新 `README.md`、`frontend/README.md`、`CHANGELOG.md`，同步本次交互口径。
- 完成回归验证：
  - `python -m pytest backend/tests -q`：`9 passed`
  - `cd frontend && npm run build`：通过

### 当前项目进度

#### 已完成功能
- 本地 Excel / CSV 数据源接入与真实本地路径桥接。
- Excel 元数据驱动的变量池构建。
- 模块 1 的新增变量页签、默认字符串类型、变量池列表与只读详情弹窗。
- `not_null`、`unique`、`cross_table_mapping` 三类规则执行。
- 统一结果看板与本地完整联调闭环。

#### 已实现但未打通 / 占位功能
- `feishu` 数据源入口仍为占位实现。
- `svn` 数据源同步流程仍为占位实现。
- 动态规则入口已保留，但尚未形成企业级规则平台能力。

#### 未开始功能
- CSV 数据源的变量池下拉提取。
- `regex` 规则闭环。
- 结果导出、筛选与高级检索。
- 统一工程化配置与 CI。

### 规范化调整
- 保持 `POST /api/v1/engine/execute` 不变。
- 保持 `TaskTree -> sources / variables / rules` 不变。
- 保持统一结果结构 `code / msg / meta / data.abnormal_results` 不变。
- 本次只调整模块 1 的前端交互，不扩展到规则模块或后端主执行链路。

### 文档同步
- 更新 `README.md`，把变量池详情交互口径统一为“详情弹窗”。
- 更新 `frontend/README.md`，补充默认字符串类型、保存收口行为和弹窗说明。
- 更新 `CHANGELOG.md`，记录本次变量池交互细化。
- 追加本次分钟级进度记录到 `PROJECT_RECORD.md`。

### 未完成项与风险
- 当前详情弹窗仍为只读，不包含编辑、删除、批量导入等扩展动作。
- 当前列预览继续复用现有预览接口，展示的是当前已加载的预览数据，不是单独新增的全量导出能力。
- 当前没有浏览器自动化用例，交互回归仍以人工流程验证为主。

### 下一步建议
1. 如需进一步降低交互回归成本，可补一条覆盖“新增变量 -> 保存 -> 查看详情弹窗”的浏览器自动化用例。
2. 后续若继续处理模块 1，可单独开一个切片评估 CSV 数据源的变量池下拉提取体验。
3. 再下一轮建议回到既定顺序，推进模块 4 的静态规则编排与看板完善。

## 进度记录 2026-04-03 14:51

### 本次目标
- 修复变量详情弹窗点击后看不到对应数据的问题。
- 在不改 `POST /api/v1/engine/execute` 主结构的前提下，完成一次真实 qa88 文件的预览回归和执行回归。
- 同步更新启动说明、联调说明与项目变更记录。

### 本次完成
- 将变量详情弹窗的列预览请求改为默认读取当前列的完整预览数据，不再只取少量行。
- 后端 `POST /api/v1/sources/column-preview` 支持在不传 `limit` 时返回完整列预览，并补充：
  - `source_path`
  - `loaded_rows`
  - `loaded_all_rows`
- 前端变量详情弹窗新增“当前来源文件”展示，能够直接看到当前预览对应的真实本地路径。
- 前端空状态提示改为明确提示用户检查来源文件、Sheet 和列名，避免把真实空数据误判为弹窗故障。
- 新增后端测试，覆盖“列预览不传 `limit` 时返回完整列数据”。
- 完成回归验证：
  - `python -m pytest backend/tests -q`：`10 passed`
  - `cd frontend && npm run build`：通过
- 用 qa88 真实文件完成两类运行中接口验证：
  - `items.xls -> items -> DESC`：`3849 / 3849`
  - `items_ext.xls -> items -> DESC`：`0 / 0`
- 重新启动本地前后端服务并验证默认地址：
  - `http://127.0.0.1:8000/health`
  - `http://127.0.0.1:5173`
- 使用运行中的本地服务再次完成 qa88 执行回归：
  - `msg = "Execution Completed"`
  - `failed_sources = []`
  - `total_rows_scanned = 5410`
  - `abnormal_results = 11`

### 当前项目进度

#### 已完成功能
- 本地 Excel / CSV 数据源接入与真实本地路径桥接。
- Excel 元数据驱动的变量池构建与变量详情弹窗。
- 变量详情弹窗的完整列预览、真实来源路径展示与滚动查看。
- `not_null`、`unique`、`cross_table_mapping` 三类规则执行。
- qa88 真实 `.xls` 文件的本地联调闭环。

#### 已实现但未打通 / 占位功能
- `feishu` 数据源入口仍为占位实现。
- `svn` 数据源同步流程仍为占位实现。
- 动态规则入口已保留，但尚未形成企业级规则平台能力。

#### 未开始功能
- CSV 数据源的变量池下拉提取。
- `regex` 规则闭环。
- 结果导出、筛选与高级检索。
- 统一工程化配置与 CI。

### 规范化调整
- 保持 `POST /api/v1/engine/execute` 不变。
- 保持 `TaskTree -> sources / variables / rules` 不变。
- 保持统一结果结构 `code / msg / meta / data.abnormal_results` 不变。
- 本次仅收口模块 1 的变量详情预览链路和联调说明，没有扩展到第二个模块。

### 文档同步
- 更新 `README.md`，补充变量详情预览修复说明与 qa88 真实回归结果。
- 更新 `frontend/README.md`，补充详情弹窗完整预览与空状态诊断说明。
- 更新 `CHANGELOG.md`，记录本次变量详情预览修复与接口字段补充。
- 追加本次分钟级进度记录到 `PROJECT_RECORD.md`。

### 未完成项与风险
- 当前仍未补浏览器自动化点击回归，用例验证以接口级和本地服务级回归为主。
- 当用户实际选择的数据文件本身没有数据时，详情弹窗会明确显示 `0 / 0`；这属于数据现状，不是程序错误。
- 变量详情弹窗仍为只读，不包含编辑、删除、批量操作等扩展能力。

### 下一步建议
1. 给“查看详情弹窗”补一条浏览器自动化回归，覆盖真实点击路径。
2. 如果下一轮继续处理模块 1，优先补 CSV 数据源的变量池提取体验。
3. 再下一轮按既定顺序推进模块 4 的静态规则编排与结果看板完善。

## 进度记录 2026-04-03 15:12

### 本次目标
- 基于当前工作区继续收口本地联调链路，不回退已有未提交改动。
- 实际启动前后端服务，确认默认访问地址可用，并再次用 qa88 两份 `.xls` 文件验证运行中链路。
- 同步更新启动命令、访问地址和联调说明，保证文档只描述本轮真实执行过的内容。

### 本次完成
- 重新确认当前工作区内的后端测试、前端构建和 qa88 API 级验证均已通过，没有发现新的代码级阻塞问题。
- 实际启动后端开发服务：`python backend/run.py`。
- 实际启动前端开发服务：`cd frontend && npm run dev -- --host 127.0.0.1 --port 5173`。
- 运行态验证通过：
  - `GET http://127.0.0.1:8000/health` 返回 `200`
  - `GET http://127.0.0.1:5173` 返回 `200`
- 使用运行中的本地服务再次验证 qa88 链路：
  - `POST /api/v1/sources/metadata` 可读出 `items` 等 Sheet
  - `POST /api/v1/sources/column-preview` 返回 `3849 / 3849`
  - `POST /api/v1/engine/execute` 返回：
    - `msg = "Execution Completed"`
    - `failed_sources = []`
    - `total_rows_scanned = 5410`
    - `abnormal_results = 11`
- 更新 `README.md`、`CHANGELOG.md` 和本文件，统一本轮启动验证与联调说明口径。

### 当前项目进度

#### 已完成功能
- 本地 Excel / CSV 数据源接入与真实本地路径桥接。
- Excel 元数据驱动的变量池构建与变量详情弹窗。
- `not_null`、`unique`、`cross_table_mapping` 三类规则执行。
- qa88 真实 `.xls` 文件的运行态执行链路验证。
- 本地前后端服务的默认启动命令、默认访问地址与文档口径收口完成。

#### 已实现但未打通 / 占位功能
- `feishu` 数据源入口仍为占位实现。
- `svn` 数据源同步流程仍为占位实现。
- 动态规则入口已保留，但尚未形成企业级规则平台能力。

#### 未开始功能
- CSV 数据源的变量池下拉提取。
- `regex` 规则闭环。
- 结果导出、筛选与高级检索。
- 统一工程化配置与 CI。

### 规范化调整
- 保持 `POST /api/v1/engine/execute` 不变。
- 保持 `TaskTree -> sources / variables / rules` 不变。
- 保持统一结果结构 `code / msg / meta / data.abnormal_results` 不变。
- 本次没有扩展到第二个模块，只收口本地联调、服务启动与文档口径。

### 文档同步
- 更新 `README.md`，补充本轮实际启动与运行态验证结果。
- 更新 `CHANGELOG.md`，记录本轮服务启动、qa88 运行态回归和文档统一。
- 追加本次分钟级进度记录到 `PROJECT_RECORD.md`。

### 未完成项与风险
- 当前终端环境没有浏览器自动化能力，本轮未记录完整浏览器点击回放；浏览器手工步骤已整理为可复现说明。
- 本机文件选择仍依赖 Windows 桌面环境与 `tkinter` 对话框。
- `abnormal_results = 11` 来自 qa88 真实业务数据，不代表程序失败。

### 下一步建议
1. 补一条浏览器自动化用例，覆盖“新增数据源 -> 添加变量 -> 添加规则 -> 执行校验”的完整点击路径。
2. 如果继续完善模块 1，优先补 CSV 数据源的变量池下拉提取体验。
3. 再下一轮按既定顺序推进模块 4 的静态规则编排与结果看板完善。

## 进度记录 2026-04-03 16:03

### 本次目标
- 只处理模块 1“数据源读取和变量池”的一个前端布局切片。
- 将步骤 2 的变量池从桌面端右侧移动到“配置变量与后端字段映射”区域下方，并完成一次本地联调回归。

### 本次完成
- 保持 `VariablePoolPanel` 现有 DOM 顺序不变，仅通过样式调整把步骤 2 从桌面端双栏改为单栏纵向堆叠。
- “当前变量池”现在固定显示在“配置变量与后端字段映射”区域下方。
- 同步微调变量池说明文案，强调“保存变量后，下方可直接用于规则编排”。
- 更新 `README.md`、`frontend/README.md`、`CHANGELOG.md` 与本文件，统一“配置区下方变量池”的表述。
- 完成回归验证并准备重启本地前后端服务。

### 当前项目进度

#### 已完成功能
- 本地 Excel / CSV 数据源接入与真实本地路径桥接。
- Excel 元数据驱动的变量池构建与变量详情弹窗。
- 步骤 2 变量池已调整为“上配置区、下变量池”的单列布局。
- `not_null`、`unique`、`cross_table_mapping` 三类规则执行。
- qa88 真实 `.xls` 文件与最小样例的本地联调闭环。

#### 已实现但未打通 / 占位功能
- `feishu` 数据源入口仍为占位实现。
- `svn` 数据源同步流程仍为占位实现。
- 动态规则入口已保留，但尚未形成企业级动态规则平台能力。

#### 未开始功能
- CSV 数据源的变量池下拉提取。
- `regex` 规则闭环。
- 结果导出、筛选与高级检索。
- 统一工程化配置与 CI。

### 规范化调整
- 保持 `TaskTree -> sources / variables / rules` 不变。
- 保持 `POST /api/v1/engine/execute` 不变。
- 保持统一结果结构 `code / msg / meta / data.abnormal_results` 不变。
- 本次仅调整步骤 2 的展示层布局，不扩展到步骤 1、3、4 和任何后端接口。

### 文档同步
- 更新 `README.md`
- 更新 `frontend/README.md`
- 更新 `CHANGELOG.md`
- 追加本次分钟级进度记录到 `PROJECT_RECORD.md`

### 未完成项与风险
- 当前步骤 2 的布局已收口，但没有新增浏览器自动化回归用例。
- 变量池仍然只服务于当前 Excel 元数据驱动流程，CSV 下拉提取体验尚未补齐。

### 下一步建议
1. 给步骤 2 补一条浏览器自动化用例，覆盖“新增变量 -> 保存 -> 在下方变量池点击查看详情”的路径。
2. 后续若继续处理模块 1，优先补 CSV 数据源的变量池提取体验。

## 进度记录 2026-04-03 17:02

### 本次目标
- 在不改 `POST /api/v1/engine/execute` 外壳和现有三类规则行为的前提下，为步骤 2 增加“组合变量”入口和全链路变量协议扩展。
- 保持当前本地完整联调路径继续可用，并同步更新项目说明与变更记录。

### 本次完成
- 将步骤 2 顶部入口调整为：`变量列表`、`添加单个变量`、`添加组合变量`。
- 单个变量页签保留原有来源数据、Sheet、列名、标签、期望类型流程，仅统一命名为“添加单个变量”。
- 新增“添加组合变量”页签，支持：
  - 同一个数据源、同一个 Sheet
  - 至少 2 列关联
  - 从已选列中选择 `key 列`
  - 固定 `json` 期望类型
  - 页签内实时 JSON 预览
- 扩展 `TaskTree.variables` 的 `VariableTag` 协议，支持：
  - `variable_kind = 'single'`
  - `variable_kind = 'composite'`
  - `columns`
  - `key_column`
- 新增后端接口 `POST /api/v1/sources/composite-preview`，返回组合变量 JSON 映射与元信息。
- 扩展本地 Excel loader，使其支持组合变量预览与执行期装载。
- 保持现有三类静态规则只面向单个变量；前端规则选择器已自动过滤组合变量，后端规则层也增加了防御性校验。
- 完成回归验证：
  - `python -m pytest backend/tests -q`：`12 passed`
  - `cd frontend && npm run build`：通过

### 当前项目进度

#### 已完成功能
- 本地 Excel / CSV 数据源接入与真实本地路径选择。
- Excel 元数据驱动的单个变量构建、变量详情弹窗和变量池管理。
- 步骤 2 变量池下移后的单列布局。
- 组合变量全链路协议扩展、JSON 预览和详情查看。
- `not_null`、`unique`、`cross_table_mapping` 三类静态规则执行。
- 最小样例与 qa88 真实文件的本地联调闭环。

#### 已实现但未打通 / 占位功能
- `feishu` 数据源入口仍为占位实现。
- `svn` 数据源同步流程仍为占位实现。
- 动态规则入口已保留，但尚未形成企业级动态规则平台能力。
- 组合变量已进入 `TaskTree.variables`，但暂未接入 JSON 专用规则类型。

#### 未开始功能
- CSV 数据源的变量池下拉提取。
- `regex` 规则闭环。
- 结果导出、筛选与高级搜索。
- 统一工程化配置与 CI。

### 规范化调整
- 保持 `TaskTree -> sources / variables / rules` 不变。
- 保持 `POST /api/v1/engine/execute` 不变。
- 保持统一结果结构 `code / msg / meta / data.abnormal_results` 不变。
- 本次只扩展步骤 2 的变量形态与预览链路，不改步骤 1、3、4 的总体布局和接口边界。

### 文档同步
- 更新 `README.md`
- 更新 `frontend/README.md`
- 更新 `CHANGELOG.md`
- 追加本次分钟级进度记录到 `PROJECT_RECORD.md`

### 未完成项与风险
- 组合变量当前只支持本地 Excel，且限制为同一数据源、同一 Sheet。
- 当前三类静态规则不会消费组合变量；如后续需要 JSON 规则，还需单独开切片扩展。
- 目前没有浏览器自动化用例覆盖“添加组合变量 -> 预览 JSON -> 保存 -> 打开详情”的完整点击路径。

### 下一步建议
1. 如果继续处理模块 1，可优先补“组合变量详情查看”和“组合变量保存”的浏览器自动化回归。
2. 如需让组合变量参与规则执行，建议单开一个切片设计 JSON/映射类规则，不与现有三类静态规则混做。

## 进度记录 2026-04-07 11:22

### 本次目标
- 只处理步骤 2 的变量编辑交互切片，把“添加单个变量 / 添加组合变量”从工作台内页签改为独立对话框。
- 保持当前 `TaskTree`、组合变量协议、后端接口和三类静态规则兼容边界不变。
- 完成一次新的前后端联调回归，并同步更新项目说明与变更记录。

### 本次完成
- 将步骤 2 主区域收口为“变量列表 + 当前变量池”，不再在主区域内展示变量编辑页签。
- `添加单个变量` 与 `添加组合变量` 已改为独立对话框，风格与“新增数据源”保持一致。
- 编辑已有变量时，会按变量类型复用对应对话框。
- 点击 `保存变量` 或 `取消` 后，会关闭当前对话框并回到变量列表。
- 完成回归验证：
  - `python -m pytest backend/tests -q` => `12 passed`
  - `cd frontend && npm run build` => 通过

### 当前项目进度

#### 已完成功能
- 本地 Excel / CSV 数据源接入与真实本地路径选择。
- Excel 元数据驱动的单个变量构建、组合变量构建、变量详情弹窗和变量池管理。
- 步骤 2 变量池位于配置区下方，变量新增与编辑统一改为独立对话框。
- `not_null`、`unique`、`cross_table_mapping` 三类静态规则执行。
- 最小样例和 qa88 真实文件的本地联调闭环。

#### 已实现但未打通 / 占位功能
- `feishu` 数据源入口仍为占位实现。
- `svn` 数据源同步流程仍为占位实现。
- 组合变量已经进入 `TaskTree.variables`，但当前三类静态规则仍不会消费组合变量。

#### 未开始功能
- CSV 数据源的变量池下拉提取。
- `regex` 规则闭环。
- 结果导出、筛选与高级搜索。
- 统一工程化配置与 CI。

### 规范化调整
- 保持 `TaskTree -> sources / variables / rules` 不变。
- 保持 `POST /api/v1/engine/execute` 不变。
- 保持统一结果结构 `code / msg / meta / data.abnormal_results` 不变。
- 本次只调整步骤 2 的变量编辑交互，不扩展步骤 1、3、4 的布局和后端协议。

### 文档同步
- 更新 `README.md`
- 更新 `frontend/README.md`
- 更新 `CHANGELOG.md`
- 追加本次分钟级记录到 `PROJECT_RECORD.md`

### 未完成项与风险
- 旧的步骤 2 页签编辑结构仍作为隐藏兼容块保留在组件内，当前不会影响运行，但后续可以再做一次彻底清理。
- 当前终端环境没有浏览器自动化能力，本轮仍以构建、测试和接口级联调回归为主。
- 组合变量仍只服务于变量池与预览链路，未接入 JSON 类规则。

### 下一步建议
1. 继续处理模块 1 时，可把步骤 2 中隐藏的旧页签结构彻底删除，进一步收敛组件复杂度。
2. 如需让组合变量真正参与校验，建议单开一个切片设计 JSON / 映射类规则。
3. 后续继续按既定顺序推进模块 4 的规则编排和结果看板增强。
## 进度记录 2026-04-07 14:36

### 本次目标
- 只处理步骤 2 中“添加组合变量”对话框的一个排版切片。
- 将 `取消 / 保存变量` 按钮从 JSON 预览区下方移动到预览区之前。

### 本次完成
- 已将组合变量对话框调整为“表单区 -> 操作区 -> JSON 预览区”的顺序。
- 单个变量对话框保持不变，没有扩大影响范围。
- 组合变量保存、取消、预览和关闭逻辑均保持原样。

### 当前状态
- 步骤 2 的组合变量对话框主操作更靠近表单区，录入后可直接保存。
- 当前联调主链路目标保持不变：`Execution Completed / total_rows_scanned = 8 / failed_sources = [] / abnormal_results = 5`。

### 下一步建议
- 如果还要继续收口步骤 2，可再单独清理组件中隐藏的旧页签兼容结构。
## 进度记录 2026-04-13 17:10

### 本次目标
- 收口主工作台首页 `/` 的视觉层级、图标语义与首页可见文案。
- 严格保持现有 DOM 层级、Grid / Flex 布局逻辑、类名、ID 与 JS 逻辑不变，只做 CSS 和文本优化。

### 本次完成
- 重写首页可见文案，清理共享头部、首页品牌区、概览指标区、流程引导条与步骤卡中的遗留乱码和冗长提示。
- 统一首页图标语义与图标容器视觉：
  - 数据源：`FolderOpened`
  - 变量：`CollectionTag`
  - 规则：`SetUp`
  - 异常结果：`TrendCharts`
  - 首页品牌：`DataBoard`
- 首页整体视觉改为更鲜明但克制的高级亮色风格，统一了：
  - 圆角
  - 边框
  - 阴影
  - 按钮质感
  - hover / pressed 反馈
- 保持 `/fixed-rules` 独立业务界面不重绘，只同步共享头部与通用状态视觉。

### 本轮回归
- `python -m pytest backend/tests -q` => `40 passed`
- `cd frontend && npm run build` => 通过
- `GET http://127.0.0.1:8000/health` => `200`
- `GET http://127.0.0.1:5173` => `200`
- `GET http://127.0.0.1:5173/fixed-rules` => `200`
- `POST /api/v1/engine/execute` => `Execution Completed / total_rows_scanned = 8 / failed_sources = [] / abnormal_results = 5`

### 当前结论
- 首页已经从“功能可用”提升到“信息层级更清晰、图标更统一、视觉更完整”的状态。
- 本轮没有触碰任何对外接口、`TaskTree` 结构、Pinia 状态模型和事件绑定，属于纯前端表现层收口。
## 进度记录 2026-04-13 18:05

### 本次目标
- 继续压缩 `/fixed-rules` 页面的文字密度，只保留标题、状态、操作入口和必要提示。

### 本次完成
- 收短固定规则页 Hero 标题与副文案。
- 压缩步骤 1、步骤 2 的说明和 hint。
- 精简变量池对话框、JSON 预览、变量详情和结果区空状态文案。
- 保持 DOM、布局骨架、类名、ID、事件绑定和业务逻辑不变。

### 当前状态
- 固定规则页页面说明明显减少，信息更聚焦在“当前状态 / 下一步 / 操作入口”。

### 下一步建议
- 如果还要继续减字，下一轮优先处理表格内的长标签摘要和规则摘要。

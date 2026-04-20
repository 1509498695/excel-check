# 更新日志

文档更新时间：2026-04-20 12:22

## [Unreleased]

- **前端全站 Apple Design 视觉重构**：
  - 共享壳层、主工作台、固定规则页、登录、注册、管理后台、个人设置统一切换为 Apple HIG 风格的玻璃材质、细描边、多层阴影、大圆角与平滑动效。
  - `frontend/src/style.css` 重建全局视觉 token，并统一覆盖 Element Plus 的按钮、输入框、下拉、表格、弹窗、Tag、Alert、Progress 与下拉菜单。
  - `frontend/src/fixed-rules.css` 单独补充固定规则页的 Header、规则组 pill、规则工作区、组合规则编辑器、SVN 结果区与弹窗层次。
  - `frontend/src/App.vue`、`MainBoard.vue`、`FixedRulesBoard.vue`、`LoginView.vue`、`RegisterView.vue`、`AdminView.vue`、`ProfileView.vue` 的脚本顶部显式补充 `// 保持原有逻辑不变` 注释，确认本轮不改状态、接口和业务逻辑。
  - 回归：
    - `cd frontend && npm run build` => 通过
    - `python -m pytest backend/tests -q` => `66 passed`
    - `GET http://127.0.0.1:8000/health` => `200`
    - `GET http://127.0.0.1:5173/login` / `register` / `/` => `200`
    - 新起 Vite 实例自动切到 `http://127.0.0.1:5174/`，`/login` / `register` / `/` => `200`

- **规则引擎物理分层完成，行为零变更（PR-3 Phase 2）**：
  - `backend/app/rules/` 完成三层化：[backend/app/rules/domain/](backend/app/rules/domain/)（`value.py / result.py / operators.py`）、[backend/app/rules/infrastructure/](backend/app/rules/infrastructure/)（`tag_extractor.py`）、[backend/app/rules/handlers/](backend/app/rules/handlers/)（`basics.py / cross.py / fixed.py`）。
  - `handlers/__init__.py` 副作用 import `basics / cross / fixed` 触发 `@register_rule` 完成 5 个 `rule_type` 注册。
  - [backend/app/rules/engine_core.py](backend/app/rules/engine_core.py) 仅 2 处 import 调整：`TagExtractor` 改从 `infrastructure.tag_extractor` 导入；底部副作用 import 改走 `handlers` 包；其余函数体、`RuleSpec / RuleExecutionContext / register_rule / execute_rules` 全部不动。
  - 7 个旧路径文件（`_value.py / _result.py / _operators.py / _tag_extractor.py / rule_basics.py / rule_cross.py / rule_fixed.py`）全部改写为薄壳 shim，仅 `from <new path> import *`，向后兼容一个发布周期。
  - **行为零变更**：任何函数体、字段名、Pydantic 模型、ValueError 文案、`level` 取值、对外 HTTP 接口、`abnormal_results` 6 字段集、4 份基线快照（S1/S2/S3/S4）、所有现有测试均 0 diff；schemas / formatter / `fixed_rules/` / loaders / 前端业务代码 / 现有测试一律未触碰。
  - 回归：
    - `python -m pytest backend/tests -q` => `66 passed`（含 4 份快照 0 diff）
    - `cd frontend && npm run build` => 通过（产物名称与字节体积与 PR-2 完成态一致）
    - `GET http://127.0.0.1:8000/health` => `200`
    - `POST /api/v1/engine/execute` 主工作台最小样例 => `Execution Completed / total_rows_scanned = 8 / failed_sources = [] / abnormal_results = 5`（与 PR-2 完成态字节级一致）
    - `POST /api/v1/fixed-rules/execute` qa88 真样例 => `Execution Completed / total_rows_scanned = 3987 / failed_sources = [] / abnormal_results = 0`（与 PR-2 完成态字节级一致）

- **执行引擎 Phase 1 重构（PR-2，黑盒不变）**：
  - 新增 4 个私有 helper 模块统一规则层共性：[backend/app/rules/_value.py](backend/app/rules/_value.py)、[backend/app/rules/_result.py](backend/app/rules/_result.py)、[backend/app/rules/_operators.py](backend/app/rules/_operators.py)、[backend/app/rules/_tag_extractor.py](backend/app/rules/_tag_extractor.py)。
  - [backend/app/rules/engine_core.py](backend/app/rules/engine_core.py) 升级 `RULE_REGISTRY` 为 `dict[str, RuleSpec]`，`RuleSpec` 同时持有 `handler` 与 `dependent_tags`；`register_rule(rule_type, *, dependent_tags=...)` 唯一签名（一次性切换，无兼容层）。
  - [backend/app/rules/rule_basics.py](backend/app/rules/rule_basics.py) / [rule_cross.py](backend/app/rules/rule_cross.py) / [rule_fixed.py](backend/app/rules/rule_fixed.py) 改用新 helper；`composite_condition_check` 注册 `dependent_tags=by_target_tag`，与其它 `rule_type` 行为对齐。
  - [backend/app/api/execute_api.py](backend/app/api/execute_api.py) `_extract_rule_tags` 改为直接复用注册表，删除 30 行 if/elif 长链；`_ensure_rule_supported` 文案逐字保留。
  - **黑盒契约 0 变化**：HTTP 入参出参、`TaskTree / ValidationRule.params` 字段语义、`abnormal_results` 6 字段集合、所有 ValueError detail 文案逐字保留；`regex / feishu / svn` 占位能力不动；schemas / formatter / `fixed_rules/` / loaders / 前端业务代码 / 现有测试均未触碰。
  - **唯一行为正向修正（已显式披露）**：`composite_condition_check` 之前未被 `_extract_rule_tags` 覆盖，依赖失败 source 时会被错误地交给 handler 并退化成 400 `references unknown tag`；本轮纳入 `dependent_tags` 后会被 `_filter_executable_rules` 一致跳过，整次请求继续 200。当前 4 份基线快照均不含「composite + 失败 source」组合，因此 S1/S2/S3/S4 全部保持 0 diff，无需 `UPDATE_ENGINE_SNAPSHOT=1` 刷新。
  - 回归：
    - `python -m pytest backend/tests -q` => `66 passed`（含 4 份快照 0 diff）
    - `cd frontend && npm run build` => 通过
    - `GET http://127.0.0.1:8000/health` => `200`
    - `POST /api/v1/engine/execute` 主工作台最小样例 => `Execution Completed / total_rows_scanned = 8 / failed_sources = [] / abnormal_results = 5`
    - `POST /api/v1/fixed-rules/execute` qa88 真样例 => `Execution Completed / total_rows_scanned = 3987 / failed_sources = [] / abnormal_results = 0`

- **新增引擎执行黑盒快照测试 baseline（PR-1）**：
  - 新增 [backend/tests/test_engine_snapshot.py](backend/tests/test_engine_snapshot.py) 与 4 份基线快照 [backend/tests/snapshots/engine/S1.json](backend/tests/snapshots/engine/S1.json) / [S2.json](backend/tests/snapshots/engine/S2.json) / [S3.json](backend/tests/snapshots/engine/S3.json) / [S4.json](backend/tests/snapshots/engine/S4.json)。
  - 通过 `POST /api/v1/engine/execute` 直接构造 payload，覆盖：S1 主工作台 `not_null + unique + cross_table_mapping`、S2 `fixed_value_compare` 的 `eq/ne/gt/lt` 各 1 条、S3 `composite_condition_check` 同时覆盖 `global_filters + branch.filters + eq/not_null/unique/duplicate_required` 4 类 assertion、S4 失败 source 降级。
  - 写 / 读快照前统一把 `meta.execution_time_ms` 归零；序列化口径 `json.dumps(..., sort_keys=True, ensure_ascii=False, indent=2)` + LF。
  - 通过环境变量 `UPDATE_ENGINE_SNAPSHOT=1` 切换写入模式；默认运行走断言模式。
  - 新增干净测试数据集 [backend/tests/data/snapshot_engine.xlsx](backend/tests/data/snapshot_engine.xlsx)（双 sheet：`values` 供 S2、`items` 供 S3）。
  - 本轮**严格未改动 `backend/app/` 下任何 .py、未改动现有测试与 conftest、未改动前端**。
  - 回归：
    - `python -m pytest backend/tests/test_engine_snapshot.py -q -s` => `4 passed`
    - `python -m pytest backend/tests -q` => `66 passed`

- **管理后台归属项目与项目管理员开放**：
  - 用户模型新增 `primary_project_id`，登录与 `/api/v1/auth/me` 的默认项目选择改为优先使用主归属项目，不再依赖 `roles[0]` 顺序。
  - 管理后台 `/admin` 现已对项目管理员开放受限版能力：可查看自己可管理项目、编辑项目名称/描述、管理普通用户成员，但不能创建或删除项目。
  - 管理后台成员区新增 `归属项目` 展示与普通用户“调整归属项目”能力；超级管理员和项目管理员的归属项目不可调整。
  - 项目列表首屏会自动选中第一个可管理项目，避免后台成员区右侧空白。
  - 后端新增 `PUT /api/v1/admin/projects/{project_id}/members/{user_id}/project`，用于调整普通用户归属项目并收口为单项目归属。
  - 补充后端回归测试，覆盖：主归属项目登录选择、项目管理员受限 `/admin`、普通用户归属项目调整、成员列表归属项目返回。
  - 回归：
    - `python -m pytest backend/tests -q` => `62 passed`
    - `cd frontend && npm run build` => 通过
    - 运行态补充验证：`http://127.0.0.1:8001/health`、`POST /api/v1/auth/login`、`GET /api/v1/auth/me`、`GET /api/v1/admin/projects` => 通过

- **[重大] 多用户认证与项目隔离体系**：
  - 新增 JWT 认证（注册 / 登录 / 令牌管理），系统启动时固定播种默认超级管理员 `admin / 123456`，注册用户默认不再自动成为超级管理员。
  - 新增三级角色权限：超级管理员、项目管理员、普通用户。
  - 新增数据持久化层：SQLAlchemy 异步引擎 + SQLite，包含 `Project`、`User`、`UserProjectRole`、`FixedRulesConfigRecord`、`WorkbenchConfigRecord` 五张 ORM 模型。
  - 固定规则配置从文件存储迁移到数据库，按 `project_id` 隔离。
  - 工作台配置新增数据库持久化，按 `project_id + user_id` 隔离，支持 2 秒防抖自动保存。
  - 新增管理后台 `/admin`：项目增删改查与成员管理。
  - 新增个人中心 `/profile`：修改密码与切换项目。
  - 前端新增 `apiFetch` 统一 JWT 注入与 401 跳转，路由新增全局认证守卫。
  - 密码哈希从 `passlib[bcrypt]` 切换为直接使用 `bcrypt`，兼容 `bcrypt 5.x`。
  - 回归：`40 passed` / `npm run build` 通过。

- **超级管理员收口**：
  - 删除“首个成功注册用户自动升为超级管理员”的后端逻辑。
  - 应用启动时会自动修复默认管理员：若不存在则创建 `admin / 123456`，若存在则统一修复为唯一超级管理员并重置为默认密码。
  - 现有其他超级管理员账号会在启动时降级为普通用户，项目级角色保持不删除。
  - 默认管理员会自动加入默认项目并具备项目管理员角色，保证登录后可直接进入工作台。

- **默认管理员登录 500 修复**：
  - 修复后端启动初始化顺序，先导入 ORM 模型，再执行 `create_all`，避免运行时 SQLite 被建成“空库无表”状态。
  - 修复默认项目播种逻辑，当前按项目名 `默认项目` 保证系统保留项目存在，不再因为库中已有任意项目而提前返回。
  - 修复后，空库或新库启动时会自动创建表结构、默认项目和默认超级管理员 `admin / 123456`。
  - 当前实测：`POST /api/v1/auth/login` 使用 `admin / 123456` 返回 `200`。

- **管理后台项目编辑与删除**：
  - 超级管理员后台补齐项目编辑入口，支持修改项目名称和描述。
  - 新增 `DELETE /api/v1/admin/projects/{project_id}`，支持删除普通项目。
  - 默认项目 `默认项目` 现在明确禁止删除，接口返回 `400`。
  - 删除普通项目时会先把项目成员迁移到默认项目，并统一降为普通用户；若成员已在默认项目存在角色记录，则保留原记录。
  - 删除普通项目后会继续清理项目级固定规则配置和工作台配置。
  - 管理后台左侧项目卡新增“编辑项目 / 删除项目”入口，删除成功后管理后台会整页刷新，确保项目列表和上下文状态同步。
  - 成员删除规则进一步收口：默认项目中删除成员会直接删除用户账号；其他项目中删除成员会自动迁移到默认项目。
  - 默认项目中的超级管理员与当前登录管理员本人不可删除；成员删除入口统一显示为“删除”并附带二次确认。
  - 修复管理后台删除项目后的前端报错：`apiFetch.ts` 现在兼容 `204 No Content` 空响应体，不再触发 `Unexpected end of JSON input`。
  - 回归：`python -m pytest backend/tests -q` => `49 passed`；`cd frontend && npm run build` => 通过。

- **切换项目数据同步**：
  - `workbench.loadFromServer` 改为先重置状态再合并服务端数据，空项目不再残留上一项目配置。
  - `fixedRules` store 新增 `resetState` action，切换项目时清空配置、执行结果和 UI 缓存。
  - `App.vue` 和 `ProfileView.vue` 的项目切换去掉 `window.location.reload()`，改为 SPA 内 store 重载 + `router.push('/')`。
  - 回归：`40 passed` / `npm run build` 通过 / API 隔离验证通过。

- 主工作台步骤 3 改为规则组编排（`WorkbenchRuleOrchestrationPanel`），与 `/fixed-rules` 规则能力对齐且 Pinia 状态隔离；移除 `RuleComposerPanel` 与三卡片静态模板入口。
- `workbench` store 使用 `ruleGroups` + `orchestrationRules`（`FixedRuleDefinition`），执行前映射为 `ValidationRule`；`taskTree.ts` 支持 `fixed_value_compare` 与 `composite_condition_check` 归一化。
- 抽取共用规则模型工具 [`frontend/src/utils/ruleOrchestrationModel.ts`](frontend/src/utils/ruleOrchestrationModel.ts)，`fixedRules` store 改为引用以减少重复。
- 「加载样例」编排已更新，最小样例当前实测 `abnormal_results = 4`（`2 not_null + 2 unique`）。

- 新增根目录 [MODULES.md](MODULES.md)，汇总前后端目录与页面级模块职责；[README.md](README.md)「相关文档」增加入口链接。

- 精简 `/fixed-rules` 页面的标题、副文案、步骤说明、变量池提示、规则编辑辅助说明和结果区空状态，降低页面文字密度。
- 本轮仅调整固定规则页可见 copy，不改 DOM、布局骨架、类名、ID、事件绑定和业务逻辑。

### 变更
- 优化主工作台首页 `/` 与共享头部的视觉表现，在不改 DOM、布局骨架、类名和交互逻辑的前提下，统一收口背景、边框、圆角、阴影、间距与 hover 反馈。
- 精简并修复首页可见文案，覆盖品牌副标题、顶栏状态、概览指标、流程引导条、步骤卡标题/描述/提示与 CTA。
- 首页文案改为更聚焦“当前状态 / 下一步动作 / 执行结果”的操作导向表达，减少冗余说明。
- 本轮回归结果：
  - `cd frontend && npm run build` => 通过
  - `GET http://127.0.0.1:8000/health` => `200`
  - `GET http://127.0.0.1:5173` => `200`
  - `GET http://127.0.0.1:5173/fixed-rules` => `200`
  - `POST /api/v1/engine/execute` => `Execution Completed / total_rows_scanned = 8 / failed_sources = [] / abnormal_results = 5`
- 固定规则页新增组合变量规则类型 `composite_condition_check`，支持“全局筛选 + 条件分支 + 分支校验”的组合变量检查配置。
- 固定规则弹窗现在会根据目标变量类型自动切换：
  - 单变量 -> 比较 / 非空 / 唯一规则
  - 组合变量 -> 条件分支校验编辑器
- 组合变量规则支持 `Key` 作为 JSON 映射键字段参与筛选与字段对字段比较；后端执行期内部使用 `__key__`。
- 组合变量规则校验当前支持：
  - 筛选：`eq / ne / gt / lt / not_null`
  - 分支校验：`eq / ne / gt / lt / not_null / unique / duplicate_required`
- 本地 Excel 组合变量执行装载已展开为可校验行集，固定规则执行链路可直接消费组合变量。
- 新增固定规则 API 回归测试，覆盖组合变量规则保存、回填、非法配置拦截和示例场景执行。
- 本轮回归结果：
  - `python -m pytest backend/tests -q` => `40 passed`
  - `cd frontend && npm run build` => 通过
  - `GET http://127.0.0.1:8000/health` => `200`
  - `GET http://127.0.0.1:5173` => `200`
  - `GET http://127.0.0.1:5173/fixed-rules` => `200`
- 修复 `/api/v1/fixed-rules/config` 在固定规则页已保存失效本地路径时直接返回 `500 Internal Server Error` 的问题。
- 固定规则配置读取现在会把“路径失效 / Sheet 不存在 / 列不存在”作为非阻断问题返回到 `meta.config_issues`，页面可继续打开并展示中文告警。
- `PUT /api/v1/fixed-rules/config` 与 `POST /api/v1/fixed-rules/execute` 继续保持严格校验；失效路径未修复时返回明确中文 `400`。
- 固定规则页顶部新增配置问题提示，数据源接入管理中的失效来源会显示 `路径失效` 状态，执行入口在阻断问题存在时会禁用。
- 修正当前固定规则 runtime 配置里残留的历史乱码分组名称。
- 本轮回归结果：
  - `python -m pytest backend/tests -q` => `33 passed`
  - `cd frontend && npm run build` => 通过
  - `GET http://127.0.0.1:8000/health` => `200`
  - `GET http://127.0.0.1:5173/fixed-rules` => `200`
  - 失效路径专项回归：
    - `GET /api/v1/fixed-rules/config` => `200 + meta.config_issues`
    - `PUT /api/v1/fixed-rules/config` => `400`
    - `POST /api/v1/fixed-rules/execute` => `400`
- 修复复用组件 `VariablePoolPanel.vue` 中残留的 `????` 乱码文案。
- 主工作台步骤 2 与固定规则页变量池模块的按钮、表头、弹窗、空态、JSON 预览和详情弹窗文案已恢复为正常中文。
- 顺手修复一处 `Sheet` 选择占位乱码。
- 本轮回归结果：
  - `cd frontend && npm run build` => 通过
  - `GET http://127.0.0.1:8000/health` => `200`
  - `GET http://127.0.0.1:5173` => `200`
  - `GET http://127.0.0.1:5173/fixed-rules` => `200`
- 固定规则页 `/fixed-rules` 现在在规则组导航上方复用了工作台的 `数据源接入管理` 和 `变量池构建` 两个模块，但底层状态改为固定规则页自己的持久化 store，不再复用主工作台缓存。
- 固定规则配置结构已升级为 `version = 4`，统一保存 `sources / variables / groups / rules`；读取旧版 `version = 3` 的规则级绑定配置时，会自动迁移为 `target_variable_tag` 绑定模型。
- 固定规则弹窗移除了 `规则文件路径 / 读取结构 / Sheet / 目标列`，改为直接从固定规则页变量池选择 `目标变量`；当前仅允许单变量进入固定规则执行链路。
- 固定规则页删除数据源时，会级联删除其变量与依赖规则；删除变量时，也会自动清理绑定该变量的规则。
- 固定规则页与主工作台的数据源、变量池已完全隔离，刷新页面后固定规则页新增的数据源、变量和规则仍会自动回填。
- 本轮联调结果：
  - `python -m pytest backend/tests -q` => `30 passed`
  - `cd frontend && npm run build` => 通过
  - `GET http://127.0.0.1:8000/health` => `200`
  - `GET http://127.0.0.1:5173` => `200`
  - `GET http://127.0.0.1:5173/fixed-rules` => `200`
  - `/fixed-rules` 真实联调 => `Execution Completed / total_rows_scanned = 6 / failed_sources = [] / abnormal_results = 4`
  - 主工作台最小链路 => `Execution Completed / total_rows_scanned = 8 / failed_sources = [] / abnormal_results = 5`
- 固定规则弹窗新增默认规则名生成逻辑：比较类按 `sheet-目标列-规则选择名称+值` 自动生成，非比较类按 `sheet-目标列-规则选择名称` 自动生成。
- 默认规则名仅在用户未手动改名时自动同步；用户手动改名或主动清空后，后续字段变化不再自动覆盖，且空规则名无法保存。
- `unique` 的所有用户可见文案统一收口为 `唯一校验`。
- 固定规则弹窗字段 `比较符` 更名为 `规则选择`，并把下拉扩展为 6 项：`等于`、`不等于`、`大于`、`小于`、`非空校验`、`唯一校验`。
- 固定规则配置结构从 `version = 2` 升级为 `version = 3`，每条规则新增 `rule_type`；读取旧版比较型配置时会自动迁移为 `fixed_value_compare`。
- `/api/v1/fixed-rules/execute` 现在支持三类固定规则：`fixed_value_compare`、`not_null`、`unique`；其中 `not_null` 维持 `error`，`unique` 维持 `warning`。
- 固定规则结果构建补齐 `params.rule_name` 与 `params.location` 兼容，避免 `/fixed-rules` 执行结果退化成主工作台默认规则名和定位文案。
- 本轮联调结果：
  - `python -m pytest backend/tests -q` => `29 passed`
  - `cd frontend && npm run build` => 通过
  - `GET http://127.0.0.1:8000/health` => `200`
  - `GET http://127.0.0.1:5173/fixed-rules` => `200`
  - `/fixed-rules` 最小链路 => `Execution Completed / total_rows_scanned = 3 / failed_sources = [] / abnormal_results = 3`
  - 主工作台最小链路 => `Execution Completed / total_rows_scanned = 8 / failed_sources = [] / abnormal_results = 5`
- 修复固定规则模块的 `svn.exe` 发现逻辑：现在会依次尝试显式配置、`PATH`、Windows 常见 TortoiseSVN 安装路径和注册表信息。
- `backend/config.py` 现已支持通过环境变量 `SVN_EXECUTABLE` 覆盖默认的 `svn` 命令。
- 使用运行中的本地服务实际验证 `POST /api/v1/fixed-rules/svn-update`：
  - `updated_paths = 1`
  - `used_executable = C:\Program Files\TortoiseSVN\bin\svn.exe`
  - `output = Updating '.' / At revision 449960.`
- 本轮回归结果：
  - `python -m pytest backend/tests -q` => `26 passed`
  - `cd frontend && npm run build` => 通过
  - `GET http://127.0.0.1:8000/health` => `200`
  - `GET http://127.0.0.1:5173/fixed-rules` => `200`
- 固定规则模块从“全局单文件配置”升级为“规则级文件绑定”，每条规则改为独立维护 `binding.file_path / binding.sheet / binding.column`。
- 固定规则持久化结构升级为 `version = 2`，读取旧版配置时会自动迁移到新版规则级绑定结构。
- 固定规则执行改为按所有规则聚合数据源，一键执行时会按 `(file_path, sheet)` 去重数据源、按 `(source, column)` 去重变量。
- `/fixed-rules` 页面改为上下布局：上方规则组搜索与横向导航，下方规则列表、规则弹窗与结果看板。
- `SVN 更新` 改为页面固定按钮，不再依赖开关；点击后会按所有已配置规则路径的父目录去重后统一执行更新。
- 本轮回归结果：
  - `python -m pytest backend/tests -q` => `21 passed`
  - `cd frontend && npm run build` => 通过
  - `GET http://127.0.0.1:8000/health` => `200`
  - `GET http://127.0.0.1:5173/fixed-rules` => `200`
- qa88 固定规则真样例已基于新版模型通过：
  - `items.xls -> items -> INT_ID > 0` => `abnormal_results = 0`
  - `items.xls -> items -> INT_ID > 10000` => `abnormal_results = 770`
- 新增固定规则模块，提供独立页面 `/fixed-rules`，用于维护固定 Excel 文件、固定列、规则组和长期复用的固定规则。
- 新增固定规则接口：
  - `GET /api/v1/fixed-rules/config`
  - `PUT /api/v1/fixed-rules/config`
  - `POST /api/v1/fixed-rules/svn-update`
  - `POST /api/v1/fixed-rules/execute`
- 新增 `fixed_value_compare` 规则类型，支持单列常量比较 `eq / ne / gt / lt`，并继续复用统一结果结构。
- 固定规则配置持久化到 `backend/.runtime/fixed-rules/default.json`，页面重新打开后会自动回填上次已保存配置。
- 固定规则页面新增规则组搜索、规则数量徽标、规则分页与结果看板，默认执行全部规则组。
- 当 shell `PATH` 未正确包含 `svn.exe` 时，固定规则模块仍可自动探测 TortoiseSVN CLI，不阻断当前固定规则主流程。
- 基于 `D:\projact_samo\GameDatas\datas_qa88\items.xls -> items -> INT_ID > 0` 的固定规则验收样例已经验证通过：
  - `Execution Completed`
  - `total_rows_scanned = 3917`
  - `failed_sources = []`
  - `abnormal_results = 0`
- 反向压测 `INT_ID > 10000` 当前实测返回 `abnormal_results = 770`。
- 本轮回归结果：
  - `python -m pytest backend/tests -q` => `18 passed`
  - `cd frontend && npm run build` => 通过
- 步骤 3 的规则编排页面已收口为纯静态规则工作区，只保留静态规则模板和静态规则配置区。
- 页面不再展示动态规则配置侧栏、`新增动态规则` 按钮、`rule_type` 输入框和 `params(JSON)` 编辑器。
- 前端执行时现在只会提交静态规则，隐藏的动态规则不会再进入最终 `TaskTree.rules`。
- 步骤 2 的 `添加单个变量` 与 `添加组合变量` 现在继续保留按钮入口，但会打开彼此独立的子页签。
- 单个变量和组合变量编辑区不再共用一套编辑状态、元数据加载状态和错误提示，避免两个子页签互相污染。
- 点击“保存变量”或“取消”后，会关闭当前对应子页签，并自动回到 `变量列表`。
- 编辑已有变量时，会复用对应类型的子页签，而不是切回通用编辑区。
- 本轮回归保持通过：
  - `python -m pytest backend/tests -q` => `12 passed`
  - `cd frontend && npm run build` => 通过
- 步骤 2 新增“添加组合变量”入口，并将原“加载示例变量”按钮替换为组合变量构建入口。
- 步骤 2 当前工作区统一为：
  - `变量列表`
  - `添加单个变量`
  - `添加组合变量`
- 扩展 `TaskTree.variables` 的 `VariableTag` 协议，支持：
  - `variable_kind`
  - `columns`
  - `key_column`
- 新增 `POST /api/v1/sources/composite-preview`，用于生成同一数据源、同一 Sheet 下的组合变量 JSON 映射预览。
- 本地 Excel loader 现已支持组合变量预览与执行期装载。
- 组合变量保存后会进入同一个变量池，并在变量列表和详情弹窗中显示 `组合变量 / JSON` 标识。
- 当前 `not_null`、`unique`、`cross_table_mapping` 静态规则继续只消费单个变量；前端规则选择器已自动过滤组合变量，后端规则层新增防御性校验。
- 完成组合变量扩展后的回归验证：
  - `python -m pytest backend/tests -q` => `12 passed`
  - `cd frontend && npm run build` => 通过
- 步骤 2 的变量池从桌面端右侧双栏区域调整为固定显示在“配置变量与后端字段映射”区域下方。
- 变量池标签流样式同步收敛为更适合全宽下方区块的横向换行布局。
- 再次按最终启动命令实际拉起本地前后端服务，确认：
  - `python backend/run.py`
  - `cd frontend && npm run dev -- --host 127.0.0.1 --port 5173`
  - `http://127.0.0.1:8000/health`
  - `http://127.0.0.1:5173`
- 使用运行中的本地服务再次验证 qa88 两份 `.xls` 文件的 metadata、column-preview 和 execute 链路，结果保持：
  - `Execution Completed`
  - `failed_sources = []`
  - `total_rows_scanned = 5410`
  - `abnormal_results = 11`
- 统一 `README.md`、`PROJECT_RECORD.md` 和本文件的联调口径，只保留本轮实际验证过的启动命令、访问地址与 qa88 联调说明。
- 修复变量详情弹窗看不到对应数据的问题，详情请求改为优先读取当前列的完整预览数据。
- 变量详情弹窗新增真实来源文件路径显示，便于直接判断当前查看的是哪一份本地文件。
- 当列预览结果为空时，前端空状态提示改为明确提醒检查来源文件、Sheet 和列名，不再只显示空表格。
- `POST /api/v1/sources/column-preview` 现在支持详情弹窗不传 `limit` 时返回完整列预览，并补充 `source_path`、`loaded_rows`、`loaded_all_rows` 字段。
- 使用运行中的本地服务再次验证 qa88 文件：
  - `items.xls -> items -> DESC` 返回 `3849 / 3849`
  - `POST /api/v1/engine/execute` 返回 `Execution Completed / 5410 / 11`
- 取消浏览器本地文件上传复制链路，不再把文件复制到 `backend/.runtime_uploads`。
- 新增 `POST /api/v1/sources/local-pick`，由本机后端弹出 Windows 系统文件选择框并返回真实本地绝对路径。
- 前端“新增数据源”弹窗改为记录真实本地路径，`数据源标识` 继续保持必填。
- 修复“先点选择文件、后填数据源标识”时容易误判为卡住的问题，改为先填标识后才能触发本机文件选择。
- 示例联调流程继续保留，但不再依赖上传桥接。
- 修复“选择文件按钮无反应”的问题，将本地文件对话框实现从 PowerShell 方案切换为本机 `tkinter` 文件对话框。
- 新增 `POST /api/v1/sources/metadata`，用于读取 Excel 数据源的 Sheet 与列结构。
- 新增 `POST /api/v1/sources/column-preview`，用于读取变量详情页签的列预览数据。
- 步骤 2 变量池从手工输入升级为元数据驱动流程，支持按“来源数据 -> Sheet -> 列名”逐级选择。
- 保留工作台内“新增变量”页签，并将变量详情从页签切换为大尺寸只读弹窗，变量池按钮和列表里的“查看详情”都可直接打开。
- 新增变量表单中的 `期望类型` 默认选中 `字符串(str)`，保存变量后不再自动拉起详情界面。
- 变量期望类型入口收敛为 `字符串(str)` 与 `JSON(json)` 两种选择。
- 当前版本明确限制：变量池下拉提取仅支持 Excel 数据源，CSV 下拉提取后续补充。
- `backend/requirements.txt` 新增 `xlrd`，把 `.xls` 读取能力补成项目级依赖，而不是依赖本机环境碰巧已安装。
- 本地 Excel 读取按扩展名显式选择引擎：`.xlsx` 使用 `openpyxl`，`.xls` 使用 `xlrd`。
- `.xls` 依赖缺失时，现在会返回明确中文错误，提示安装 `xlrd`。
- 使用 `D:\projact_samo\GameDatas\datas_qa88\IAPConfig.xls` 与 `D:\projact_samo\GameDatas\datas_qa88\items.xls` 完成一次真实联调回归。

### 测试
- 新增“列预览不传 `limit` 时返回完整列数据”的后端接口测试。
- 新增 `local-pick` 接口测试，覆盖：
  - 成功返回真实本地路径
  - 用户取消选择返回 `cancelled`
- 新增 `metadata` 接口测试，覆盖 Excel Sheet / 列结构返回。
- 新增 `column-preview` 接口测试，覆盖变量详情预览返回。
- 新增 CSV 数据源在变量池下拉提取中被明确拦截的测试。
- 保留执行接口回归测试，继续覆盖：
  - 空值
  - 重复值
  - 跨表映射缺失
- 额外用 qa88 的两份 `.xls` 配置表完成真实执行验证，确认：
  - `failed_sources = []`
  - `Execution Completed`
  - `cross_table_mapping` 可返回真实异常
- 实际启动本地前后端开发服务，并确认：
  - `http://127.0.0.1:8000/health` 可访问
  - `http://127.0.0.1:5173` 前端首页可访问

### 文档
- 更新 `README.md`
- 更新 `PROJECT_RECORD.md`
- 更新 `frontend/README.md`
- 更新本文件，统一为“真实本地路径”口径

## 2026-04-07 变量编辑对话框更新

### 变更
- 步骤 2 的 `添加单个变量` 和 `添加组合变量` 现在统一改为独立对话框。
- 步骤 2 主区域只保留变量列表与当前变量池，不再展示变量编辑页签。
- 新增和编辑已有变量时，都会按变量类型复用对应对话框。
- 点击 `保存变量` 或 `取消` 后，会关闭当前对话框并回到变量列表。
- 本轮回归结果：
  - `python -m pytest backend/tests -q` => `12 passed`
  - `cd frontend && npm run build` => 通过

## [0.2.0] - 2026-04-02

### 新增
- 新增 `frontend` 子项目，落地 `MainBoard` 四步工作台。
- 新增前后端最小联调链路。
- 新增结果看板和规则编排界面。

## [0.1.0] - 2026-04-01

### 新增
- 新增 FastAPI 后端最小骨架。
- 新增本地 Excel / CSV 读取能力。
- 新增 `not_null`、`unique`、`cross_table_mapping` 三类规则。
- 新增最小后端测试数据与接口测试。
## 2026-04-07 组合变量对话框按钮位置调整

- 将“添加组合变量”对话框中的 `取消 / 保存变量` 按钮组移动到 JSON 预览区之前。
- 对话框现在采用“表单区 -> 操作区 -> 预览区”的顺序，便于先完成配置再查看下方 JSON 预览。
- “添加单个变量”对话框保持不变，本次仅调整组合变量对话框。
## [0.4.7] - 2026-04-13

### Changed
- 收口主工作台首页 `/` 的视觉样式，统一共享头部、首页品牌区、概览指标区、流程引导条和步骤卡的圆角、边框、阴影与交互反馈。
- 首页图标调整为更明确的业务语义，并统一图标容器的尺寸、底板和色彩映射。
- 首页可见文案改为更短、更偏操作导向的表达，清理遗留乱码与冗余说明。

### Verified
- `python -m pytest backend/tests -q` => `40 passed`
- `cd frontend && npm run build` => passed
- `POST /api/v1/engine/execute` => `Execution Completed / total_rows_scanned = 8 / failed_sources = [] / abnormal_results = 5`

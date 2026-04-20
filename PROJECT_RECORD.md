# 项目记录文档

项目目录：`D:\project\excel-check`

## 进度记录 2026-04-20 17:40

### 本次目标

- 以桌面参考稿 `htm.html` 和 `弹窗样式.html` 为唯一视觉真相，把当前项目继续收口到 **1:1 参考稿风格**。
- 重点修复当前主工作台还残留的两处偏差：
  - 仍在使用 `WorkbenchStepCard` 折叠式工作流卡，而不是参考稿的 4 个展开模块
  - 结果区仍是上一版 `alert + progress + element table` 混合结构，不是参考稿的统计块 + 异常表格

### 本次完成

#### 触达文件

- [`frontend/src/views/MainBoard.vue`](frontend/src/views/MainBoard.vue)
  - 移除 `WorkbenchStepCard` 引用与折叠壳层，把步骤 1~4 全部改回参考稿式展开模块：
    - `01 数据源`
    - `02 变量池`
    - `03 规则`
    - `04 结果`
  - 每个模块统一为：`顶部 2px 激活色带 + 左侧编号 badge + 标题 + 状态胶囊 + 副说明 + 下方正文`
  - `scrollToStep(step)`、步骤点击高亮、样例填充、执行校验、`@saved -> scrollToStep` 等行为全部沿用。
- [`frontend/src/components/workbench/ResultBoardPanel.vue`](frontend/src/components/workbench/ResultBoardPanel.vue)
  - 结果区从旧的 `el-alert + 通过率 progress + summary tiles + el-table`，重写为参考稿同构结构：
    - 上方告警 Banner（失败数据源 / 执行错误）
    - 中部 4 个统计块：扫描总行数 / 失败数据源 / 异常结果 / 执行耗时
    - 下方异常明细表：`命中规则 / 定位 / 行号 / 原始值 / 级别 / 说明`
  - `store.executionMeta`、`store.abnormalResults`、`store.pageError` 的消费口径零改动。
- [`frontend/src/style.css`](frontend/src/style.css)
  - 新增统一 `Dialog / Table / Form tokens`：
    - `el-dialog` 统一圆角、边框、阴影、header/body/footer padding
    - `workbench-table` 统一参考稿式浅表头、12px uppercase 表头、白底正文
    - `mono-chip / truncate-line / table-actions` 统一 reference 味道的辅助样式
  - 这组全局 tokens 会同步影响主工作台、固定规则页以及共享弹窗，是本轮“全站统一”的真实落点。

#### 严格未触碰

- [`frontend/src/store/`](frontend/src/store/) 全部 Pinia 状态
- [`frontend/src/api/`](frontend/src/api/) 全部请求封装
- [`frontend/src/types/`](frontend/src/types/) 全部协议定义
- [`backend/`](backend/) 任何 `.py` 与测试

### 回归结果

- `python -m pytest backend/tests -q` => `67 passed`
- `cd frontend && npm run build` => 通过（vue-tsc + Vite v8.0.3）
- 运行态探活：
  - `GET http://127.0.0.1:8000/health` => `200`
  - `GET http://127.0.0.1:5173/` => `200`
  - `GET http://127.0.0.1:5173/login` => `200`
  - `GET http://127.0.0.1:5173/fixed-rules` => `200`

### 当前项目进度

#### 已完成功能

- 主工作台骨架现已与 `htm.html` 收口到同一套展开式工作台结构，不再残留折叠工作流卡。
- 结果区现已切回参考稿式统计块 + 异常表格结构。
- 共享弹窗 / 表格 / 表单 tokens 进一步统一，工作台与弹窗风格更加一致。

#### 已知遗留

- `frontend/src/components/workbench/WorkbenchStepCard.vue` 文件仍保留在仓库中，但主工作台已不再使用；后续如无其它页面复用，可单独立项清理。
- 变量详情弹窗仍沿用上一轮详情型布局，本轮未纳入“5 个核心弹窗”范围内的再次收口。

## 进度记录 2026-04-20 16:55

### 本次目标

- 修复主工作台步骤 3「规则」展开后的排版崩坏（根因是上一轮删除 `frontend/src/fixed-rules.css` 时，`WorkbenchRuleOrchestrationPanel.vue` 仍在引用 `rule-binding-board / group-band-card / group-pill / rule-workspace-card / composite-condition-card` 等 class，layout 全失效）。
- 把工作台页签的 5 个弹窗（新增数据源 / 添加单变量 / 添加组合变量 / 新建规则组 / 新建规则）按已确认的设计稿全量重写，对齐全站 Linear 风格。

### 本次完成

#### 触达文件（按 Phase）

- **Phase A** [`frontend/src/components/workbench/WorkbenchRuleOrchestrationPanel.vue`](frontend/src/components/workbench/WorkbenchRuleOrchestrationPanel.vue)：
  - 模板全量重写为 Tailwind utility，与 [`frontend/src/views/FixedRulesBoard.vue`](frontend/src/views/FixedRulesBoard.vue) 同款规则编排区 1:1 对齐：左侧 260px 规则组垂直列表（`bg-canvas/40 + 4px 左主色色带 + bg-accent-soft 选中态`）+ 右侧极简 HTML 表格。
  - **Dialog 4** 新建 / 重命名规则组：从原 `ElMessageBox.prompt` 升级为 420px 自定义 `<el-dialog>`，新增 4 个 reactive 状态（`isGroupDialogVisible / groupDialogMode / groupForm / isSubmittingGroup`）+ `openCreateGroupDialog / openRenameGroupDialog / handleSubmitGroup` 3 个新函数，业务调用仍走原 `store.createOrchestrationGroup / store.renameOrchestrationGroup`。
  - **Dialog 5** 新增 / 编辑规则：760px、三段式 SectionHeader 风格（基本信息 / 校验配置 / 组合分支），段 2 在目标为组合变量时整段 `opacity-50 pointer-events-none` 并显示「当前不适用」胶囊；段 3 嵌套层次 `bg-subtle → bg-card → border-line`；全部 `el-form-item` 替换为 `<label>` + 控件直渲。
  - 删除 `Delete / EditPen` 图标 import；保留 `Plus / Search`。
  - 顶部待修复告警从 `el-alert` 换成 `border + 4px 左 warning 色带` 的极简 Banner。
  - **业务函数零改动**：`handleSaveRule / validateRuleForm / openCreateRuleDialog / openEditRuleDialog / handleRemoveRule / handleRemoveGroup / addBranch / removeBranch / addBranchFilter / removeBranchFilter / addBranchAssertion / removeBranchAssertion / setConditionOperator / setConditionValueSource / validateCompositeCondition / buildRuleCondition / buildRuleSelectionSummary / buildRuleVariableSummary / buildRuleSourcePathSummary / syncRuleNameWithForm` 等约 40 个全部沿用。
- **Phase B** [`frontend/src/components/workbench/DataSourcePanel.vue`](frontend/src/components/workbench/DataSourcePanel.vue)：
  - 仅重写「新增 / 编辑数据源」`<el-dialog>` 内部 body：从 `el-form / el-form-item` 改为 `flex flex-col gap-4 + label.text-[12px].text-ink-500 + el-input/el-select`；520px 宽。
  - 路径输入行改为 `flex items-center gap-2 + flex-1 input + 选择文件按钮`，`needsToken` 飞书分支保留。
  - footer 按钮换成原生 `<button>`（`border-line bg-card` 取消 + `bg-accent` 保存数据源）。
  - 外层「面板表头 + 数据源表格 + 状态 Tag」全部保留，所有 props / emit / computed / watch / 函数零改动。
- **Phase C** [`frontend/src/components/workbench/VariablePoolPanel.vue`](frontend/src/components/workbench/VariablePoolPanel.vue)：
  - 重写「添加单个变量」弹窗：520px、双列 grid 排布（来源 / Sheet / 列名 / 期望类型）+ 全宽变量标签 + 1 句副文 "默认按 [来源-Sheet-列名] 自动生成；改后不再覆盖"。
  - 重写「添加组合变量」弹窗：720px、`grid grid-cols-[1fr_280px] gap-6`；左栏完整表单；右栏 JSON 映射预览（`<pre> bg-canvas font-mono text-[11px]`，`max-h-[300px]` 内部滚动），含统计行（行数 / key 数 / Key 列名）。
  - 错误告警从 `el-alert` 换成同款 4px 左 warning 色带 Banner。
  - 「变量详情」弹窗本轮未触碰，留待后续单独清理。
  - 所有 props / emit / computed / watch、`fetchCompositePreview` 调用链路、`handleSingleSourceChange / handleCompositeSourceChange / saveSingleVariable / saveCompositeVariable` 等业务函数零改动。

#### 严格未触碰

- [`frontend/src/store/`](frontend/src/store/) 全部 Pinia 状态
- [`frontend/src/api/`](frontend/src/api/) 全部请求封装
- [`frontend/src/types/`](frontend/src/types/) 全部协议定义
- [`backend/`](backend/) 任何 `.py` 与测试

### 回归结果

- `python -m pytest backend/tests -q` => `67 passed`
- `cd frontend && npm run build` => 通过（vue-tsc + Vite v8.0.3，零 TS 错误，零 Tailwind 警告；产物：`index-D-IzhydK.css 419.68KB / gzip 60.48KB`，`index-1x24Im5o.js 189.03KB`）
- `python backend/run.py` 启动；`GET http://127.0.0.1:8000/health` => `200`
- `npm run dev -- --host 127.0.0.1 --port 5173` 启动；6 路由实测：
  - `/login` / `/register` / `/` / `/fixed-rules` / `/admin` / `/profile` => 全部 `200`
- 主工作台最小样例（`POST /api/v1/engine/execute` + `minimal_rules.xlsx` + `not_null / unique / cross_table_mapping`）：
  - `code=200 / msg=Execution Completed / total_rows_scanned=8 / failed_sources=[] / abnormal_results=5`
- 固定规则 qa88 真样例（`PUT /api/v1/fixed-rules/config` + `D:\projact_samo\GameDatas\datas_qa88\items.xls -> items -> INT_ID > 0`，再 `POST /api/v1/fixed-rules/execute`）：
  - `code=200 / msg=Execution Completed / total_rows_scanned=3987 / failed_sources=[] / abnormal_results=0`

### 当前项目进度

#### 已完成功能

- 工作台页签 4 个步骤展开后视觉 1:1 对齐 Linear 风格设计稿，步骤 3 排版崩坏完全修复。
- 5 个工作台弹窗 1:1 对齐设计稿（420 / 520 / 720 / 760 四档宽度），共享组件改动同步惠及固定规则页 `/fixed-rules`。
- 主工作台与固定规则页的端到端业务接口与 baseline 字节级一致。

#### 已实现但未打通 / 占位功能

- `regex` 规则已注册但未闭环
- `svn` 作为主工作台独立 source 类型的完整闭环未开放
- `feishu` 数据源仍为占位实现
- 「变量详情」弹窗未对齐新设计语言（本轮显式留作下一轮单独立项）

#### 未开始功能

- 固定规则结果导出 / 多配置集切换
- 多用户协同编辑冲突处理

### 文档同步

- 更新 [`README.md`](README.md) 顶部追加本轮变更条目
- 更新 [`PROJECT_RECORD.md`](PROJECT_RECORD.md)：追加本次分钟级记录（即本节）
- 更新 [`CHANGELOG.md`](CHANGELOG.md)：在 `[Unreleased]` 顶部追加阶段性变更条目
- 更新 [`frontend/README.md`](frontend/README.md)：追加本轮前端实际触达范围与运行态验证结果
- 更新 [`需求文档.md`](需求文档.md)：0 章追加本轮需求补充

### 未完成项与风险

- DataSourcePanel / VariablePoolPanel 是共享组件，新弹窗外形对 `/fixed-rules` 同步生效——这是统一设计系统的预期效果，已通过 qa88 固定规则联调兜住。
- 「变量详情」弹窗仍保留旧外形（`detail-dialog-shell / variable-detail-panel / detail-meta-grid` 等老 class），属于「已知遗留 + 等待下一轮单独立项清理」状态；功能完整可用，仅外形与新设计不一致。
- 「新建规则组 / 重命名规则组」从 ElMessageBox.prompt 升级到自定义 el-dialog，新增 4 个 reactive ref；已确认 watcher / computed 不会捕获到这些内部状态。

## 进度记录 2026-04-20 16:10

### 本次目标

- 按已确认的 6 片重构 spec，把 Excel Check 全站 6 个页面（共享壳层、主工作台、固定规则、管理后台、个人设置、登录、注册）一次性收口到同一套 Linear 冷静风 + Tailwind v3 + 单 accent 体系，弃用旧的 Apple 玻璃质感样式。
- **业务红线**：不动 Pinia store、API 模块、类型协议、路由守卫、后端字段；只动模板结构、布局容器、CSS、文案。

### 本次完成

#### 触达文件（按阶段）

- **Phase 0** 新增 6 个共享展示组件：
  - [`frontend/src/components/shell/PageHeader.vue`](frontend/src/components/shell/PageHeader.vue)
  - [`frontend/src/components/shell/SectionHeader.vue`](frontend/src/components/shell/SectionHeader.vue)
  - [`frontend/src/components/shell/StatPill.vue`](frontend/src/components/shell/StatPill.vue)
  - [`frontend/src/components/shell/StatusDot.vue`](frontend/src/components/shell/StatusDot.vue)
  - [`frontend/src/components/shell/EmptyState.vue`](frontend/src/components/shell/EmptyState.vue)
  - [`frontend/src/components/shell/DataTable.vue`](frontend/src/components/shell/DataTable.vue)
- **Phase 1** [`frontend/src/App.vue`](frontend/src/App.vue)：删除顶部 `app-shell-toolbar`（含「当前空间」label + 角色 Tag + 项目 Tag）；左边栏品牌区改为主色方块 + 24×24 表格 SVG；TopBar 改由各页面自己提供；导航激活态用 `bg-accent-soft + 主色文字`。
- **Phase 2** [`frontend/src/views/MainBoard.vue`](frontend/src/views/MainBoard.vue) + [`frontend/src/components/workbench/WorkbenchStepCard.vue`](frontend/src/components/workbench/WorkbenchStepCard.vue)：接入 `PageHeader / StatPill`；KPI 卡去 hover 浮起；当前激活步骤改为顶部 2px 主色色带（`before:bg-accent`）；折叠步骤的 chevron 加 hover 旋转 180° 200ms 缓动；KPI 与 Stepper 文案 utility 化（`数据源 / 至少接入 1 个`、`变量池 / 沉淀字段与组合变量` 等）。
- **Phase 3** [`frontend/src/views/FixedRulesBoard.vue`](frontend/src/views/FixedRulesBoard.vue) 全量重构：
  - **删除**文件 [`frontend/src/fixed-rules.css`](frontend/src/fixed-rules.css)，并从 [`frontend/src/main.ts`](frontend/src/main.ts) 移除 `import './fixed-rules.css'`。
  - 接入 `PageHeader / SectionHeader / StatPill / StatusDot`；Hero 段、`SectionBlock` 包装与玻璃质感全部删除。
  - 规则组从横向 pill 改为左侧垂直列表 + `4px 左主色色带 + bg-accent-soft + accent-ink 主色文字` 的选中态。
  - 规则列表改为极简 HTML 表格（`bg-canvas` 浅表头 + 行 hover `bg-canvas`）。
  - 「新建规则」弹窗内部用 3 个 `SectionHeader` 分隔「基本信息 / 校验配置 / 组合分支」，弃用 `el-form-item` 框；组合规则的「全局筛选 / 分支筛选 / 分支校验」用 `bg-subtle` 嵌套层次表达。
  - 失效告警从 `el-alert` 换成自定义 Banner（`border + border-l-4 border-l-warning bg-warning-soft/40`）。
- **Phase 4** [`frontend/src/views/AdminView.vue`](frontend/src/views/AdminView.vue) 标准化：接入 `PageHeader / SectionHeader`；项目列表改垂直列表 + 4px 左色带；成员表格改为极简 HTML 表格 + 行 hover；编辑/调整归属弹窗用 `label + 控件` 双行布局；主按钮只保留 `创建项目 / 保存`。
- **Phase 5** [`frontend/src/views/ProfileView.vue`](frontend/src/views/ProfileView.vue) 单列叙事：居中 720px 单列；3 段「账号信息 / 修改密码 / 我的项目」用 `SectionHeader + border-b border-line` 分隔；不再使用任何卡片底色与浮起。
- **Phase 6** [`frontend/src/views/LoginView.vue`](frontend/src/views/LoginView.vue) + [`frontend/src/views/RegisterView.vue`](frontend/src/views/RegisterView.vue) 回归克制：删除任何渐变 / 模糊 / 装饰光斑；卡片宽度 380px + 1px line 边 + `shadow-card-2`；品牌方块外置（与左边栏同款），底部 `© Excel Check · 2026`。
- **Phase 7** [`frontend/src/style.css`](frontend/src/style.css) 全局收口：
  - `:root / body` 背景从原橙蓝双 radial gradient + 渐变改为纯 `#f7f8fa`。
  - 兼容旧组件的 CSS 变量（`--accent / --brand / --success / --warning / --danger / --shadow-soft / --shadow-panel`）全部对齐 Tailwind 新 token，去掉残留的 `#ff984d` 暖橙系。
  - 新增 `prefers-reduced-motion` 兜底，统一关闭过渡 / 动画 / scroll-behavior。
  - 新增 Element Plus token 校准段：`--el-button-bg-color` 等按钮、`el-input/select` 聚焦光晕、`el-pagination`、`el-dropdown-menu__item`、`el-message` 图标颜色全部对齐 `#2563eb / #10b981 / #f59e0b / #ef4444`。

#### 严格未触碰

- [`frontend/src/store/`](frontend/src/store/) 全部 Pinia 状态
- [`frontend/src/api/`](frontend/src/api/) 全部请求封装
- [`frontend/src/types/`](frontend/src/types/) 全部协议定义
- [`frontend/src/router/`](frontend/src/router/) 与全局守卫
- [`backend/`](backend/) 任何 `.py` 与测试

### 回归结果

- `python -m pytest backend/tests -q` => `67 passed`
- `cd frontend && npm run build` => 通过（vue-tsc + Vite v8.0.3，零 TS 错误，零 Tailwind 警告；产物：`index-D1hkGF37.css 419.18KB / gzip 60.38KB`，`index-p6N8XX7f.js 178.35KB`，`auth-alxLMu_a.js 951.96KB`，`AdminView-Dd7BOH0Z.js / ProfileView-C_0snwP9.js / LoginView-BxJPImUM.js / RegisterView-DntV6b-5.js`）
- `python backend/run.py` 启动；`GET http://127.0.0.1:8000/health` => `200`
- `npm run dev -- --host 127.0.0.1 --port 5173` 启动；6 路由实测：
  - `GET http://127.0.0.1:5173/login` => `200`
  - `GET http://127.0.0.1:5173/register` => `200`
  - `GET http://127.0.0.1:5173/` => `200`
  - `GET http://127.0.0.1:5173/fixed-rules` => `200`
  - `GET http://127.0.0.1:5173/admin` => `200`
  - `GET http://127.0.0.1:5173/profile` => `200`
- 主工作台最小样例联调（`backend/tests/data/minimal_rules.xlsx` + `not_null + unique + cross_table_mapping`，使用 `admin / 123456` 登录后调用 `POST /api/v1/engine/execute`）：
  - `code=200 / msg=Execution Completed / total_rows_scanned=8 / failed_sources=[] / abnormal_results=5`
- 固定规则 qa88 真样例联调（`PUT /api/v1/fixed-rules/config` 写入 `D:\projact_samo\GameDatas\datas_qa88\items.xls -> items -> INT_ID > 0`，再 `POST /api/v1/fixed-rules/execute`）：
  - `code=200 / msg=Execution Completed / total_rows_scanned=3987 / failed_sources=[] / abnormal_results=0`

### 当前项目进度

#### 已完成功能

- 全站 6 个页面统一到同一套 design tokens（Linear 冷静风 + Tailwind v3 + 单 accent #2563eb），切换无割裂感。
- 共享展示组件库（PageHeader / SectionHeader / StatPill / StatusDot / EmptyState / DataTable）首发落地，可复用于后续新页面。
- `frontend/src/fixed-rules.css` 已彻底退役。
- 主工作台与固定规则页主链路与 PR-2 / PR-3 完成态字节级一致。

#### 已实现但未打通 / 占位功能

- `regex` 规则已注册但未闭环
- `svn` 作为主工作台独立 source 类型的完整闭环未开放
- `feishu` 数据源仍为占位实现

#### 未开始功能

- 固定规则结果导出 / 多配置集切换
- 多用户协同编辑冲突处理

### 文档同步

- 更新 [`README.md`](README.md) 顶部追加本轮全站统一重构条目
- 更新 [`PROJECT_RECORD.md`](PROJECT_RECORD.md)：追加本次分钟级记录（即本节）
- 更新 [`CHANGELOG.md`](CHANGELOG.md)：在 `[Unreleased]` 顶部追加阶段性变更条目
- 更新 [`frontend/README.md`](frontend/README.md)：追加本轮前端实际触达范围与运行态验证结果
- 更新 [`需求文档.md`](需求文档.md)：0. 文档说明追加本轮需求补充

### 未完成项与风险

- 旧的页面级 CSS（如 `.admin-* / .profile-* / .auth-*`）仍残留在 `frontend/src/style.css` 中（约 200 行死代码），属于「兼容旧组件 + 等待下一轮单独立项清理」状态。本轮不主动删除是为了避免误删 `DataSourcePanel` / `VariablePoolPanel` 内部仍依赖的 `workbench-table / .full-width / .compact-empty-state` 等共享样式。
- `auth-alxLMu_a.js` 单 chunk 仍偏大（951.96KB / gzip 307.42KB），主要来自 Element Plus + Pinia + 路由 + Vue 运行时；这与本轮重构无关，后续可单独立项做 chunk 拆分。
- 当前未补 Playwright/UI 自动化截图基线；本轮以构建、pytest、运行态接口与路由 200 为最终验收口径。

## 进度记录 2026-04-20 14:35

### 本次目标
- 按「Linear 冷静 + 图书馆目录清楚」的设计哲学，把主工作台 `/` 的视觉与结构重构落地，并引入 Tailwind v3 作为项目从此之后的标准样式方案。

### 本次完成
- `frontend/package.json`：新增 dev 依赖 `tailwindcss@^3 / postcss / autoprefixer`。
- `frontend/tailwind.config.js`：新增。把工作台 design tokens 固化（色板：`canvas / card / subtle / ink / line / accent / accent-soft / accent-ink / success / warning / danger`；字体：`Inter + Noto Sans SC + JetBrains Mono`；阴影：`card-1 / card-2`；圆角：`field=6px / card=12px`；缓动：`premium`）。`corePlugins.preflight = false` 关闭重置以避免冲掉 Element Plus 与既有 4000+ 行 CSS。
- `frontend/postcss.config.js`：新增。
- `frontend/index.html`：`lang` 改为 `zh-CN`，标题更新为「Excel Check 配置表校验工作台」，加载 Google Fonts 三族字体（`display=swap` 异步）。
- `frontend/src/style.css`：顶部插入 `@tailwind base/components/utilities`；`:root` 字体栈把 `Inter / Noto Sans SC` 提到最前；清理仅服务于 MainBoard 的废弃 class（`workbench-toolbar-tray / workbench-toolbar-meta / workbench-toolbar-actions / meta-card-compact strong / workbench-step-guide-shell / workbench-step-guide-nav / workbench-step-guide-detail / workbench-step-guide-copy / workbench-step-guide-context / workbench-step-guide-meta / workbench-step-guide-actions / step-guide-nav-item / step-guide-nav-index / step-guide-summary-card / step-guide-detail-tags / overview-item-top / overview-item-label / overview-item-value`，以及移动端响应式段里对应引用）。
- `frontend/src/components/workbench/WorkbenchStepCard.vue`：新增。Props `step / title / description / status / expanded / isCurrent`，emit `update:expanded`。折叠态单行可点击展开，展开态在 `isCurrent` 时呈现 1px 主色边 + 略深阴影；展开态 header 提供「收起」按钮。
- `frontend/src/views/MainBoard.vue`：整页结构与视觉重写：
  - 顶栏改为 `space-between`，左侧面包屑 + 标题，右侧「加载样例 + 执行校验 + 清除错误（条件出现）」；删除原日期/模式/状态三胶囊。
  - 新增 Stepper（4 步水平进度条），点击仍走 `handleStepperClick → scrollToStep` 链路；当前步骤唯一带主色高亮。
  - 删除原「先接入数据源」引导卡（信息已合并到 Stepper 的描述行）。
  - KPI 4 列纯白卡：caption + 等宽大数字 + 状态胶囊；保留 `overviewItems` 的遍历与数据来源。
  - 4 个步骤区改用 `WorkbenchStepCard` 包裹原有 panel；新增 `expandedSteps` reactive 与 `watch(activeGuideStep)` 实现「真折叠」：默认仅当前步骤展开，其他三步折叠为单行，可点击展开 / 收起。
  - `scrollToStep(step)` 会自动把目标步骤展开后再滚动，避免跳过去后看到空白。
- `SectionBlock.vue` 不动（继续为 `FixedRulesBoard.vue` 服务）。
- `FixedRulesBoard.vue` 与 `fixed-rules.css` 本轮零变更。

### 回归结果
- `cd frontend && npm run build` → 通过（vue-tsc + Vite v8.0.3，零 TS 错误，零 Tailwind 警告，CSS 体积 425.42 KB / gzip 60.59 KB）。
- 服务实测：
  - `python backend/run.py` 启动；`curl http://127.0.0.1:8000/health` → `200`
  - `npm run dev -- --host 127.0.0.1 --port 5173` 启动；`curl http://127.0.0.1:5173/` → `200`
- 业务回归（代码层面）：所有 store 调用、计算属性、子组件 props 与事件零改动，下列调用链完整保留：
  - 加载样例：`applyDemoScenario`
  - 执行校验：`runExecution → store.executeValidation → scrollToStep(4)`
  - 步骤导航点击：`handleStepperClick → scrollToStep`
  - DataSourcePanel `@saved` → `handleSourceSaved → scrollToStep(2)`（自动展开步骤 2）

### 当前项目进度

#### 已完成功能
- 主工作台视觉系统对齐 Linear 冷静风 + Tailwind v3 + 三族字体加载
- 多用户认证、项目隔离、主工作台与固定规则页主链路（含组合变量条件分支校验）
- 默认管理员、运行时数据库自动播种

#### 已实现但未打通 / 占位功能
- `regex` 规则已注册但未闭环
- `svn` 作为主工作台独立 source 类型的完整闭环未开放
- `feishu` 数据源仍为占位实现

#### 未开始功能
- 固定规则页 `/fixed-rules` 同款视觉系统对齐（本轮显式不做，留下一轮独立立项）
- 固定规则结果导出 / 多配置集切换 / 多用户协同编辑冲突处理

### 文档同步
- 更新 `README.md`
- 更新 `frontend/README.md`
- 更新 `CHANGELOG.md`
- 更新 `需求文档.md`
- 追加本次分钟级进度记录到 `PROJECT_RECORD.md`

### 未完成项与风险
- Tailwind 与既有 4000+ 行 CSS 并存：本轮通过 `corePlugins.preflight = false` 关闭浏览器重置，避免冲突；后续若大规模迁移既有页面到 Tailwind，需要分页面单独立项。
- `FixedRulesBoard.vue` 视觉与主工作台不再一致：用户在两个页面间切换会感到节奏差异。计划下一轮单独立项把固定规则页对齐同款 design tokens。

## 进度记录 2026-04-20 13:43

### 本次目标
- 把主工作台顶部步骤说明模块从“中轴窄卡”改成真正铺满整个模块框体的桌面工作区布局。
- 保持步骤切换、滚动定位和执行入口全部不变，只做视图层重排。

### 本次完成
- `frontend/src/style.css`
  - `workbench-step-guide-shell` 改为全宽纵向容器，不再为中间小卡保留收缩宽度。
  - `workbench-step-guide-nav` 改为整行四等分横排，占满模块宽度。
  - `workbench-step-guide-detail` 改为全宽 grid 布局，桌面端使用 `左主信息 + 右辅助信息` 双列结构。
  - `workbench-step-guide-meta` 改为右侧纵向堆叠，`step-guide-summary-card` 占满辅助列。
  - `workbench-step-guide-actions` 在桌面端改为右对齐，移动端回退为单列纵向堆叠。
- `frontend/src/views/MainBoard.vue`
  - 模板和业务逻辑保持不变，继续复用现有 `stepGuideItems`、`activeGuideDetail`、`handleGuideStepClick`、`scrollToStep(step)`、`runExecution`。

### 当前状态
- 主工作台顶部区域当前为：
  - 概览卡条
  - 全宽步骤说明模块（顶部横排步骤条 + 下方铺满模块的详情区）
  - 下方实际工作区
- 详情区不再只聚集在中间 560px 小卡内，桌面端已形成更完整的模块内占满效果。

### 本轮回归
- `python -m pytest backend/tests -q` => `67 passed`
- `cd frontend && npm run build` => 通过
- `GET http://127.0.0.1:8000/health` => `200`
- `GET http://127.0.0.1:5173/` => `200`
- `GET http://127.0.0.1:5173/login` => `200`

### 下一步建议
1. 如果你还想继续压缩留白，下一轮可以把右侧辅助列里的标签和按钮做成更紧凑的工具区。
2. 如果想更接近专业工作台风格，可以再补一步，把步骤按钮的选中态做成更明显的分段控制器视觉。

## 进度记录 2026-04-20 13:37

### 本次目标
- 修复默认管理员 `admin / 123456` 在运行时偶发无法登录的问题。
- 把修复做成代码级自恢复，而不是手工重新播种一次数据库。

### 本次完成
- `backend/app/database.py`
  - 新增 `ensure_default_auth_bootstrap()`，统一补齐默认项目、默认管理员与用户主归属项目。
  - `init_db()` 改为复用这条自修复入口，避免启动链路和登录兜底逻辑分叉。
- `backend/app/auth/router.py`
  - 登录接口继续优先走原 `authenticate_user()`。
  - 当且仅当默认管理员 `admin` 登录失败时，触发一次受控自修复并重试一次。
  - 普通用户登录行为保持不变。
- `backend/tests/test_auth_bootstrap.py`
  - 新增“默认管理员缺失时，登录接口可自修复恢复登录”的回归测试。
- 运行态
  - 已重启当前 `backend/run.py` 服务，让 8000 端口实例切换到新修复版本。

### 当前状态
- 当前后端既能在启动时播种默认管理员，也能在默认管理员缺失的坏运行态下于登录时自恢复。
- 实际运行中的 `http://127.0.0.1:8000` 已切换到新版本，`admin / 123456` 可直接登录。

### 本轮回归
- `python -m pytest backend/tests/test_auth_bootstrap.py -q` => `7 passed`
- `python -m pytest backend/tests -q` => `67 passed`
- `cd frontend && npm run build` => 通过
- `GET http://127.0.0.1:8000/health` => `200`
- `POST http://127.0.0.1:8000/api/v1/auth/login` 使用 `admin / 123456` => `200`
- `GET http://127.0.0.1:5173/login` => `200`

### 下一步建议
1. 如果后续允许管理员主动修改默认账号密码，可以把“启动时重置默认密码”和“登录时自修复密码”拆成更细粒度策略。
2. 如果还要继续强化可观测性，可以补一条启动日志或告警，明确记录默认管理员修复是否发生过。

## 进度记录 2026-04-20 12:22

### 本次目标
- 按已确认方案对前端全站执行 Apple Design / Human Interface Guidelines 视觉重构，覆盖共享壳层、主工作台、固定规则页、登录、注册、管理后台与个人设置。
- **红线不变**：Pinia 状态、`watch/onMounted` 生命周期、路由守卫、API 调用、类型协议、后端字段消费、规则执行与认证链路全部保持原有行为。

### 本次完成

#### 触达文件
- [`frontend/src/style.css`](frontend/src/style.css)：在原样式基础上追加 Apple 风格覆盖层，统一全局 token、背景、玻璃材质、Element Plus 组件皮肤、工作台卡片层次、认证页与管理页表现。
- [`frontend/src/fixed-rules.css`](frontend/src/fixed-rules.css)：重绘固定规则页 Header、规则组 pill、规则工作区、组合规则编辑器、SVN 结果卡与弹窗层次，使其与工作台属于同一套设计语言。
- [`frontend/src/App.vue`](frontend/src/App.vue)：脚本顶部补充 `// 保持原有逻辑不变` 注释；共享壳层视觉由 CSS 接管为悬浮玻璃导航与胶囊激活态。
- [`frontend/src/views/MainBoard.vue`](frontend/src/views/MainBoard.vue)、[`frontend/src/views/FixedRulesBoard.vue`](frontend/src/views/FixedRulesBoard.vue)、[`frontend/src/views/LoginView.vue`](frontend/src/views/LoginView.vue)、[`frontend/src/views/RegisterView.vue`](frontend/src/views/RegisterView.vue)、[`frontend/src/views/AdminView.vue`](frontend/src/views/AdminView.vue)、[`frontend/src/views/ProfileView.vue`](frontend/src/views/ProfileView.vue)：脚本顶部统一补充 `// 保持原有逻辑不变` 注释，明确本轮只做视图层改造。

#### 视觉收口结果
- 全局字体栈改为 `-apple-system / SF Pro / PingFang SC`，背景改为 `#f5f5f7` 基底叠加低对比光斑。
- 全站统一为玻璃面板、细描边、多层阴影、大圆角和 `cubic-bezier(0.22, 1, 0.36, 1)` 动效。
- Element Plus 的按钮、输入框、下拉、表格、弹窗、Tag、Alert、Progress、Dropdown 全部改为 Apple 风格皮肤。
- 工作台和固定规则页保留现有 DOM 职责与数据绑定，只重构 Hero、概览条、步骤卡、结果看板、规则组导航、编辑器与弹窗的视觉层次。
- 登录 / 注册 / 管理后台 / 个人设置统一升级为更高完成度的玻璃质感页面，并补充输入聚焦光晕、按钮 hover/active、卡片 hover 浮起等微交互。

#### 严格未触碰
- [`frontend/src/store/`](frontend/src/store/) 全部状态模型
- [`frontend/src/api/`](frontend/src/api/) 全部请求封装
- [`frontend/src/types/`](frontend/src/types/) 全部协议定义
- [`backend/`](backend/) 任何业务代码

### 回归结果
- `cd frontend && npm run build` => 通过
- `python -m pytest backend/tests -q` => `66 passed`
- `python backend/run.py` 启动后 `GET http://127.0.0.1:8000/health` => `200`
- `GET http://127.0.0.1:5173/login` / `register` / `/` => `200`
- 新起一份 `npm run dev -- --host 127.0.0.1 --port 5173` 时，因 `5173` 已被占用自动切到 `http://127.0.0.1:5174/`；`GET /login` / `register` / `/` 均返回 `200`

### 文档同步
- [`README.md`](README.md)：顶部追加本轮全站 Apple Design 视觉重构说明与回归结果。
- [`PROJECT_RECORD.md`](PROJECT_RECORD.md)：追加本次分钟级记录（即本节）。
- [`CHANGELOG.md`](CHANGELOG.md)：在 `[Unreleased]` 追加前端全站 Apple Design 视觉重构条目。
- [`frontend/README.md`](frontend/README.md)：补充本轮前端实际触达范围、视觉方向与运行态验证结果。
- [`需求文档.md`](需求文档.md)：修订记录追加 V4.11，并在现状总览中补充全站 Apple Design 视觉体系已落地。

### 未完成项与风险
- 本轮未新增视觉截图基线或 Playwright/UI 自动化；当前验证口径仍以 `npm run build`、后端 `pytest` 和本地页面访问为主。
- `5173` 端口在联调时已有现存进程，因此新起 Vite 自动切到 `5174`；这不是本轮代码问题，但后续如需固定端口展示可先释放旧进程。

## 进度记录 2026-04-20 15:42

### 本次目标
- 执行 PR-3 Phase 2 物理分层：把 PR-2 已固化的 4 个私有 helper 与 3 个 handler 模块按 `domain / infrastructure / handlers` 三层目录搬迁；调整 import 路径；旧路径保留薄壳 shim 一个发布周期；`engine_core` 副作用 import 改走 `handlers` 包。
- **行为零变更**：任何函数体、字段名、Pydantic 模型、ValueError 文案、`level` 取值、对外接口 0 改动；66 个现有测试与 4 份基线快照均 0 diff；前端业务代码不动。

### 本次完成

#### 新增（10 个文件）
- [`backend/app/rules/domain/__init__.py`](backend/app/rules/domain/__init__.py)：仅 docstring
- [`backend/app/rules/domain/value.py`](backend/app/rules/domain/value.py)：从 `_value.py` 整体迁入；行为 1:1 等价
- [`backend/app/rules/domain/result.py`](backend/app/rules/domain/result.py)：从 `_result.py` 整体迁入；内部 `unwrap_scalar` 引用改走 `domain.value`
- [`backend/app/rules/domain/operators.py`](backend/app/rules/domain/operators.py)：从 `_operators.py` 整体迁入；内部 `is_empty_value / normalize_fixed_text / to_number` 引用改走 `domain.value`
- [`backend/app/rules/infrastructure/__init__.py`](backend/app/rules/infrastructure/__init__.py)：仅 docstring
- [`backend/app/rules/infrastructure/tag_extractor.py`](backend/app/rules/infrastructure/tag_extractor.py)：从 `_tag_extractor.py` 整体迁入；零 import 调整
- [`backend/app/rules/handlers/__init__.py`](backend/app/rules/handlers/__init__.py)：副作用 import `basics / cross / fixed`，触发 `@register_rule`
- [`backend/app/rules/handlers/basics.py`](backend/app/rules/handlers/basics.py)：从 `rule_basics.py` 整体迁入；4 处 import 改为 `domain.* / infrastructure.*`
- [`backend/app/rules/handlers/cross.py`](backend/app/rules/handlers/cross.py)：从 `rule_cross.py` 整体迁入；4 处 import 改为新路径
- [`backend/app/rules/handlers/fixed.py`](backend/app/rules/handlers/fixed.py)：从 `rule_fixed.py` 整体迁入；5 处 import 改为新路径

#### 改造（1 个文件）
- [`backend/app/rules/engine_core.py`](backend/app/rules/engine_core.py)：仅 2 处 import 调整
  - 顶部 `from backend.app.rules._tag_extractor import TagExtractor` → `from backend.app.rules.infrastructure.tag_extractor import TagExtractor`
  - 底部 `from backend.app.rules import rule_basics, rule_cross, rule_fixed  # noqa` → `from backend.app.rules import handlers  # noqa: E402,F401`
  - 函数体、`RuleSpec / RuleExecutionContext / register_rule / execute_rules` 全部不动

#### 旧路径全部改写为薄壳 shim（7 个文件，向后兼容一个发布周期）
- [`backend/app/rules/_value.py`](backend/app/rules/_value.py) → `from backend.app.rules.domain.value import *`
- [`backend/app/rules/_result.py`](backend/app/rules/_result.py) → `from backend.app.rules.domain.result import *`
- [`backend/app/rules/_operators.py`](backend/app/rules/_operators.py) → `from backend.app.rules.domain.operators import *`
- [`backend/app/rules/_tag_extractor.py`](backend/app/rules/_tag_extractor.py) → `from backend.app.rules.infrastructure.tag_extractor import *`
- [`backend/app/rules/rule_basics.py`](backend/app/rules/rule_basics.py) → `from backend.app.rules.handlers.basics import *`
- [`backend/app/rules/rule_cross.py`](backend/app/rules/rule_cross.py) → `from backend.app.rules.handlers.cross import *`
- [`backend/app/rules/rule_fixed.py`](backend/app/rules/rule_fixed.py) → `from backend.app.rules.handlers.fixed import *`

#### 严格未触碰
- [`backend/app/api/`](backend/app/api/) 全部
- [`backend/app/fixed_rules/`](backend/app/fixed_rules/) 全部
- [`backend/app/loaders/`](backend/app/loaders/) 全部
- [`backend/app/utils/`](backend/app/utils/) 全部
- [`backend/tests/`](backend/tests/) 全部
- [`frontend/`](frontend/) 业务代码全部

### 回归结果
- `python -m pytest backend/tests -q` => `66 passed`，PR-1 4 份基线快照 0 diff
- `python -m pytest backend/tests/test_engine_snapshot.py -q -s` => `4 passed`，4 个 case 摘要与 PR-2 完成态完全一致
- `cd frontend && npm run build` => 通过（vite 1.06s，产物 `auth-BsKMUGWj.js / index-CHyr57kN.js / AdminView-CQ5P-f4g.js / ProfileView-Bln0sz_V.js / RegisterView-BnbIKZmR.js / LoginView-CoTbk_B9.js / index-19MGR9tm.css / index.html` 名称与字节体积与 PR-2 一致）
- 后端启动 `python backend/run.py` => `GET http://127.0.0.1:8000/health` 返回 `200 / {"code":200,"msg":"ok","data":{"status":"healthy","service":"excel-check-backend"}}`
  - 注：首次启动撞到 8000 端口被旧进程残留占用，释放后第二次启动一次通过；模块加载与注册流程在第一次启动日志里就已显示 `Application startup complete.`，与本轮重构无关
- 主工作台最小样例 `POST /api/v1/engine/execute` + `minimal_rules.xlsx`：`code=200 / msg=Execution Completed / total_rows_scanned=8 / failed_sources=[] / abnormal_results=5`，与 PR-2 完成态字节级一致
- 固定规则 qa88 真样例 `POST /api/v1/fixed-rules/execute` + `D:\projact_samo\GameDatas\datas_qa88\items.xls -> items -> INT_ID > 0`：`code=200 / msg=Execution Completed / total_rows_scanned=3987 / failed_sources=[] / abnormal_results=0`，与 PR-2 完成态字节级一致

### 加载顺序（重构后）
1. `execute_api` 顶部 `import engine_core`
2. `engine_core` 顶部 `import infrastructure.tag_extractor`（零内部依赖，安全加载）
3. `engine_core` 定义 `RuleSpec / RULE_REGISTRY / register_rule / execute_rules`
4. `engine_core` 底部 `from backend.app.rules import handlers`
5. `handlers/__init__.py` 触发 `import basics / cross / fixed`
6. 三个 handler 模块在 import 时执行 `@register_rule` 装饰器，把 5 个 `rule_type` 写入 `RULE_REGISTRY`

### 文档同步
- [`README.md`](README.md)：顶部追加 2026-04-20 Phase 2 物理分层条目（含三层目录、shim 策略、回归数据）
- [`PROJECT_RECORD.md`](PROJECT_RECORD.md)：追加本次分钟级记录（即本节）
- [`CHANGELOG.md`](CHANGELOG.md) `[Unreleased]` 区追加阶段性变更条目
- [`frontend/README.md`](frontend/README.md)：写明前端 0 改动、`npm run build` 已重新验证
- [`需求文档.md`](需求文档.md)：0.1 修订记录追加 V4.10；0.2 现状总览补充新目录结构说明

### 未完成项与风险
- 不创建 `_registry.py` / `domain/set_assertions.py` / `infrastructure/context_query.py`：PR-3 spec 明确「可选」与「如已在 PR-2 抽出则一并迁入」；本仓库未抽出这三类，未来若有需要再单独 PR 处理
- 旧路径 7 个 shim 应在下一个发布周期统一删除；外部如有引用旧路径请尽快迁移到新路径
- 本轮按红线明确不动 `backend/app/api / fixed_rules / loaders / utils` 与现有任何测试，如未来需要把 fixed_rules 注入形态切到新 helper 是另一轮 PR 的范围

## 进度记录 2026-04-20 14:18

### 本次目标
- 执行 PR-2 Phase 1 引擎重构：抽出共性逻辑、把 `RULE_REGISTRY` 升级为 `RuleSpec(handler + dependent_tags)`、`execute_api._extract_rule_tags` 改走注册表，删除 if/elif 长链。
- **黑盒契约 0 变化**：HTTP 接口、字段语义、`abnormal_results` 6 字段集、所有 ValueError 文案逐字保留；4 份基线快照 0 diff；现有测试一律不修改。

### 本次完成

#### 新增私有 helper 模块（4 个）
- [`backend/app/rules/_value.py`](backend/app/rules/_value.py)：`normalize_text / is_empty_value / normalize_fixed_text / to_number / unwrap_scalar / get_variable_frame / get_business_column_name`，1:1 等价原 `rule_basics` 与 `rule_fixed` 中的同名私有 helper，含中文 `规则 '<rt>' 仅支持单个变量...` 与英文 `Rule '<rt>' references unknown tag '<tag>'.` 异常文案。
- [`backend/app/rules/_result.py`](backend/app/rules/_result.py)：`AbnormalResult` 值对象 + `to_dict()`；`build_basic_result` 等价原 `_build_abnormal_result`，`build_fixed_result` 等价原 `_build_fixed_rule_result`，`raw_value` 自动通过 `unwrap_scalar` 降级。
- [`backend/app/rules/_operators.py`](backend/app/rules/_operators.py)：常量 `COMPARE_OPERATORS / SET_STYLE_OPERATORS`、值对象 `CompareAssertionResult(failed, incomparable)`；`matches_compare_filter / evaluate_compare_assertion / matches_not_null_filter / is_not_null_violation` 同时覆盖筛选与断言两套语义。
- [`backend/app/rules/_tag_extractor.py`](backend/app/rules/_tag_extractor.py)：5 种 `rule_type` 的依赖 tag 提取器 `by_target_tags / by_dict_and_target_tag / by_target_tag / no_tags`，文案与原 `execute_api._extract_rule_tags` 完全一致。

#### 改造文件（5 个）
- [`backend/app/rules/engine_core.py`](backend/app/rules/engine_core.py)：新增 `RuleSpec(handler, dependent_tags)`，`RULE_REGISTRY` 类型升级为 `dict[str, RuleSpec]`；`register_rule(rule_type, *, dependent_tags)` 唯一签名（一次性切换，无兼容层）；`execute_rules` 取出 `RuleSpec.handler` 调用，未命中规则文案保持 `f"Unsupported rule_type: '{rule.rule_type}'."`；末尾副作用 import 保留。
- [`backend/app/rules/rule_basics.py`](backend/app/rules/rule_basics.py)：删除所有原私有 helper，全部改用 `_value / _result / _tag_extractor` 中的对应 API；`@register_rule` 全部改为新签名（`not_null / unique` 用 `by_target_tags`，`regex` 用 `no_tags`）；handler 内循环结构、字段顺序、`level` 取值、message 文案逐字保留。
- [`backend/app/rules/rule_cross.py`](backend/app/rules/rule_cross.py)：完全脱离 `rule_basics` 私有符号；`check_cross_table_mapping` 改用 `by_dict_and_target_tag(rule)` 解包 `[dict_tag, target_tag]`，与 `dependent_tags` 复用同一份代码与文案；`@register_rule("cross_table_mapping", dependent_tags=by_dict_and_target_tag)`。
- [`backend/app/rules/rule_fixed.py`](backend/app/rules/rule_fixed.py)：`COMPARE_OPERATORS / SET_STYLE_OPERATORS` 改从 `_operators` 导入；`_normalize_fixed_text / _to_number / _build_fixed_rule_result / _matches_compare_filter` 删除并切到新 helper；`_evaluate_row_assertion` 内部 not_null 走 `is_not_null_violation`、eq/ne/gt/lt 走 `evaluate_compare_assertion` 并按 `incomparable / failed` 走原有两条报错路径，message 文案逐字保留；`@register_rule("fixed_value_compare", dependent_tags=by_target_tag)` 与 `@register_rule("composite_condition_check", dependent_tags=by_target_tag)`。
- [`backend/app/api/execute_api.py`](backend/app/api/execute_api.py)：`_extract_rule_tags(rule)` 重写为 `return RULE_REGISTRY[rule.rule_type].dependent_tags(rule)`，删除 30 行 if/elif 长链；`_ensure_rule_supported` 文案逐字保留。

#### 严格未触碰
- [`backend/app/api/schemas.py`](backend/app/api/schemas.py) / [`backend/app/api/fixed_rules_schemas.py`](backend/app/api/fixed_rules_schemas.py) / [`backend/app/utils/formatter.py`](backend/app/utils/formatter.py)
- [`backend/app/fixed_rules/`](backend/app/fixed_rules/) 全部 / [`backend/app/api/fixed_rules_api.py`](backend/app/api/fixed_rules_api.py)
- [`backend/app/loaders/`](backend/app/loaders/) 全部
- [`frontend/`](frontend/) 业务代码全部
- [`backend/tests/`](backend/tests/) 现有任何测试与 conftest

### 行为变更披露（合规要求，必须显式记录）
- **唯一行为正向修正**：`composite_condition_check` 之前在 [`backend/app/api/execute_api.py`](backend/app/api/execute_api.py) 的 `_extract_rule_tags` 中漏处理（参见 [`docs/refactor/engine-rules-baseline.md`](docs/refactor/engine-rules-baseline.md) §3 重点段），导致依赖失败 source 时该规则不会被 `_filter_executable_rules` 跳过、而是被传给 handler，handler 在 `loaded_variables` 中找不到 tag → 抛 `Rule 'composite_condition_check' references unknown tag '<tag>'.` → 整次请求退化成 400。
- 本轮把 `composite_condition_check` 注册为 `dependent_tags=by_target_tag` 后，依赖失败 source 时该规则会与其他 `rule_type` 一致被跳过：`failed_sources` 仅记录失败的 source、整次请求继续 200，仅这一条 composite 规则缺席，其余规则继续正常执行。
- **不影响 4 份基线快照**：S1/S2/S3/S4 当前都不包含「composite + 失败 source」组合，全部保持 0 diff，本轮**未**触发 `UPDATE_ENGINE_SNAPSHOT=1`。

### 回归结果
- `python -m pytest backend/tests -q` => `66 passed`
- `python -m pytest backend/tests/test_engine_snapshot.py -q -s` => `4 passed`，4 份快照摘要与 PR-1 完全一致：
  - `S1 code=200 msg='Execution Completed' total_rows_scanned=8 failed_sources=[] abnormal_results=5`
  - `S2 code=200 msg='Execution Completed' total_rows_scanned=5 failed_sources=[] abnormal_results=9`
  - `S3 code=200 msg='Execution Completed' total_rows_scanned=6 failed_sources=[] abnormal_results=7`
  - `S4 code=200 msg='Execution Completed' total_rows_scanned=5 failed_sources=['src_bad'] abnormal_results=2`
- `cd frontend && npm run build` => 通过（vite 构建 2.93s，仅产出 chunk-size warning，无任何前端代码改动）
- 后端启动 `python backend/run.py` => `GET http://127.0.0.1:8000/health` 返回 `200 / {"code":200,"msg":"ok","data":{"status":"healthy","service":"excel-check-backend"}}`
- 主工作台最小样例联调（`POST /api/v1/engine/execute` + `minimal_rules.xlsx`）：`code=200 / msg=Execution Completed / total_rows_scanned=8 / failed_sources=[] / abnormal_results=5`，与 README 历史基线一致。
- 固定规则 qa88 真样例联调（`POST /api/v1/fixed-rules/execute` + `D:\projact_samo\GameDatas\datas_qa88\items.xls -> items -> INT_ID > 0`）：`code=200 / msg=Execution Completed / total_rows_scanned=3987 / failed_sources=[] / abnormal_results=0`。
  - 与历史基线 `total_rows_scanned=3917` 的差异是真实数据自然增长（用户本地 svn 工作副本已被刷新），`abnormal_results = 0` 与历史一致；行为口径无任何漂移。

### 文档同步
- [`README.md`](README.md)：顶部追加 2026-04-20 Phase 1 重构条目（含 4 个新文件、RuleSpec 升级、composite 行为修正披露、回归数据）。
- [`PROJECT_RECORD.md`](PROJECT_RECORD.md)：追加本次分钟级记录（即本节）。
- [`CHANGELOG.md`](CHANGELOG.md)：在 `[Unreleased]` 区追加阶段性变更条目。
- [`frontend/README.md`](frontend/README.md)：写明前端 0 改动 + 已重新跑 `npm run build`。
- [`需求文档.md`](需求文档.md)：0.1 修订记录追加 V4.9，0.2 现状总览补充一段 RuleSpec 注册模型说明。

### 未完成项与风险
- 本轮按红线明确不创建 `domain/ infrastructure/ handlers/` 等子目录；这些是 Phase 2 物理移动的范围。
- 本轮按红线不动任何 schemas、loader、`fixed_rules/`、前端业务代码。
- composite 行为修正后，未来任何「composite + 失败 source」的快照都需要新增（PR-1 baseline §3 已建议加入但本轮按对话结论留待 PR-2 之后专门补充）；当前 4 份快照不受影响。

## 进度记录 2026-04-20 11:42

### 本次目标
- 引入 PR-1 引擎执行黑盒快照基线测试，作为后续 PR-2 物理移动 / 拆分阶段的安全网。
- **本轮严格不动任何业务代码**：`backend/app/` 下的 `.py` 全部保持不变，现有测试、conftest、API 协议、前端实现一律不动。

### 本次完成
- 新增 [`backend/tests/test_engine_snapshot.py`](backend/tests/test_engine_snapshot.py)：
  - 直接打 `POST /api/v1/engine/execute`，对外响应做字节级快照。
  - 写快照与读快照前都把 `meta.execution_time_ms` 强制归零，规避毫秒级抖动。
  - 序列化口径统一：`json.dumps(..., sort_keys=True, ensure_ascii=False, indent=2)` + 强制 `LF` 行尾。
  - 通过环境变量 `UPDATE_ENGINE_SNAPSHOT=1` 切换写入模式；默认走断言模式。
  - 终端打印每个 case 的 `code / msg / total_rows_scanned / failed_sources / abnormal_results 数量`。
- 新增 4 份基线快照（[`backend/tests/snapshots/engine/`](backend/tests/snapshots/engine/)）：
  - `S1.json`：主工作台基线 `not_null + unique + cross_table_mapping`，`abnormal_results = 5`。
  - `S2.json`：固定规则单值比较 `fixed_value_compare` 的 `eq / ne / gt / lt` 各 1 条，`abnormal_results = 9`。
  - `S3.json`：固定规则组合分支 `composite_condition_check`，同时覆盖 `global_filters + branch.filters` 与 `eq / not_null / unique / duplicate_required` 4 类 assertion，`abnormal_results = 7`。
  - `S4.json`：失败 source 降级，`failed_sources == ["src_bad"]`、`abnormal_results = 2`，依赖失败 source 的规则被 `_filter_executable_rules` 跳过，其余规则继续执行。
- 新增干净测试数据集 [`backend/tests/data/snapshot_engine.xlsx`](backend/tests/data/snapshot_engine.xlsx)：
  - `values` sheet：`ID` 列为整数序列 `[1, 2, 2, 3, 5]`，专供 S2 使用，避开 `minimal_rules.xlsx` 中 NaN/空白单元格在 FastAPI JSON 序列化阶段的非确定性。
  - `items` sheet：`INT_ID / INT_Faction / INT_Group` 三列，专供 S3 组合变量使用。
- 同步更新 [`README.md`](README.md)、[`frontend/README.md`](frontend/README.md)、[`CHANGELOG.md`](CHANGELOG.md)、[需求文档.md](需求文档.md) 的顶部说明与修订表。

### 回归结果
- `python -m pytest backend/tests/test_engine_snapshot.py -q -s`（默认断言模式）→ `4 passed`
- `python -m pytest backend/tests -q` → `66 passed`（原 62 通过 + 新增 4 通过）
- 终端摘要打印：
  - `S1`：`code=200 msg='Execution Completed' total_rows_scanned=8 failed_sources=[] abnormal_results=5`
  - `S2`：`code=200 msg='Execution Completed' total_rows_scanned=5 failed_sources=[] abnormal_results=9`
  - `S3`：`code=200 msg='Execution Completed' total_rows_scanned=6 failed_sources=[] abnormal_results=7`
  - `S4`：`code=200 msg='Execution Completed' total_rows_scanned=5 failed_sources=['src_bad'] abnormal_results=2`

### 文档同步
- [PROJECT_RECORD.md](PROJECT_RECORD.md)：追加本次分钟级进度记录（即本节）。
- [CHANGELOG.md](CHANGELOG.md)：在 `[Unreleased]` 区追加「新增引擎执行黑盒快照测试 baseline（S1/S2/S3/S4）」。
- [README.md](README.md)：顶部追加 2026-04-20 简短说明，明确本轮仅新增测试基线、不改业务。
- [frontend/README.md](frontend/README.md)：顶部追加同日简短说明，明确前端无任何改动。
- [需求文档.md](需求文档.md)：0.1 修订记录追加 V4.8 一行。

### 未完成项与风险
- 本轮不专门覆盖 [backend/app/api/execute_api.py](backend/app/api/execute_api.py) 中 `_extract_rule_tags` 对 `composite_condition_check` 的漏判（与 [docs/refactor/engine-rules-baseline.md](docs/refactor/engine-rules-baseline.md) 一致），该 case 留待 PR-2 修复时一并补充。
- baseline 快照已与当前实现完全一致；PR-2 阶段如需主动变更响应外形，应在评审通过后用 `UPDATE_ENGINE_SNAPSHOT=1` 显式刷新基线。
- 本轮按红线要求未触发 frontend 任何命令；前端构建结果不在本次回归口径内。

## 进度记录 2026-04-17 19:33

### 本次目标
- 收口普通用户主归属项目语义，开放项目管理员受限版 `/admin`，并补齐后台成员区归属项目调整闭环。

### 本次完成
- `backend/app/models.py`：
  - 为 `User` 新增 `primary_project_id`，用于表达稳定的主归属项目。
- `backend/app/database.py`：
  - 启动初始化时补齐已有 SQLite 运行库的 `users.primary_project_id` 列。
  - 对旧用户回填主归属项目，默认超级管理员播种时同步写入主归属项目。
- `backend/app/auth/service.py`、`backend/app/auth/router.py`、`backend/app/auth/dependencies.py`：
  - 登录与 `/auth/me` 的当前项目选择改为优先使用主归属项目，不再依赖 `roles[0]`。
  - 注册用户时自动把注册项目写入主归属项目。
- `backend/app/admin/schemas.py`、`backend/app/admin/router.py`：
  - 新增普通用户归属项目调整接口 `PUT /api/v1/admin/projects/{project_id}/members/{user_id}/project`。
  - `/admin/projects` 与项目编辑接口开放给项目管理员的受限版权限。
  - 成员列表新增 `primary_project_id / primary_project_name` 返回。
  - 归属项目调整明确禁止作用于超级管理员和项目管理员。
  - 项目删除、成员删除迁移到默认项目时，同步修正主归属项目。
- `frontend/src/router/index.ts`、`frontend/src/App.vue`：
  - `/admin` 路由守卫与导航入口改为对项目管理员和超级管理员开放。
- `frontend/src/api/admin.ts`、`frontend/src/types/auth.ts`、`frontend/src/views/AdminView.vue`：
  - 管理后台成员区新增“归属项目”列和“调整归属项目”交互。
  - 页面打开或刷新项目列表后，默认选中第一个可管理项目，避免右侧空白。
  - 项目管理员当前只能管理自己可管理项目，且不能创建或删除项目。
- `backend/tests/test_admin_projects.py`、`backend/tests/test_auth_bootstrap.py`、`backend/tests/conftest.py`：
  - 补充主归属项目登录选择、项目管理员受限后台权限、普通用户归属项目调整、成员列表归属项目返回等回归测试。

### 回归结果
- `python -m pytest backend/tests -q` → `62 passed`
- `cd frontend && npm run build` → 通过
- 运行态补充验证：
  - `GET http://127.0.0.1:8001/health` → `200`
  - `POST http://127.0.0.1:8001/api/v1/auth/login` 使用 `admin / 123456` → `200`
  - `GET http://127.0.0.1:8001/api/v1/auth/me` → `200`
  - `GET http://127.0.0.1:8001/api/v1/admin/projects` → `200`
  - `GET http://127.0.0.1:5174` → 可访问

### 当前项目进度

#### 已完成功能
- 默认管理员与唯一超级管理员收口
- 主归属项目语义与登录默认项目选择收口
- 项目管理员受限版管理后台
- 普通用户归属项目展示与调整闭环
- 多用户认证、项目隔离、主工作台与固定规则页主链路

#### 已实现但未打通 / 占位功能
- `regex` 规则已注册但未闭环
- `svn` 作为主工作台独立 source 类型的完整闭环未开放
- `feishu` 数据源仍为占位实现

#### 未开始功能
- 固定规则结果导出
- 固定规则多配置集切换
- 多用户协同编辑冲突处理

### 文档同步
- 更新 `README.md`
- 更新 `frontend/README.md`
- 更新 `CHANGELOG.md`
- 更新 `需求文档.md`
- 追加本次分钟级进度记录到 `PROJECT_RECORD.md`

### 未完成项与风险
- 当前运行时数据库仍未接入 Alembic 迁移脚本，本轮通过启动阶段轻量补列兼容已有 SQLite 库；后续表结构演进仍需标准迁移方案。
- 本轮默认端口 `8000 / 5173` 被现有本地进程占用，因此新增运行态验证改用 `8001 / 5174` 补充完成；未主动干预用户现有进程。

## 进度记录 2026-04-17 18:56

### 本次目标
- 修复默认超级管理员 `admin / 123456` 登录时返回 `500 Internal Server Error` 的问题。

### 本次完成
- `backend/app/database.py`：
  - 修复启动初始化顺序，改为先显式导入 ORM 模型，再执行 `Base.metadata.create_all()`。
  - 修复默认项目播种逻辑，按项目名 `默认项目` 保证系统保留项目存在，不再因为库中已有任意项目而提前返回。
  - 收口默认超级管理员播种与修复逻辑，确保 `admin / 123456` 始终存在且为唯一超级管理员，并补齐默认项目成员关系。
- `backend/tests/conftest.py`：
  - 测试环境改为稳定建表后按表清空数据，避免反复 `drop_all / create_all` 带来的表状态不一致。
- `backend/tests/test_auth_bootstrap.py`：
  - 补充“默认项目按名称创建”和“空库初始化后 admin 可直接登录”回归测试。

### 回归结果
- `python -m pytest backend/tests -q` → `56 passed`
- `cd frontend && npm run build` → 通过
- `GET http://127.0.0.1:8000/health` → `200`
- `GET http://127.0.0.1:5173` → `200`
- `POST /api/v1/auth/login` 使用 `admin / 123456` → `200`

### 当前项目进度

#### 已完成功能
- 默认管理员与唯一超级管理员收口
- 运行时数据库自动建表、默认项目播种、默认管理员播种
- 多用户认证、项目隔离、管理后台、主工作台与固定规则页主链路

#### 已实现但未打通 / 占位功能
- `regex` 规则已注册但未闭环
- `svn` 作为主工作台独立 source 类型的完整闭环未开放
- `feishu` 数据源仍为占位实现

#### 未开始功能
- 固定规则结果导出
- 固定规则多配置集切换
- 多用户协同编辑冲突处理

### 文档同步
- 更新 `README.md`
- 更新 `frontend/README.md`
- 更新 `CHANGELOG.md`
- 更新 `需求文档.md`
- 追加本次分钟级进度记录到 `PROJECT_RECORD.md`

### 未完成项与风险
- 当前运行时数据库仍未接入 Alembic 迁移脚本，后续表结构演进仍需继续补标准迁移流程。

## 进度记录 2026-04-17 16:20

### 本次目标
- 为超级管理员补齐管理后台中的项目编辑与删除闭环，并确保默认项目不可删除。

### 本次完成
- `backend/app/admin/router.py`：新增 `DELETE /api/v1/admin/projects/{project_id}`，补齐默认项目删除保护、项目不存在 `404`、项目名重复 `400`，并在删除时显式清理项目级固定规则与工作台配置记录。
- `frontend/src/api/admin.ts`：新增删除项目 API 封装。
- `frontend/src/views/AdminView.vue`：补充项目编辑弹窗、项目删除确认、项目卡编辑/删除入口，以及编辑/删除后的选中态与成员列表刷新逻辑。
- `frontend/src/style.css`：补充管理后台项目卡操作区与项目编辑弹窗局部样式。
- `backend/tests/test_admin_projects.py`：新增项目编辑、删除、默认项目保护和非超级管理员拦截测试。

### 回归结果
- `python -m pytest backend/tests -q` → `49 passed`
- `cd frontend && npm run build` → 通过
- 管理后台项目编辑 / 删除闭环已完成代码级回归，后续联调将以 `admin / 123456` 登录验证。

### 当前项目进度

#### 已完成功能
- JWT 用户认证体系（注册 / 登录 / 默认管理员修复）
- 三级角色权限（超级管理员 / 项目管理员 / 普通用户）
- 管理后台项目创建、修改、删除与成员管理
- 个人中心（修改密码 + 切换项目）
- 主工作台四步校验闭环
- 固定规则模块完整持久化与执行闭环

#### 已实现但未打通 / 占位功能
- `regex` 规则已注册但未闭环
- `svn` 作为主工作台独立 source 类型的完整闭环未开放
- `feishu` 数据源仍为占位实现
- CSV 变量池下拉提取未开放

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
- 删除项目当前为永久删除，不提供恢复能力。
- 默认项目保护当前按系统保留项目口径实现，后续如需多保留项目需单独扩展策略。

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

## 进度记录 2026-04-17 15:46

### 本次目标
- 收口多用户认证中的超级管理员来源，移除“首个注册用户自动升超管”逻辑。
- 固定系统默认超级管理员为 `admin / 123456`，并让权限边界回到“全局超管 + 项目管理员”两层语义。

### 本次完成
- 删除后端注册流程里按用户总数判断首个注册用户升超管的逻辑，普通注册用户现在固定为普通用户。
- 在数据库启动初始化链路中新增默认管理员播种/修复：
  - 不存在 `admin` 时自动创建 `admin / 123456`
  - 存在 `admin` 时强制修复为唯一超级管理员，并同步默认密码
  - 其他已有超级管理员全部降级为普通用户
  - 默认管理员自动加入默认项目并具备项目管理员角色
- 新增认证回归测试，覆盖：
  - 默认管理员播种
  - 已有多超管状态收口为 `admin` 唯一超管
  - 注册用户不再自动成为超级管理员
- 同步更新 `README.md`、`frontend/README.md`、`CHANGELOG.md`、`需求文档.md`

### 本轮回归
- `python -m pytest backend/tests -q` => `45 passed`

### 当前状态
- 系统当前的权限来源已经收口为：
  - 全局层：`User.is_super_admin`
  - 项目层：`UserProjectRole.role`
- 当前默认只保留一个全局超级管理员入口 `admin / 123456`，后续若要新增其他全局超管，需要通过单独的后台能力实现，不再走注册自动提权。

### 下一步建议
1. 后续单开一轮后台能力扩展，为现有超级管理员增加“手动提升 / 取消全局超级管理员”的管理入口。
2. 再单开一轮把“项目管理员”在后台中的可见菜单、接口权限和成员分配操作彻底补齐。

## 进度记录 2026-04-17 17:12

### 本次目标
- 收口管理后台删除项目后的成员去向和页面刷新行为。
- 保证删除普通项目时不会误删账号，并让后台状态在删除后彻底同步。

### 本次完成
- 后端 `DELETE /api/v1/admin/projects/{project_id}` 新增成员迁移逻辑：
  - 删除普通项目前，先把项目成员迁移到默认项目 `默认项目`
  - 迁移后的成员统一降为普通用户 `user`
  - 若该成员已在默认项目存在角色记录，则保留原记录，不重复插入也不覆盖
- 项目删除后继续清理该项目下的固定规则配置和工作台配置，再删除项目本身。
- 前端管理后台删除项目成功后改为整页刷新，避免项目列表、成员区和用户项目上下文残留旧状态。
- 同步更新 `README.md`、`frontend/README.md`、`CHANGELOG.md`、`需求文档.md`。

### 当前状态
- 默认项目仍然不可删除。
- 删除普通项目时，成员会被保留并自动迁移到默认项目，不会被删除账号。
- 管理后台删除成功后会整页刷新一次，当前页面状态与最新数据库状态保持一致。

### 本轮回归
- `python -m pytest backend/tests -q`
- `cd frontend && npm run build`

### 下一步建议
1. 如果后续成员迁移还需要可配置规则，可再单开一轮支持“迁移到指定项目”或“保留原项目角色”策略。
2. 如需降低整页刷新成本，后续可再单开一轮改成更细粒度的 store 与上下文刷新。

## 进度记录 2026-04-17 18:08

### 本次目标
- 收口管理后台“成员删除”在默认项目和普通项目中的行为差异。
- 修复删除项目后的报错链路，同时保持后台删除项目后的整页刷新策略。

### 本次完成
- `backend/app/admin/router.py`
  - 默认项目中删除成员时，改为直接删除用户账号
  - 其他项目中删除成员时，改为迁移到默认项目并删除当前项目角色
  - 默认项目中的超级管理员与当前登录管理员本人现在明确禁止删除
- `backend/tests/test_admin_projects.py`
  - 新增成员删除迁移、默认项目删账号、默认项目超管保护、当前用户保护等回归测试
- `frontend/src/views/AdminView.vue`
  - 成员操作按钮文案从“移除”统一为“删除”
  - 删除成员统一增加二次确认
  - 默认项目与普通项目使用不同的确认文案和成功提示
- 同步更新 `README.md`、`frontend/README.md`、`CHANGELOG.md`、`需求文档.md`

### 当前状态
- 默认项目中删除成员 = 删除用户账号
- 其他项目中删除成员 = 迁移到默认项目
- 删除项目后仍然保持整页刷新，成员迁移链路继续有效

### 本轮回归
- `python -m pytest backend/tests -q`
- `cd frontend && npm run build`

### 下一步建议
1. 如果后续要支持“删除成员后迁移到指定项目”，建议单开一轮补迁移目标选择。
2. 如果后续要支持用户归档而不是删号，可再单开一轮引入账号禁用态。

## 进度记录 2026-04-17 18:28

### 本次目标
- 修复管理后台删除项目后前端弹出 `Unexpected end of JSON input` 的问题。

### 本次完成
- 在 `frontend/src/utils/apiFetch.ts` 中补充 `204 No Content` 与空响应体兼容逻辑：
  - 删除项目接口成功返回空 body 时，前端不再继续执行 `response.json()`
  - 普通 `200` 但响应体为空时，也统一安全返回 `undefined`
- 同步更新 `README.md`、`frontend/README.md`、`CHANGELOG.md`、`需求文档.md`
- 继续保留删除项目后的整页刷新策略，不改变现有删除业务语义

### 当前状态
- 管理后台删除普通项目后，不应再出现 `Failed to execute 'json' on 'Response': Unexpected end of JSON input`
- 删除项目链路继续保持：
  - 成员迁移到默认项目
  - 后台整页刷新

### 本轮回归
- `python -m pytest backend/tests -q`
- `cd frontend && npm run build`

### 下一步建议
1. 如果后续还要统一更多空响应接口，可继续把 `apiFetch` 的成功响应处理沉淀成更明确的响应规范。

## 进度记录 2026-04-20 12:45

### 本次目标
- 把前端认证后壳层收口为桌面级全屏应用，固定左侧导航与右侧独立滚动工作区。
- 在不改 Pinia、路由守卫、API、事件绑定和后端字段消费的前提下，完成工作台、固定规则页、管理后台、个人设置、登录、注册的布局升级。

### 本次完成
- `frontend/src/App.vue`
  - 顶部导航壳层改为左侧固定边栏，统一承载 `工作台 / 固定规则 / 管理后台 / 个人设置 / 项目切换 / 退出登录`
  - 保留原项目切换、登出和角色显隐逻辑，并补充 `// 保留原有业务逻辑` 注释
- `frontend/src/views/MainBoard.vue`
  - 改为左侧四步流程导航 + 右侧工作内容区
  - 顶部工具条收口样例、清错、执行与状态信息
  - 保留数据遍历、执行入口、自动保存和滚动定位逻辑
- `frontend/src/views/FixedRulesBoard.vue`
  - 改为上方配置区 + 左侧规则组侧栏 + 右侧规则编辑与结果区的桌面工具布局
  - 保留 `loadCapabilities / loadConfig / executeConfig / runSvnUpdate` 与规则组、规则列表遍历逻辑
- `frontend/src/views/AdminView.vue`、`ProfileView.vue`、`LoginView.vue`、`RegisterView.vue`
  - 统一切换为更稳定的桌面面板结构
  - 继续保留既有提交、跳转、项目切换和鉴权调用逻辑
- `frontend/src/style.css`、`frontend/src/fixed-rules.css`
  - 补齐全屏应用壳层、独立滚动区、固定规则三段式布局和对应响应式收口
- 同步更新 `README.md`、`CHANGELOG.md`、`frontend/README.md`、`需求文档.md`

### 当前状态
- 认证后页面当前统一为桌面级全屏应用壳层，浏览器页面本身不再承担主业务滚动。
- 被触达页面已显式补充 `// 保留原有业务逻辑` / `// 保持原有逻辑不变` 注释，便于后续继续做 UI 演进时核对业务零改动边界。
- 固定规则页现在具备更清晰的“配置区 / 规则组 / 规则与结果工作区”分区，长规则组列表限制在侧栏内部滚动。

### 本轮回归
- `cd frontend && npm run build` => 通过
- `python -m pytest backend/tests -q` => `66 passed`
- `GET http://127.0.0.1:8000/health` => `200`
- `GET http://127.0.0.1:5173/login` / `register` / `/` / `fixed-rules` / `admin` / `profile` => `200`

### 下一步建议
1. 如果下一轮还要继续减字，可优先把表格内的长摘要、规则条件描述和空状态说明进一步收进 Tooltip / Popover。
2. 如果后续要做更强的桌面工作流体验，可以单开一轮补充键盘快捷操作、分段控制器高亮动画和结果区筛选器。

## 进度记录 2026-04-20 13:11

### 本次目标
- 把主工作台中原左侧侧栏底部的“下一步说明”单卡迁移到 hero 下方。
- 将该区域改为“左侧步骤导航 + 右侧详情栏”双栏结构，同时保持原滚动定位和执行入口不变。

### 本次完成
- `frontend/src/views/MainBoard.vue`
  - 新增基于现有 `workflowGuide / stepHints / stepStatuses` 组织出来的 `stepGuideItems`
  - hero 下方新增步骤说明区，左侧显示 `数据源 / 变量池 / 规则 / 结果`，右侧显示当前步骤的完整说明、状态摘要和操作按钮
  - 左侧点击步骤后会同步切换详情，并继续调用原 `scrollToStep(step)` 逻辑
  - 当步骤 4 处于“可执行”状态时，详情区按钮继续复用原 `runExecution` 入口
  - 原左侧侧栏底部的 `workflowGuide` 卡片移除，侧栏只保留步骤跳转
- `frontend/src/style.css`
  - 新增 `workbench-step-guide-*` 样式，收口 hero 下方的步骤说明区布局、卡片层次和移动端折叠表现
  - 原左侧步骤导航与新说明区共享选中态高亮
- 同步更新 `README.md`、`CHANGELOG.md`、`frontend/README.md`、`需求文档.md`

### 当前状态
- 主工作台当前同时具备：
  - hero 下方的步骤说明区，用于集中阅读每一步的说明
  - 左侧步骤导航，用于快速跳转到实际工作区
- 新说明区不引入第二套业务状态，只是复用既有计算结果做视图重组。

### 本轮回归
- `cd frontend && npm run build` => 通过
- `python -m pytest backend/tests -q` => `66 passed`
- `GET http://127.0.0.1:8000/health` => `200`
- `GET http://127.0.0.1:5173/login` / `register` / `/` / `fixed-rules` / `profile` => `200`

### 下一步建议
1. 如果你希望这块更像 macOS Finder 的 inspector，下一轮可以把右侧详情做成更强的信息层级和图标化摘要。
2. 如果后续要继续压缩首页信息密度，可以再把概览卡和步骤说明区合并成一块分区式看板。

## 进度记录 2026-04-20 13:19

### 本次目标
- 把主工作台说明模块中的步骤按钮改为顶部横排。
- 移除左侧旧步骤列，让页面只保留一套步骤导航入口。

### 本次完成
- `frontend/src/views/MainBoard.vue`
  - 移除 `workbench-desktop-layout` 中左侧旧步骤列
  - 保留 hero 下方说明模块，并让步骤按钮只在该模块顶部横排展示
  - 顶部横排按钮继续复用 `stepGuideItems`、`activeGuideDetail` 和 `handleGuideStepClick`
  - 点击步骤后仍同步切换详情，并继续调用原 `scrollToStep(step)` 逻辑
- `frontend/src/style.css`
  - `workbench-step-guide-shell` 改为“顶部横排步骤条 + 下方详情卡”的纵向结构
  - `workbench-step-guide-nav` 改为四等分横排，移动端降级为两列换行
  - `workbench-desktop-layout` 改为单列内容区，消除旧侧栏留白
- 同步更新 `README.md`、`CHANGELOG.md`、`frontend/README.md`、`需求文档.md`

### 当前状态
- 主工作台当前只保留一套顶部横排步骤按钮，不再存在左侧重复步骤列。
- 页面结构已收口为：
  - 顶部 hero
  - hero 下方说明模块（顶部横排步骤条 + 下方详情卡）
  - 下方工作内容区

### 本轮回归
- `cd frontend && npm run build` => 通过
- `python -m pytest backend/tests -q` => `66 passed`
- `GET http://127.0.0.1:8000/health` => `200`
- `GET http://127.0.0.1:5173/` / `login` / `register` / `fixed-rules` / `profile` => `200`

### 下一步建议
1. 如果还想更贴近你给的示意图，下一轮可以继续把横排步骤按钮压缩得更“胶囊化”，减少内部字数层级。
2. 如果后续首页还要进一步去网页感，可以再把概览卡位置往说明模块内部收，减少模块切换感。

## 进度记录 2026-04-20 13:30

### 本次目标
- 让主工作台顶部排版更接近最新示意图。
- 收口“概览卡、步骤条、详情卡”三者的上下关系与居中方式。

### 本次完成
- `frontend/src/views/MainBoard.vue`
  - 调整顶部结构顺序，改为“概览卡在上、步骤说明模块在下”
  - 步骤说明模块内部继续保留横排步骤条和详情卡，但整体移入主内容区并与概览卡形成同一层级
- `frontend/src/style.css`
  - 收口步骤说明模块为更居中的大面板
  - 横排步骤条宽度压缩到更接近示意图
  - 详情卡改为固定最大宽度并居中显示
- 同步更新 `README.md`、`CHANGELOG.md`、`frontend/README.md`、`需求文档.md`

### 当前状态
- 主工作台顶部区域当前为：
  - 概览卡条
  - 步骤说明模块（上方横排步骤条 + 下方居中详情卡）
  - 下方具体工作区
- 整体版式已经比上一轮更接近你给的第二张图。

### 本轮回归
- `cd frontend && npm run build` => 通过
- `python -m pytest backend/tests -q` => `66 passed`
- `GET http://127.0.0.1:8000/health` => `200`
- `GET http://127.0.0.1:5173/` / `login` => `200`

### 下一步建议
1. 如果你还想继续贴近图稿，下一轮可以把详情卡的按钮和标签再往右侧收，做成更轻的浮层感。
2. 如果顶部概览卡还显得过高，可以继续压缩卡片高度和 icon 尺寸。

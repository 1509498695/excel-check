# Excel Check Frontend

## 2026-04-14 多用户认证与前端配套

- **新增页面**：`LoginView.vue`、`RegisterView.vue`（登录 / 注册）、`AdminView.vue`（管理控制台）、`ProfileView.vue`（个人资料）。
- **默认超级管理员**：系统启动时会固定维护 `admin / 123456` 作为全局超级管理员；注册页创建的新用户默认都是普通用户，不再自动晋升为超级管理员。
- **请求封装**：`src/utils/apiFetch.ts` 统一发起 API 请求，自动注入 JWT；收到 `401` 时清理本地会话并跳转登录。
- **认证状态**：`src/store/auth.ts`（Pinia）维护登录态、当前用户与角色等信息。
- **API 模块**：`src/api/auth.ts`（注册、登录、当前用户等）、`src/api/admin.ts`（项目与成员等管理接口）。
- **路由守卫**：`src/router/index.ts` 中全局 `beforeEach`，按路由元信息区分需登录、仅访客（guest）、超级管理员（admin）等访问策略。
- **工作台自动保存**：`workbench` store 在主要状态变更后采用 **2 秒防抖（debounce）** 自动调用后端持久化，减少频繁写入。
- **切换项目数据同步**：项目切换后不再整页刷新，改为 SPA 内重置 `workbench` 和 `fixedRules` store 并重新加载对应项目数据，空项目不残留旧配置。
- **`App.vue`**：头部增加用户下拉菜单（个人资料、退出等）；**超级管理员** 可见 **管理后台** 导航入口。

## 2026-04-14 主工作台步骤 3 规则组编排
- 步骤 3 使用 `WorkbenchRuleOrchestrationPanel.vue`，与 `/fixed-rules` 规则组/规则弹窗交互同构；状态仅存 `useWorkbenchStore`，与 `fixed-rules` store 隔离。
- 删除 `RuleComposerPanel.vue`；样例编排改为 `fixed_value_compare` + `not_null` + `unique` 组合，最小样例当前 `abnormal_results = 4`。
- 回归：`npm run build` 通过；`pytest backend/tests` 由根目录执行仍为 `40 passed`。

文档更新时间：2026-04-17 15:46
 
## 2026-04-13 固定规则页文案收口
- `/fixed-rules` 页面的 Hero、步骤说明、变量池提示、规则编辑辅助文案和结果区文案已做强收口。
- 本轮不改结构和交互，只压缩固定规则页可见文案密度。

## 2026-04-13 工作台首页视觉与文案收口说明
- 主工作台首页 `/` 与共享头部完成一轮视觉精修，不改现有 DOM 层级、Grid / Flex 骨架、类名和事件绑定。
- 本轮主要调整：
  - 收口全局背景、边框、阴影、圆角和间距层级
  - 优化 `workbench-topbar`、`overview-strip`、`workflow-guide`、`section-block` 的视觉呼吸感
  - 精简首页 CTA、状态提示和步骤说明文案
  - 修复首页与共享头部中的可见中文乱码
- 回归结果：
  - `cd frontend && npm run build`：通过
  - `http://127.0.0.1:5173`：`200`
  - `http://127.0.0.1:5173/fixed-rules`：`200`
  - `POST /api/v1/engine/execute`：`Execution Completed / total_rows_scanned = 8 / failed_sources = [] / abnormal_results = 4`

## 2026-04-13 固定规则页组合变量条件分支校验说明
- `/fixed-rules` 现在支持把固定规则页变量池中的组合变量直接绑定到规则弹窗。
- 选择组合变量后，弹窗会从简单规则表单切换为组合变量条件分支编辑器，结构为：
  - `全局筛选条件`
  - `条件分支列表`
  - `分支筛选条件`
  - `分支校验条件`
- 前端展示中的 `Key` 对应组合变量 JSON 的映射键；后端执行期内部映射为 `__key__`。
- 当前支持的组合变量规则语义：
  - 筛选条件：`等于 / 不等于 / 大于 / 小于 / 非空`
  - 校验条件：`等于 / 不等于 / 大于 / 小于 / 非空 / 唯一 / 必须重复`
  - 比较类条件右值支持：`固定值` 或 `字段`
- 单变量与组合变量共用一个“新增规则”入口，但保存时会按目标变量类型自动选择正确规则协议：
  - 单变量 -> 原有简单规则
  - 组合变量 -> `composite_condition_check`
- 本轮前端回归：
  - `cd frontend && npm run build`：通过
  - `http://127.0.0.1:5173`：`200`
  - `http://127.0.0.1:5173/fixed-rules`：`200`

## 2026-04-11 固定规则页失效路径告警说明
- 修复了固定规则页在读取已保存但路径失效的固定规则配置时，因为后端返回 `500` 导致页面只显示错误提示、无法进入修复流程的问题。
- 固定规则页现在会在 `loadConfig()` 成功后同时接收 `meta.config_issues`，即使存在失效路径也会继续渲染已保存配置。
- 页面顶部新增中文 warning 提示，至少会说明：
  - 哪个 `source_id` 有问题
  - 当前失效路径是什么
  - 需要到 `数据源接入管理` 中修复
- 固定规则页复用的 `DataSourcePanel` 现在支持按 `source_id` 注入问题提示；失效数据源行会显示 `路径失效` 状态，并在路径下方补充 warning 文案。
- 固定规则页存在阻断性配置问题时，执行入口会自动禁用，避免继续触发后端 `400`。
- 本轮回归结果：
  - `python -m pytest backend/tests -q`：`33 passed`
  - `cd frontend && npm run build`：通过
  - `http://127.0.0.1:5173/fixed-rules`：`200`

## 2026-04-11 变量池面板乱码修复说明
- 修复了 `frontend/src/components/workbench/VariablePoolPanel.vue` 里的 `????` 占位文案。
- 当前主工作台步骤 2 与固定规则页变量池模块已恢复正常中文显示，覆盖：
  - 按钮
  - 表格列头
  - 表单标签
  - 空状态
  - JSON 预览区
  - 变量详情弹窗
- 顺手修复了一处 `Sheet` 选择框占位乱码。
- 本次只调整前端展示文案，不改接口、Pinia 状态和固定规则 `version = 4` 配置结构。
- 本轮回归结果：
  - `cd frontend && npm run build`：通过
  - `http://127.0.0.1:5173`：`200`
  - `http://127.0.0.1:5173/fixed-rules`：`200`

## 2026-04-10 固定规则页独立持久化能力说明
- `/fixed-rules` 现在会在规则组导航上方显示两块独立模块：
  - `数据源接入管理`
  - `变量池构建`
- 这两块模块复用了工作台现有 UI，但底层不再复用 `useWorkbenchStore()`，而是连接固定规则页自己的 `useFixedRulesStore()`。
- 固定规则页的数据源、变量、规则当前统一保存到 `version = 4` 的固定规则配置中；刷新页面后仍会自动回填。
- 固定规则页与主工作台的数据源、变量池完全隔离，两个页面不会互相显示对方的数据。
- 固定规则弹窗已移除：
  - `规则文件路径`
  - `读取结构`
  - `Sheet`
  - `目标列`
- 固定规则弹窗改为直接从固定规则页变量池选择 `目标变量`；当前仅允许选择单变量，组合变量继续支持持久化和预览，但不进入当前规则执行链路。
- 当前回归结果：
  - `python -m pytest backend/tests -q`：`30 passed`
  - `cd frontend && npm run build`：通过
  - `http://127.0.0.1:8000/health`：`200`
  - `http://127.0.0.1:5173`：`200`
  - `http://127.0.0.1:5173/fixed-rules`：`200`
  - 固定规则页真实联调：`Execution Completed / total_rows_scanned = 6 / failed_sources = [] / abnormal_results = 4`

## 2026-04-10 固定规则默认命名与唯一校验文案说明
- `/fixed-rules` 的 `规则名称` 现在会自动生成默认值：
  - 比较类：`sheet-目标列-规则选择名称+值`
  - 非比较类：`sheet-目标列-规则选择名称`
- 默认名称仅在用户未手动改名时自动同步；如果用户主动修改或清空规则名称，后续字段变化不再覆盖，且空名称不能保存。
- `unique` 的所有用户可见文案已统一改为 `唯一校验`。
- 本轮回归结果：
  - `python -m pytest backend/tests -q`：`29 passed`
  - `cd frontend && npm run build`：通过
  - `http://127.0.0.1:5173/fixed-rules`：`200`

## 2026-04-10 固定规则“规则选择”弹窗扩展说明
- `/fixed-rules` 规则弹窗中的 `比较符` 已改名为 `规则选择`。
- 下拉选项当前固定为：
  - `等于 (=)`
  - `不等于 (!=)`
  - `大于 (>)`
  - `小于 (<)`
  - `非空校验`
  - `唯一校验`
- 当前仅比较类规则显示 `比较值`；选择 `非空校验` 或 `唯一校验` 时，表单会隐藏 `比较值` 并在保存前清理残留值。
- 固定规则前端状态已兼容 `rule_type`：
  - `fixed_value_compare`
  - `not_null`
  - `unique`
- 固定规则页摘要文案和规则列表已同步改为泛化规则表达，不再把全部规则都渲染为“比较规则”。
- 本轮回归结果：
  - `python -m pytest backend/tests -q`：`29 passed`
  - `cd frontend && npm run build`：通过
  - `http://127.0.0.1:5173/fixed-rules`：`200`

## 2026-04-09 固定规则模块 SVN 联调修复说明
- `/fixed-rules` 页面无需新增配置表单，继续复用现有 `SVN 更新` 按钮和结果区。
- 后端已经补齐 Windows 下的 `svn.exe` 自动探测逻辑；当 shell 的 `PATH` 配错时，仍可自动命中 TortoiseSVN 安装路径。
- 本机当前实测 `SVN 更新` 已通过：
  - `updated_paths = 1`
  - `used_executable = C:\Program Files\TortoiseSVN\bin\svn.exe`
  - `output = Updating '.' / At revision 449960.`
- 本轮回归结果：
  - `python -m pytest backend/tests -q`：`26 passed`
  - `cd frontend && npm run build`：通过
  - `http://127.0.0.1:5173/fixed-rules`：`200`

## 2026-04-08 固定规则模块规则级文件绑定说明
- `/fixed-rules` 页面已从“全局单文件配置”升级为“每条规则独立绑定文件路径、Sheet 和目标列”的固定规则工作区。
- 页面布局改为上下结构：
  - 上方是规则组搜索与横向分组导航
  - 下方是当前规则组的规则配置列表、规则弹窗与结果看板
- 顶部固定显示 `保存配置`、`SVN 更新`、`执行全部规则` 三个操作按钮。
- `SVN 更新` 不再依赖开关，点击后会汇总当前所有已配置规则的固定路径，并按父目录去重后统一更新。
- 固定规则配置结构已升级为 `version = 2`，规则本身通过 `binding.file_path / binding.sheet / binding.column` 维护自己的文件绑定。
- 当前回归结果：
  - `python -m pytest backend/tests -q`：`21 passed`
  - `cd frontend && npm run build`：通过
  - `http://127.0.0.1:5173/fixed-rules`：`200`
  - qa88 验收样例：`items.xls -> items -> INT_ID > 0 -> abnormal_results = 0`

## 2026-04-08 固定规则模块说明
- 新增独立路由 `/fixed-rules`，作为“固定 Excel 文件 + 固定列 + 规则组”的长期复用校验页。
- 固定规则页采用双栏企业后台布局：
  - 左侧规则组搜索、规则组列表与规则数量徽标
  - 右侧固定文件配置、当前组规则列表、分页与结果看板
- 固定规则支持：
  - 自动读取已保存配置
  - 默认组 `未分组`
  - 自定义规则组新增、改名、删除
  - 单列常量比较规则 `eq / ne / gt / lt`
- 固定规则后端接口：
  - `GET /api/v1/fixed-rules/config`
  - `PUT /api/v1/fixed-rules/config`
  - `POST /api/v1/fixed-rules/svn-update`
  - `POST /api/v1/fixed-rules/execute`
- 当前回归结果：
  - `python -m pytest backend/tests -q`：`18 passed`
  - `cd frontend && npm run build`：通过
  - qa88 固定规则验收样例：`items.xls -> items -> INT_ID > 0 -> abnormal_results = 0`

## 2026-04-07 步骤 3 静态规则工作区收口说明
- 步骤 3 当前只保留静态规则模板和静态规则配置区，不再展示动态规则配置侧栏。
- 页面已移除 `新增动态规则` 按钮、`rule_type` 输入框、`params(JSON)` 编辑器和相关说明文案。
- 执行请求现在只提交静态规则；即使内存里残留动态规则，也不会进入最终执行。
- 本次回归结果：
  - `python -m pytest backend/tests -q`：`12 passed`
  - `cd frontend && npm run build`：通过
  - `GET http://127.0.0.1:8000/health`：返回 `200`
  - `GET http://127.0.0.1:5173`：返回 `200`
  - 最小样例链路保持：`Execution Completed / total_rows_scanned = 8 / failed_sources = [] / abnormal_results = 4`

## 2026-04-07 组合变量对话框按钮位置调整说明
- “添加组合变量”对话框现在会先显示可编辑表单区，再显示 `取消 / 保存变量` 操作区，最后显示 JSON 预览区。
- 这样在录入关联列、key 列和变量标签后，可以先直接完成保存，再决定是否继续查看下方 JSON 预览。
- “添加单个变量”对话框保持原样，本次只调整组合变量对话框。

文档更新时间：2026-04-07 11:22

## 2026-04-07 步骤 2 变量编辑对话框说明
- 步骤 2 主区域现在只保留 `变量列表` 和 `当前变量池`。
- 点击 `添加单个变量` 会打开独立的单个变量对话框。
- 点击 `添加组合变量` 会打开独立的组合变量对话框。
- 编辑已有变量时，也会按类型复用对应对话框。
- 点击 `保存变量` 后，会关闭当前对话框并返回变量列表。
- 点击 `取消` 后，会关闭当前对话框且不保留未保存内容。
- 本次回归结果：
  - `python -m pytest backend/tests -q`：`12 passed`
  - `cd frontend && npm run build`：通过
  - 最小样例链路保持：`Execution Completed / total_rows_scanned = 8 / failed_sources = [] / abnormal_results = 4`

文档更新时间：2026-04-07 10:11

## 2026-04-07 步骤 2 子页签行为收口说明

- 步骤 2 继续保留按钮入口，不改为固定三页签常驻展示。
- 点击 `添加单个变量` 或 `添加组合变量` 后，会在步骤 2 内打开对应的独立子页签。
- 单个变量与组合变量现在拥有彼此隔离的表单状态、元数据加载状态和错误提示。
- 点击“保存变量”后，会关闭当前子页签，并自动回到 `变量列表`。
- 点击“取消”后，也会关闭当前子页签，并回到 `变量列表`。
- 编辑已有变量时，会复用对应类型的子页签，而不是切到共用编辑区。
- 本次回归结果：
  - `python -m pytest backend/tests -q`：`12 passed`
  - `cd frontend && npm run build`：通过
  - 最小样例链路保持：`Execution Completed / total_rows_scanned = 8 / failed_sources = [] / abnormal_results = 4`

## 子项目简介

`frontend` 是 Excel Check 的前端工作台子项目，使用 `Vue 3 + TypeScript + Vite + Pinia + Element Plus` 实现 `MainBoard` 单页工作台。

当前这版前端主要承担三件事：

- 维护 `TaskTree` 的前端状态
- 通过四步工作台组织数据源、变量、规则和结果
- 调用现有 FastAPI 后端完成执行与结果展示
- 以更贴近企业校验后台的工作台样式承载完整本地联调流程

## 当前已实现内容

- `MainBoard` 四步工作台页面
- `/fixed-rules` 固定规则检查页面
- `Pinia` 状态管理
- `Vue Router` 双入口：
  - `/`
  - `/fixed-rules`
- `Element Plus` 组件接入与主题化样式
- 主工作台步骤 3 规则组编排（与 `/fixed-rules` 同构交互，状态隔离）：
  - `fixed_value_compare`、`not_null`、`unique`、`composite_condition_check`
- 引擎仍支持 `cross_table_mapping`；主工作台 UI 不再提供跨表映射配置入口
- 固定规则模块：
  - 固定规则页自己的数据源接入管理与变量池构建
  - `version = 4` 配置结构与旧版 `version = 3` 规则级绑定自动迁移
  - 顶部规则组导航与计数
  - 规则 CRUD 与单变量选规
  - `规则选择` 弹窗与比较 / 非空 / 唯一三类固定规则
  - 聚合执行结果看板
- 调用 `/api/v1/sources/capabilities`
- 调用 `/api/v1/sources/metadata`
- 调用 `/api/v1/sources/column-preview`
- 调用 `/api/v1/engine/execute`（编排规则经 `orchestrationRulesToValidationRules` 映射）
- 调用 `/api/v1/fixed-rules/config`
- 调用 `/api/v1/fixed-rules/svn-update`
- 调用 `/api/v1/fixed-rules/execute`
- Vite 开发代理转发到 `http://127.0.0.1:8000`
- 一键“填充联调示例”入口
- 模块 1 的变量池页签化工作流：
  - `添加单个变量` 子页签
  - `添加组合变量` 子页签
  - Excel 数据源的 Sheet / 列名下拉提取
  - 自动变量标签生成
  - 变量详情弹窗与可滚动列预览
- 白底紧凑工作台风格 UI：
  - 顶部工具头部
  - 四步分区白底面板
  - 橙蓝主色动作体系
  - 结果看板概览条与异常表格

## 按页面模块推进的建议

如果你后续希望按网页显示结构分模块开发，建议采用下面这 4 个页面模块：

1. 数据源读取和变量池
2. 正则校验
3. 动态规则检查和看板
4. 静态规则检查和看板

建议把“页面模块划分”和“实际开发顺序”分开管理：

- 页面模块按上面 4 个组织。
- 实际开发顺序推荐 `模块 1 -> 模块 4 -> 模块 2 -> 模块 3`。
- `工程基线` 可作为跨模块准备项单独插入，不算页面模块之一。

各模块建议职责如下：

- 模块 1：负责 source 和 variable 底座，不掺入规则结果逻辑。
- 模块 4：优先做成第一条静态规则闭环，继续复用统一结果看板。
- 模块 2：把 `regex` 当成新增规则类型，而不是单独起一套执行系统。
- 模块 3：先做 JSON 校验、未注册规则报错和已注册规则执行，不一开始追求任意规则全支持。

前端层面的约束建议保持不变：

- 保持单一 `MainBoard` 工作台，不拆成 4 个独立前端应用。
- 保持共享 `Pinia` 状态中心，不复制多套规则状态。
- 保持共享结果看板，不为静态规则、正则规则和动态规则各做一套结果页。

## 模块 1 当前落地状态

- 当前已把变量池从手工输入 `sheet` / `column` 升级为元数据驱动流程。
- 变量构建现在通过“来源数据 -> Sheet -> 列名”逐级选择完成。
- 变量标签默认按 `[sourceId-sheet-column]` 自动生成；若用户手工修改，不再自动覆盖。
- 新增变量时，`期望类型` 默认选中 `字符串(str)`。
- 变量保存后会进入配置区下方的变量池，但不会自动打开详情窗口。
- 点击变量按钮或变量列表里的“查看详情”，会在当前工作台内打开大尺寸只读详情弹窗。
- 变量详情弹窗展示来源数据、Sheet、列名、期望类型和当前已加载的列预览，预览表格支持滚动查看。
- 模块 1 当前只支持 Excel 数据源的变量池下拉提取；CSV 仍可参与执行主流程，但暂不支持同样的下拉提取体验。

## 目录说明

```text
frontend
├── src
│   ├── api
│   ├── components
│   │   └── workbench
│   ├── router
│   ├── store
│   ├── types
│   ├── utils
│   └── views
├── package.json
└── vite.config.ts
```

## 本地开发

安装依赖：

```powershell
cd frontend
npm install
```

启动开发环境：

```powershell
npm run dev -- --host 127.0.0.1 --port 5173
```

构建生产包：

```powershell
npm run build
```

## 联调说明

- 默认开发地址：`http://127.0.0.1:5173`
- 默认代理后端：`http://127.0.0.1:8000`
- 联调前需要先启动根目录下的 FastAPI 后端

推荐最小联调样例：

- source：`src_demo`
- path：`D:/project/excel-check/backend/tests/data/minimal_rules.xlsx`
- variables：
  - `[items-id]`
  - `[drops-ref]`
- rules：
  - `not_null`
  - `unique`
  - `cross_table_mapping`

### 如何完成一次完整校验流程

1. 在项目根目录启动后端：

```powershell
python backend/run.py
```

2. 在 `frontend` 目录启动前端：

```powershell
npm run dev -- --host 127.0.0.1 --port 5173
```

3. 打开 `http://127.0.0.1:5173`
4. 点击首页右上角 `填充联调示例`
5. 点击 `立即执行校验`
6. 结果看板应展示：
   - 扫描总行数 `8`
   - 失败数据源 `0`
   - 异常结果 `4` 条
   - 命中类型：`2 not_null + 2 unique + 1 cross_table_mapping`

### 默认访问地址

- 前端工作台：`http://127.0.0.1:5173`
- 固定规则页面：`http://127.0.0.1:5173/fixed-rules`
- 后端健康检查：`http://127.0.0.1:8000/health`
- 后端文档：`http://127.0.0.1:8000/docs`

### 固定规则模块验收路径

1. 启动后端：

```powershell
python backend/run.py
```

2. 启动前端：

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

3. 打开 `http://127.0.0.1:5173/fixed-rules`
4. 确认顶部可见固定的 `SVN 更新` 与 `执行全部规则` 按钮
5. 新建规则组 `基础校验`
6. 新建规则 `INT_ID 必须大于 0`
7. 在规则弹窗中填写：
   - 文件路径：`D:\projact_samo\GameDatas\datas_qa88\items.xls`
   - Sheet：`items`
   - 目标列：`INT_ID`
   - 规则选择：`大于 (>)`
   - 比较值：`0`
8. 如需验证扩展后的弹窗能力，可继续新增：
   - `INT_ID 不能为空`，规则选择：`非空校验`
   - `INT_ID 唯一校验`，规则选择：`唯一校验`
9. 点击“SVN 更新”
10. 确认结果区返回：
   - `updated_paths = 1`
   - `used_executable = C:\Program Files\TortoiseSVN\bin\svn.exe`
11. 点击“执行全部规则”

当前实测结果：
- `Execution Completed`
- `total_rows_scanned = 3917`
- `failed_sources = []`
- `abnormal_results = 0`
- 若使用最小临时样例同时验证 `大于 / 非空 / 唯一` 三类固定规则，当前实测结果为：
  - `Execution Completed`
  - `total_rows_scanned = 3`
  - `failed_sources = []`
  - `abnormal_results = 3`

## 当前未完成项

- CSV 数据源的变量池下拉提取
- 固定规则模块的多配置集切换
- 固定规则结果导出
- 真实拖拽式变量编排
- 报告导出
- 结果筛选与高级搜索
- 登录和权限
- 飞书 / SVN 的完整前端操作流

## 2026-04-03 交互补充说明

- 新增数据源时，必须先填写`数据源标识`，再点击`选择文件`
- 当`数据源标识`为空时，`选择文件`按钮会保持禁用
- 只有在标识已填写后，前端才会调用`POST /api/v1/sources/local-pick`
- 选择本地文件成功后，真实本地绝对路径会写回输入框，再点击`保存数据源`即可继续后续流程

## 2026-04-03 变量详情弹窗修复说明

- 变量详情弹窗现在会优先请求当前列的完整预览数据，而不是只取少量预览。
- 弹窗中新增“当前来源文件”区域，可直接查看本次预览对应的真实本地路径。
- 当预览结果为 `0 / 0` 时，界面会提示用户优先检查来源文件、Sheet 和列名是否选对。
- 预览表格继续保留固定高度和滚动容器，像 `items.xls -> items -> DESC` 这类 3000+ 行预览会在弹窗内滚动展示。
- 当前验证结果：
  - `items.xls -> items -> DESC` 返回 `3849 / 3849`
  - `items_ext.xls -> items -> DESC` 返回 `0 / 0`

## 2026-04-03 步骤 2 布局调整说明

- 步骤 2 的变量池已从桌面端右侧调整到“配置变量与后端字段映射”区域下方。
- 当前改动只涉及步骤 2 的布局样式和局部说明文案，不影响步骤 1、3、4 以及任何后端接口。
- 变量标签仍可直接点击查看详情，详情弹窗和规则编排用法保持不变。

## 2026-04-03 组合变量说明

### 步骤 2 当前工作区入口
- `变量列表`
- `添加单个变量`
- `添加组合变量`

### 添加单个变量
- 保留原有来源数据、Sheet、列名、变量标签、期望类型流程。
- 当前三类静态规则仍然只消费这类单个变量。

### 添加组合变量
- 只支持同一个数据源、同一个 Sheet 的多列组合。
- 至少选择 2 列，并从已选列中指定 1 列作为 `key 列`。
- `期望类型` 固定为 `json`，页面只读显示。
- 页面会实时请求 `/api/v1/sources/composite-preview`，生成 JSON 字典预览：
  - 外层 key：来自 `key 列`
  - 内层对象：保留其余关联列，不包含 `key 列` 本身

### 变量池与详情弹窗
- 组合变量保存后也会进入同一个变量池。
- 变量池和变量列表会额外显示“组合变量 / JSON”标识，方便和单个变量区分。
- 详情弹窗会根据变量类型切换展示：
  - 单个变量：列预览
  - 组合变量：格式化 JSON 预览
## 2026-04-13 首页 UI 收口

- 主工作台首页 `/` 已完成一轮只涉及表现层的 UI 收口，未改 DOM 结构、布局骨架、类名、ID、事件与业务逻辑。
- 本轮主要调整：
  - 共享头部与首页品牌区视觉统一
  - 概览指标卡图标与状态色统一
  - 流程引导条与步骤卡层级更清晰
  - 首页可见文案改为更短、更偏操作导向的表达
- 图标语义现已统一为：
  - 数据源：`FolderOpened`
  - 变量：`CollectionTag`
  - 规则：`SetUp`
  - 异常结果：`TrendCharts`

### 验证

- `npm run build`：通过
- 首页地址：[http://127.0.0.1:5173](http://127.0.0.1:5173)
- 固定规则页地址：[http://127.0.0.1:5173/fixed-rules](http://127.0.0.1:5173/fixed-rules)

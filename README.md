# Excel Check

文档更新时间：2026-04-11 13:06

## 2026-04-11 固定规则页失效路径容错说明
### 本次调整内容
- 修复了 `/api/v1/fixed-rules/config` 在读取已保存固定规则配置时，因为本地数据源路径失效而直接返回 `500 Internal Server Error` 的问题。
- 固定规则配置读取现在会区分：
  - 结构性非法配置：继续严格失败
  - 运行时可修复问题：降级返回 `200 + meta.config_issues`
- 当前已覆盖的非阻断问题包括：
  - 本地 Excel 路径失效
  - 变量引用的 Sheet 不存在
  - 变量引用的列不存在
- 固定规则页前端现在会在页面顶部展示明确中文 warning，并在数据源接入管理列表里把对应数据源标成 `路径失效`，方便直接修复。
- 固定规则页在存在阻断性配置问题时会禁用执行入口，避免继续点击后再撞接口错误。
- `PUT /api/v1/fixed-rules/config` 与 `POST /api/v1/fixed-rules/execute` 继续保持严格校验；如果路径未修复，仍会返回明确中文 `400`。
- 顺手修正了当前固定规则 runtime 配置里残留的历史乱码分组名称，避免页面恢复后继续回显脏数据。

### 本次回归结果
- `python -m pytest backend/tests -q`：`33 passed`
- `cd frontend && npm run build`：通过
- 运行中的本地服务验证：
  - `http://127.0.0.1:8000/health`：`200`
  - `http://127.0.0.1:5173/fixed-rules`：`200`
- 失效路径专项回归：
  - `GET /api/v1/fixed-rules/config`：`200`，并返回 `meta.config_issues`
  - `PUT /api/v1/fixed-rules/config`：`400`
  - `POST /api/v1/fixed-rules/execute`：`400`

## 2026-04-11 变量池面板乱码修复说明
### 本次调整内容
- 修复了复用组件 `frontend/src/components/workbench/VariablePoolPanel.vue` 中残留的 `????` 占位文案。
- 恢复了主工作台 `/` 与固定规则页 `/fixed-rules` 共用变量池模块里的中文界面文案，包括：
  - 顶部按钮
  - 表格表头与操作按钮
  - 单变量弹窗
  - 组合变量弹窗
  - JSON 预览区
  - 变量详情弹窗
- 顺手修复了同文件里残留的一处 `Sheet` 选择占位乱码。
- 本次只修复前端显示文案，不改接口、状态模型和持久化结构。

### 本次回归结果
- `cd frontend && npm run build`：通过
- 运行中的本地服务验证：
  - `http://127.0.0.1:8000/health`：`200`
  - `http://127.0.0.1:5173`：`200`
  - `http://127.0.0.1:5173/fixed-rules`：`200`

## 2026-04-10 固定规则页独立持久化能力说明
### 本次调整内容
- `/fixed-rules` 已在规则组导航上方新增两个独立模块：
  - `数据源接入管理`
  - `变量池构建`
- 这两个模块复用了工作台现有 UI 与元数据读取能力，但底层状态不再使用工作台缓存，而是走固定规则页自己的 `useFixedRulesStore()`。
- 固定规则配置结构已升级为 `version = 4`，当前统一持久化：
  - `sources`
  - `variables`
  - `groups`
  - `rules`
- 固定规则页新增的数据源、单变量、组合变量和规则都会保存到 `backend/.runtime/fixed-rules/default.json`，刷新页面后仍会自动回填。
- `/fixed-rules` 与主工作台 `/` 的数据源和变量池已完全隔离：
  - 固定规则页新增的数据源、变量不会出现在主工作台
  - 主工作台缓存中的数据源、变量也不会出现在固定规则页
- 固定规则弹窗已移除：
  - `规则文件路径`
  - `读取结构`
  - `Sheet`
  - `目标列`
- 固定规则弹窗改为直接从固定规则页自己的变量池选择 `目标变量`，当前仅允许绑定单变量；组合变量继续支持持久化、编辑和预览，但不进入当前固定规则执行链路。
- 固定规则绑定模型已从旧版 `binding.file_path / binding.sheet / binding.column` 收口为 `target_variable_tag`；后端读取旧版 `version = 3` 配置时会自动迁移为当前 `version = 4` 结构。
- 固定规则页删除数据源时，会级联删除其变量与绑定规则；删除变量时，也会自动清理依赖该变量的规则。

### 本次回归结果
- `python -m pytest backend/tests -q`：`30 passed`
- `cd frontend && npm run build`：通过
- 运行中的本地服务验证：
  - `http://127.0.0.1:8000/health`：`200`
  - `http://127.0.0.1:5173`：`200`
  - `http://127.0.0.1:5173/fixed-rules`：`200`
- 固定规则页真实联调样例：
  - 持久化配置：`1` 个数据源、`3` 个变量（含 `1` 个组合变量）、`3` 条规则
  - 执行结果：`Execution Completed / total_rows_scanned = 6 / failed_sources = [] / abnormal_results = 4`
- 主工作台最小链路保持不变：
  - `POST /api/v1/engine/execute`
  - 返回：`Execution Completed / total_rows_scanned = 8 / failed_sources = [] / abnormal_results = 5`

## 2026-04-10 固定规则默认命名与唯一校验文案说明
### 本次调整内容
- `/fixed-rules` 规则弹窗的 `规则名称` 现在会按当前表单自动生成默认值：
  - 比较类：`sheet-目标列-规则选择名称+值`
  - 非比较类：`sheet-目标列-规则选择名称`
- 默认规则名会在“用户未手动改名”时自动同步；如果用户手动修改或主动清空规则名称，后续字段变化不再自动覆盖，且空规则名不能保存。
- `unique` 的用户可见文案本轮统一收口为 `唯一校验`，不再显示此前的旧命名。

### 本次回归结果
- `python -m pytest backend/tests -q`：`29 passed`
- `cd frontend && npm run build`：通过
- 运行中的本地服务验证：
  - `http://127.0.0.1:8000/health`：`200`
  - `http://127.0.0.1:5173`：`200`
  - `http://127.0.0.1:5173/fixed-rules`：`200`
- 固定规则与主工作台联调链路保持不变：
  - `/fixed-rules`：`Execution Completed / total_rows_scanned = 3 / failed_sources = [] / abnormal_results = 3`
  - `/api/v1/engine/execute`：`Execution Completed / total_rows_scanned = 8 / failed_sources = [] / abnormal_results = 5`

## 2026-04-10 固定规则弹窗“规则选择”扩展说明
### 本次调整内容
- `/fixed-rules` 的“新增固定规则”弹窗已将字段名从 `比较符` 调整为 `规则选择`。
- 固定规则下拉当前固定为 6 项：
  - `等于 (=)`
  - `不等于 (!=)`
  - `大于 (>)`
  - `小于 (<)`
  - `非空校验`
  - `唯一校验`
- 当选择 `非空校验` 或 `唯一校验` 时，弹窗会隐藏 `比较值`，保存时也不会再保留历史比较值。
- 固定规则配置结构已从 `version = 2` 升级为 `version = 3`，每条规则新增 `rule_type`，后端会在读取旧版比较型配置时自动迁移为 `fixed_value_compare`。
- 固定规则执行编排当前支持三类 `rule_type`：
  - `fixed_value_compare`
  - `not_null`
  - `unique`
- `/fixed-rules` 的执行结果会继续复用统一结果协议；其中 `not_null` 维持 `error` 语义，`unique` 维持 `warning` 语义。

### 本次回归结果
- `python -m pytest backend/tests -q`：`29 passed`
- `cd frontend && npm run build`：通过
- 本地服务已按最新代码重启并保持运行：
  - `http://127.0.0.1:8000/health`：`200`
  - `http://127.0.0.1:5173`：`200`
  - `http://127.0.0.1:5173/fixed-rules`：`200`
- 固定规则模块最小联调已实测通过：
  - 规则：`INT_ID > 0`、`INT_ID 非空`、`INT_ID 唯一校验`
  - 返回：`Execution Completed / total_rows_scanned = 3 / failed_sources = [] / abnormal_results = 3`
- 主工作台最小链路再次回归：
  - `POST /api/v1/engine/execute`
  - 返回：`Execution Completed / total_rows_scanned = 8 / failed_sources = [] / abnormal_results = 5`

## 2026-04-09 固定规则模块 SVN 自动探测修复说明
### 本次调整内容
- 修复固定规则模块的 `svn.exe` 发现逻辑，不再只依赖当前 shell 的 `PATH`。
- 后端现在会按以下顺序解析 SVN CLI：
  - 显式配置的 `svn_executable`
  - `PATH` 中的 `svn`
  - Windows 下常见的 TortoiseSVN 安装路径与注册表信息
- `backend/config.py` 现在支持通过环境变量 `SVN_EXECUTABLE` 覆盖默认命令；未设置时仍回退到 `svn`。
- `/api/v1/fixed-rules/svn-update` 的接口形状保持不变，固定规则页继续复用现有 `SVN 更新` 按钮和结果区。

### 本次回归结果
- `python -m pytest backend/tests -q`：`26 passed`
- `cd frontend && npm run build`：通过
- 本地服务已按最新代码重启并保持运行：
  - `http://127.0.0.1:8000/health`：`200`
  - `http://127.0.0.1:5173`：`200`
  - `http://127.0.0.1:5173/fixed-rules`：`200`
- 运行中的固定规则 `SVN 更新` 已验证通过：
  - 工作副本：`D:\projact_samo\GameDatas\datas_qa88`
  - 返回：`updated_paths = 1`
  - `used_executable = C:\Program Files\TortoiseSVN\bin\svn.exe`
  - 最新输出：`At revision 449960.`
- 运行中的固定规则执行保持正常：
  - `items.xls -> items -> INT_ID > 0`
  - `Execution Completed / total_rows_scanned = 3917 / failed_sources = [] / abnormal_results = 0`
- 主工作台最小链路已回归：
  - `POST /api/v1/engine/execute`
  - `Execution Completed / total_rows_scanned = 8 / failed_sources = [] / abnormal_results = 5`

## 2026-04-08 固定规则模块规则级文件绑定说明
### 本次调整内容
- 固定规则模块从“全局单文件配置”升级为“每条规则独立绑定文件路径、Sheet 和目标列”的模型，固定规则页面不再维护单独的全局固定文件配置卡。
- `/fixed-rules` 页面改为上下结构：上方是规则组搜索与横向分组导航，下方是当前规则组的规则配置区与结果看板，保留“一键执行全部规则”。
- `SVN 更新` 按钮改为页面固定按钮，不再依赖开关；点击后会汇总当前所有已保存规则的固定路径，并按父目录去重后统一执行更新。
- 固定规则配置继续持久化到 `backend/.runtime/fixed-rules/default.json`，但配置结构已升级为 `version = 2`，每条规则使用 `binding.file_path / binding.sheet / binding.column` 保存自己的文件绑定。
- 后端新增旧配置自动迁移逻辑：若检测到旧版顶层 `file_path / sheet / columns` 结构，会在读取时自动迁移到新版规则级绑定，不要求手工清空旧配置。
- 固定规则执行改为按规则聚合数据源：数据源按 `(file_path, sheet)` 去重，变量按 `(source, column)` 去重；`POST /api/v1/engine/execute`、`TaskTree -> sources / variables / rules` 和统一结果结构保持不变。

### 本次回归结果
- `python -m pytest backend/tests -q`：`21 passed`
- `cd frontend && npm run build`：通过
- 本地服务已按最新代码重新启动：
  - `http://127.0.0.1:8000/health`：`200`
  - `http://127.0.0.1:5173`：`200`
  - `http://127.0.0.1:5173/fixed-rules`：`200`
- 固定规则验收样例：
  - `D:\projact_samo\GameDatas\datas_qa88\items.xls -> items -> INT_ID > 0`
  - 返回 `Execution Completed / total_rows_scanned = 3917 / failed_sources = [] / abnormal_results = 0`
- 固定规则反向压测样例：
  - `D:\projact_samo\GameDatas\datas_qa88\items.xls -> items -> INT_ID > 10000`
  - 返回 `Execution Completed / total_rows_scanned = 3917 / failed_sources = [] / abnormal_results = 770`
- 旧工作台最小链路保持不回归：
  - `POST /api/v1/engine/execute`
  - 返回 `Execution Completed / total_rows_scanned = 8 / failed_sources = [] / abnormal_results = 5`
- 在 2026-04-08 这一轮回归时，当前环境仍未检测到 `svn` CLI，因此当时固定规则页点击 `SVN 更新` 时会返回明确提示。

## 2026-04-08 固定规则模块收口说明
### 本次调整内容
- 新增独立路由 `/fixed-rules`，用于维护“固定 Excel 文件 + 固定 Sheet + 固定列 + 规则组”的长期复用校验配置。
- 新增固定规则后端接口：
  - `GET /api/v1/fixed-rules/config`
  - `PUT /api/v1/fixed-rules/config`
  - `POST /api/v1/fixed-rules/svn-update`
  - `POST /api/v1/fixed-rules/execute`
- 固定规则配置会持久化到 `backend/.runtime/fixed-rules/default.json`；后续重新打开页面会自动回填已保存的文件路径、Sheet、固定列、规则组与规则。
- 固定规则模块新增 `fixed_value_compare` 规则能力，当前支持单列对常量值的 `eq / ne / gt / lt` 比较。
- 固定规则页面已收口为企业后台式双栏工作区：左侧规则组导航与数量徽标，右侧文件配置、当前组规则列表、分页与结果看板。
- 在 2026-04-08 这一轮收口时，当前环境尚未检测到 `svn` CLI，因此当时的 `SVN 更新` 仍以明确提示为主。

### 本次回归结果
- `python -m pytest backend/tests -q`：`18 passed`
- `cd frontend && npm run build`：通过
- 固定规则验收样例：
  - `D:\projact_samo\GameDatas\datas_qa88\items.xls -> items -> INT_ID > 0`
  - 返回 `Execution Completed / total_rows_scanned = 3917 / failed_sources = [] / abnormal_results = 0`
- 固定规则反向压测样例：
  - `D:\projact_samo\GameDatas\datas_qa88\items.xls -> items -> INT_ID > 10000`
  - 返回 `Execution Completed / total_rows_scanned = 3917 / failed_sources = [] / abnormal_results = 770`
- 当时在 `svn_enabled = true` 且当前环境缺少 CLI 的情况下，`SVN 更新` 会返回：
  - `当前环境未检测到 svn 命令，请先安装 SVN CLI，或在后端配置中指定 svn 可执行文件路径。`

## 2026-04-07 步骤 3 静态规则工作区收口说明
### 本次调整内容
- 步骤 3 现在收口为纯静态规则工作区，只保留界面上的静态规则模板和静态规则配置区。
- 页面不再展示动态规则配置侧栏、`新增动态规则` 按钮、`rule_type` 输入框和 `params(JSON)` 编辑器。
- 为避免隐藏配置继续生效，前端执行时现在只会提交静态规则；当前内存里的动态规则不会进入最终 `TaskTree.rules`。

### 本次回归结果
- `python -m pytest backend/tests -q`：`12 passed`
- `cd frontend && npm run build`：通过
- 运行中的本地服务验证：
  - `GET http://127.0.0.1:8000/health`：返回 `200`
  - `GET http://127.0.0.1:5173`：返回 `200`
- 最小联调结果保持不变：`Execution Completed / total_rows_scanned = 8 / failed_sources = [] / abnormal_results = 5`

## 2026-04-07 组合变量对话框按钮位置调整说明
### 本次调整内容
- 步骤 2 的“添加组合变量”对话框现在采用“表单区 -> 取消/保存变量 -> JSON 预览区”的顺序。
- `取消` 与 `保存变量` 按钮已经从 JSON 预览区下方移动到表单区之后，便于先完成配置再查看预览。
- “添加单个变量”对话框保持现状，本次不做同步改动。

### 本次回归结果
- `python -m pytest backend/tests -q`：通过
- `cd frontend && npm run build`：通过
- 最小联调结果保持不变：`Execution Completed / total_rows_scanned = 8 / failed_sources = [] / abnormal_results = 5`

文档更新时间：2026-04-07 11:22

## 2026-04-07 步骤 2 变量编辑对话框说明

### 本次调整内容
- 步骤 2 现在只保留 `变量列表` 和下方 `当前变量池`，不再在主区域内承载变量编辑表单。
- 点击 `添加单个变量` 会打开独立的“单个变量”对话框。
- 点击 `添加组合变量` 会打开独立的“组合变量”对话框。
- 编辑已有变量时，会按变量类型复用对应对话框：
  - 单个变量 -> 单个变量对话框
  - 组合变量 -> 组合变量对话框
- 点击 `保存变量` 后，会关闭当前对应对话框，并回到变量列表；刚保存的变量会继续保持高亮，方便后续规则编排。
- 点击 `取消` 后，会直接关闭当前对话框，不保留未保存内容。

### 本次回归结果
- `python -m pytest backend/tests -q`：`12 passed`
- `cd frontend && npm run build`：通过
- 运行态最小联调结果保持不变：
  - `msg = "Execution Completed"`
  - `total_rows_scanned = 8`
  - `failed_sources = []`
  - `abnormal_results = 5`

文档更新时间：2026-04-07 10:11

## 2026-04-07 步骤 2 子页签行为收口说明

### 本次调整内容
- 步骤 2 继续保留两个按钮入口：
  - `添加单个变量`
  - `添加组合变量`
- 点击按钮后，会在步骤 2 内打开各自独立的子页签，而不是共用同一个编辑区。
- 单个变量和组合变量现在使用各自独立的编辑状态、元数据加载状态和错误提示，不再互相污染。
- 点击“保存变量”后，会关闭当前对应的子页签，并自动回到 `变量列表`。
- 点击“取消”时，也会关闭当前子页签，并回到 `变量列表`。
- 编辑已有变量时，会复用对应类型的子页签：
  - 单个变量 -> `添加单个变量` 子页签
  - 组合变量 -> `添加组合变量` 子页签

### 本次回归结果
- `python -m pytest backend/tests -q`：`12 passed`
- `cd frontend && npm run build`：通过
- 前后端重启后：
  - `http://127.0.0.1:8000/health` 返回 `200`
  - `http://127.0.0.1:5173` 返回 `200`
- 最小样例完整执行链路保持不变：
  - `msg = "Execution Completed"`
  - `total_rows_scanned = 8`
  - `failed_sources = []`
  - `abnormal_results = 5`

## 项目简介
Excel Check 是一个面向配置表校验场景的本地工作台项目，当前采用 `FastAPI + Vue 3 + Pinia + Element Plus` 实现最小可运行版本。

当前版本已经支持：
- 本地 Excel / CSV 数据源接入
- 基于 Excel 元数据的变量池构建
- `not_null`、`unique`、`cross_table_mapping` 三类规则执行
- 固定规则模块的比较 / 非空 / 唯一校验执行
- 结果看板展示
- 前后端本地完整联调

## 当前关键能力

### 后端
- `GET /health`
- `GET /api/v1/sources/capabilities`
- `POST /api/v1/sources/local-pick`
- `POST /api/v1/sources/metadata`
- `POST /api/v1/sources/column-preview`
- `POST /api/v1/engine/execute`
- `GET /api/v1/fixed-rules/config`
- `PUT /api/v1/fixed-rules/config`
- `POST /api/v1/fixed-rules/svn-update`
- `POST /api/v1/fixed-rules/execute`
- 本地 Excel / CSV 按 `source + sheet + column` 精确读取
- 本地 Excel 的 Sheet / 列名结构读取与列预览
- 规则注册表和三类基础规则
- 固定规则模块的 `fixed_value_compare / not_null / unique`
- source 级失败降级

### 前端
- `MainBoard` 四步工作台
- `/fixed-rules` 固定规则检查页
- 数据源、变量、规则、结果的 Pinia 状态管理
- 本机文件选择框接入
- 变量池“添加单个变量 / 添加组合变量”子页签
- Excel 数据源的 Sheet / 列名下拉提取
- 变量详情弹窗与可滚动列预览
- 纯静态规则模板配置区
- 固定规则模块的规则组导航、规则 CRUD、分页与结果看板
- 完整结果看板

### 当前模块进展说明
- 模块 1“数据源读取和变量池”已完成首个元数据驱动切片：
  - 数据源仅展示用户已保存的来源数据
  - 变量构建支持按“来源数据 -> Sheet -> 列名”逐级选择
  - 变量标签默认按 `[sourceId-sheet-column]` 自动生成
  - 新增变量时，期望类型默认选中“字符串(str)”
  - 保存变量后仅回写变量池，不再自动打开变量详情
  - 变量池按钮和列表中的“查看详情”会打开工作台内的只读详情弹窗
- 当前版本的变量池下拉提取仅支持 Excel 数据源。
- CSV 数据源仍可参与主流程执行，但变量池的真实 Sheet / 列名下拉提取尚未开放。
- 固定规则模块已经独立落地：
  - 支持固定规则页自己的数据源接入管理与变量池构建，并持久化到 `version = 4` 配置
  - 支持 `sources / variables / groups / rules` 一体化保存，以及旧版 `version = 3` 规则级绑定自动迁移
  - 支持规则组新增、改名、删除与规则自动迁移到 `未分组`
  - 支持固定规则弹窗直接从固定规则页变量池选择 `目标变量`
  - 支持比较 / 非空 / 唯一三类固定规则，以及组合变量的持久化与预览
  - 支持固定显示的 `SVN 更新` 按钮，统一更新当前固定规则页已保存的数据源路径
  - 当前 Windows 环境可自动探测 TortoiseSVN CLI，并完成真实工作副本更新
  - 当前不扩展到多配置集、CSV、飞书或跨文件关系型固定规则

## 本地文件选择说明
浏览器不能直接拿到真实本地绝对路径，因此当前方案改为：

- 前端点击“选择文件”
- 后端在本机 Windows 环境通过 `tkinter` 弹出系统文件选择框
- 选中文件后直接返回真实本地绝对路径
- 前端把这个真实路径写入数据源输入框

当前**不会**再把文件复制到 `backend/.runtime_uploads` 目录。

## 安装依赖

### 后端
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

说明：
- `backend/requirements.txt` 现在已经显式包含 `openpyxl` 和 `xlrd`。
- 其中 `.xlsx` 读取依赖 `openpyxl`，`.xls` 读取依赖 `xlrd`。
- 若当前 shell 的 `PATH` 没有正确包含 `svn.exe`，固定规则模块会优先尝试自动探测 Windows 下的 TortoiseSVN 安装路径；如需手工覆盖，也可在启动前设置环境变量 `SVN_EXECUTABLE`。

### 前端
```powershell
cd frontend
npm install
```

## 启动命令

### 启动后端
在项目根目录执行：
```powershell
python backend/run.py
```

### 启动前端
```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

## 默认访问地址
- 前端工作台：`http://127.0.0.1:5173`
- 固定规则页面：`http://127.0.0.1:5173/fixed-rules`
- 后端健康检查：`http://127.0.0.1:8000/health`
- 后端文档：`http://127.0.0.1:8000/docs`

## 联调说明

### 最短联调路径
1. 启动后端。
2. 启动前端。
3. 打开 `http://127.0.0.1:5173`。
4. 点击“填充联调示例”。
5. 点击“立即执行校验”。

预期结果：
- `msg = "Execution Completed"`
- `total_rows_scanned = 8`
- `failed_sources = []`
- `abnormal_results = 5`

### 手工完整流程
1. 在步骤 1 点击“新增数据源”。
2. 输入数据源标识，例如 `src_demo`。
3. 选择“本地 Excel”。
4. 点击“选择文件”，在系统文件框中选择：
   `D:\project\excel-check\backend\tests\data\minimal_rules.xlsx`
5. 确认输入框已写入真实本地绝对路径。
6. 点击“保存数据源”。
7. 在步骤 2 点击“添加单个变量”。
8. 在工作台内的“添加单个变量”子页签中依次选择：
   - 来源数据
   - Sheet
   - 列名
   - 期望类型（默认字符串，可切换为 JSON）
9. 确认变量标签自动生成为 `[sourceId-sheet-column]` 后保存变量；保存成功后会自动关闭当前“添加单个变量”子页签，并回到“变量列表”。
10. 点击下方变量池中的变量按钮或变量列表里的“查看详情”，确认变量详情弹窗中的列预览可滚动查看。
11. 在步骤 3 添加：
   - `not_null`
   - `unique`
   - `cross_table_mapping`
12. 点击“立即执行校验”。

预期结果：
- 扫描总行数：`8`
- 失败数据源：`0`
- 异常结果：`5` 条
- 命中分布：`2 not_null + 2 unique + 1 cross_table_mapping`

### 使用 qa88 配置表完成一次真实联调
以下流程已经基于你本机的两个文件验证通过：

- `D:\projact_samo\GameDatas\datas_qa88\IAPConfig.xls`
- `D:\projact_samo\GameDatas\datas_qa88\items.xls`

推荐联调配置如下：

1. 启动后端：
```powershell
python backend/run.py
```

2. 启动前端：
```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

3. 打开前端工作台：`http://127.0.0.1:5173`
4. 在步骤 1 添加两个数据源：
   - `src_iap` -> `D:\projact_samo\GameDatas\datas_qa88\IAPConfig.xls`
   - `src_items` -> `D:\projact_samo\GameDatas\datas_qa88\items.xls`
5. 在步骤 2 添加两个变量：
   - 来源 `src_items`，Sheet 选择 `items`，列名选择 `INT_ID`，期望类型选择 `字符串`，保存为默认标签 `[src_items-items-INT_ID]`
   - 来源 `src_iap`，Sheet 选择 `Template`，列名选择 `INT_ItemId`，期望类型选择 `字符串`，保存为默认标签 `[src_iap-Template-INT_ItemId]`
6. 在步骤 3 添加三条规则：
   - `not_null`，目标变量选择 `[src_items-items-INT_ID]` 和 `[src_iap-Template-INT_ItemId]`
   - `unique`，目标变量选择 `[src_items-items-INT_ID]`
   - `cross_table_mapping`，字典变量选择 `[src_items-items-INT_ID]`，目标变量选择 `[src_iap-Template-INT_ItemId]`
7. 点击“立即执行校验”。

本次真实联调结果：
- 返回：`msg = "Execution Completed"`
- `failed_sources = []`
- `total_rows_scanned = 5410`
- `abnormal_results = 11`
- 主要异常来自 `IAPConfig.xls -> Template -> INT_ItemId` 中若干值为 `0`，未命中 `items.xls -> items -> INT_ID`

### 固定规则模块验收路径
以下流程已经基于当前工作树中的固定规则模块实测通过：

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
4. 确认页面顶部固定显示 `SVN 更新` 与 `执行全部规则` 按钮
5. 新建规则组 `基础校验`
6. 新建规则，并在规则表单中逐项配置：
   - 文件路径：`D:\projact_samo\GameDatas\datas_qa88\items.xls`
   - Sheet：`items`
   - 目标列：`INT_ID`
   - 规则名：`INT_ID 必须大于 0`
   - 规则选择：`大于 (>)`
   - 比较值：`0`
7. 如需验证新的固定规则能力，可继续新增：
   - `INT_ID 非空`，规则选择：`非空校验`
   - `INT_ID 唯一校验`，规则选择：`唯一校验`
8. 点击“SVN 更新”
9. 确认结果区返回：
   - `updated_paths = 1`
   - `used_executable = C:\Program Files\TortoiseSVN\bin\svn.exe`
10. 点击“执行全部规则”

预期结果：
- `msg = "Execution Completed"`
- `total_rows_scanned = 3917`
- `failed_sources = []`
- `abnormal_results = 0`

反向压测可把比较值改为 `10000`，当前实测结果为：
- `msg = "Execution Completed"`
- `total_rows_scanned = 3917`
- `failed_sources = []`
- `abnormal_results = 770`
- 首条异常定位：`items -> INT_ID / row_index = 2 / raw_value = 1`

## 当前联调验证结果
本次已验证：
- `python -m pytest backend/tests -q`
- `cd frontend && npm run build`
- 已实际启动：
  - `python backend/run.py`
  - `cd frontend && npm run dev -- --host 127.0.0.1 --port 5173`
- `GET /health`
- `GET /`（前端首页）
- `GET /api/v1/sources/capabilities`
- `POST /api/v1/sources/metadata`
- `POST /api/v1/sources/column-preview`
- `POST /api/v1/engine/execute`
- `POST /api/v1/fixed-rules/svn-update`
- `POST /api/v1/fixed-rules/execute`
- 使用 `D:\projact_samo\GameDatas\datas_qa88\IAPConfig.xls` 与 `D:\projact_samo\GameDatas\datas_qa88\items.xls` 完成一次真实执行链路验证
- 使用运行中的本地服务再次验证 qa88 配置表链路，结果为：
  - `msg = "Execution Completed"`
  - `failed_sources = []`
  - `total_rows_scanned = 5410`
  - `abnormal_results = 11`
- 使用运行中的固定规则服务验证 `SVN 更新`，结果为：
  - `updated_paths = 1`
  - `used_executable = C:\Program Files\TortoiseSVN\bin\svn.exe`
  - `output = Updating '.' / At revision 449960.`
- 使用固定规则模块再次验证 qa88 单文件链路，结果为：
  - `D:\projact_samo\GameDatas\datas_qa88\items.xls -> items -> INT_ID > 0`
  - `Execution Completed / total_rows_scanned = 3917 / failed_sources = [] / abnormal_results = 0`
- 使用固定规则模块完成反向压测：
  - `D:\projact_samo\GameDatas\datas_qa88\items.xls -> items -> INT_ID > 10000`
  - `Execution Completed / total_rows_scanned = 3917 / failed_sources = [] / abnormal_results = 770`

说明：
- `POST /api/v1/sources/local-pick` 采用本机 `tkinter` 文件对话框，自动化测试通过 monkeypatch 验证返回真实路径与取消选择逻辑。
- 后端本地 Excel 读取现在会按扩展名显式选择引擎：`.xlsx` 使用 `openpyxl`，`.xls` 使用 `xlrd`。
- 如果缺少 `.xls` 读取依赖，接口会直接返回明确中文提示，而不是产生模糊的读取失败。
- 如果前端仍命中旧接口或出现 `404`，通常是后端仍在运行旧进程；先停止旧进程，再重新执行 `python backend/run.py`。
- 当前终端环境未提供浏览器自动化回放能力，本轮没有记录完整的浏览器点击回放；页面可访问性、运行中接口与 qa88 执行链路已经实际验证通过，浏览器手工步骤可直接按上面的联调说明复现。

## 测试命令
```powershell
python -m pytest backend/tests -q
```

```powershell
cd frontend
npm run build
```

## 当前未完成项
- 飞书数据源真实接入
- SVN 作为主工作台 `source` 类型的完整闭环
- CSV 数据源的变量池下拉提取
- 固定规则模块的多配置集切换
- 固定规则结果导出
- `regex` 规则
- 导出报告
- 更丰富的规则体系
- 统一工程化配置与 CI

## 相关文档
- 项目记录：[PROJECT_RECORD.md](D:/project/excel-check/PROJECT_RECORD.md)
- 更新日志：[CHANGELOG.md](D:/project/excel-check/CHANGELOG.md)

## 2026-04-03 交互补充说明

### 新增数据源的正确操作顺序
1. 先输入`数据源标识`
2. 再点击`选择文件`
3. 在系统文件框中选择本地 Excel 或 CSV 文件
4. 确认真实本地绝对路径已写入输入框
5. 最后点击`保存数据源`

### 本次交互修复
- `数据源标识`为空时，`选择文件`按钮会保持禁用
- 前端不会在标识为空时发起`POST /api/v1/sources/local-pick`
- 弹窗会明确提示“请先填写数据源标识，再选择本地文件”
- 选择文件进行中会显示明确的按钮状态，避免误判为页面卡住

## 2026-04-03 组合变量扩展说明

### 步骤 2 现在有 3 个工作区入口
- `变量列表`
- `添加单个变量`
- `添加组合变量`

### 组合变量的当前规则
- 组合变量只允许来自同一个数据源、同一个 Sheet。
- 组合变量至少需要选择 2 列。
- 用户必须从已选列中指定 1 列作为 `key_column`。
- 生成的 JSON 中，外层 key 来自 `key_column` 的每行值。
- 内层对象只保留其余关联列，不包含 key 列本身。

### 当前规则兼容策略
- 组合变量已经正式进入 `TaskTree.variables`。
- 当前 `not_null`、`unique`、`cross_table_mapping` 仍只面向单个变量。
- 步骤 3 的静态规则选择器会自动过滤掉组合变量，避免误配。

### 本轮联调回归结果
- `python -m pytest backend/tests -q`：`12 passed`
- `cd frontend && npm run build`：通过
- 组合变量预览接口：`POST /api/v1/sources/composite-preview` 已验证通过
- 最小样例执行链路保持不变：
  - `msg = "Execution Completed"`
  - `total_rows_scanned = 8`
  - `failed_sources = []`
  - `abnormal_results = 5`

### 当前组合变量使用方式
1. 在步骤 1 先保存一个本地 Excel 数据源。
2. 在步骤 2 点击 `添加组合变量`。
3. 选择同一个数据源和同一个 Sheet。
4. 至少勾选 2 列，并从已选列中指定 1 列作为 `key 列`。
5. 输入变量标签后，可在页签内直接查看 JSON 预览。
6. 保存后，组合变量会进入下方变量池，并显示为 `组合变量 / JSON`。

### 当前能力边界
- 组合变量当前只支持本地 Excel 数据源。
- 组合变量当前只支持“同一数据源 + 同一 Sheet”的多列组合。
- `not_null`、`unique`、`cross_table_mapping` 仍只面向单个变量，规则区会自动过滤组合变量。
- 组合变量已经进入 `TaskTree.variables`，可作为后续 JSON 类规则和动态规则扩展的正式输入。

### 本次联调回归结果
- `python -m pytest backend/tests -q`：通过
- `cd frontend && npm run build`：通过
- `GET http://127.0.0.1:8000/health`：返回`200`
- `GET http://127.0.0.1:5173`：返回`200`
- 使用最小样例执行校验结果：
  - `msg = "Execution Completed"`
  - `total_rows_scanned = 8`
  - `failed_sources = []`
  - `abnormal_results = 5`

## 2026-04-03 变量详情预览修复说明

### 本次修复内容
- 变量详情弹窗不再只取少量预览，而是会尽量读取当前列的完整预览数据。
- 详情弹窗新增“当前来源文件”显示，可直接看到本次预览对应的真实本地路径。

## 2026-04-03 步骤 2 布局调整说明

### 本次调整内容
- 步骤 2 的变量池不再显示在配置区右侧，而是固定移动到“配置变量与后端字段映射”区域下方。
- 本次只调整步骤 2 的前端展示层，不改步骤 1、3、4 的布局，不改任何接口和变量交互逻辑。
- 变量标签池继续支持点击查看详情，变量列表中的“查看详情”入口保持不变。
- 当预览结果为 `0 / 0` 时，页面会明确提示先检查来源文件、Sheet 和列名，而不是只显示空表格。
- 详情表格继续保留滚动容器，完整预览数据较多时可在弹窗内滚动查看。

### qa88 真实文件验证结果
- 运行中的 `POST /api/v1/sources/column-preview` 对以下请求已验证通过：
  - 来源文件：`D:\projact_samo\GameDatas\datas_qa88\items.xls`
  - Sheet：`items`
  - 列名：`DESC`
- 当前真实返回结果：
  - `total_rows = 3849`
  - `loaded_rows = 3849`
  - `source_path = D:\projact_samo\GameDatas\datas_qa88\items.xls`
- 对照验证：
  - `D:\projact_samo\GameDatas\datas_qa88\items_ext.xls -> items -> DESC` 当前真实结果为 `0 / 0`
  - 这类情况代表当前选中的文件本身没有可预览数据，不再误判为前端弹窗损坏

### 本地完整联调结果
- 运行中的 `POST /api/v1/engine/execute` 已再次用 qa88 数据验证通过：
  - `msg = "Execution Completed"`
  - `failed_sources = []`
  - `total_rows_scanned = 5410`
  - `abnormal_results = 11`
- 这里的 `11` 条异常来自真实业务数据，不代表程序失败。

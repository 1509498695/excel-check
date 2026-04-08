# Excel Check

文档更新时间：2026-04-07 20:43

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
- 本地 Excel / CSV 按 `source + sheet + column` 精确读取
- 本地 Excel 的 Sheet / 列名结构读取与列预览
- 规则注册表和三类基础规则
- source 级失败降级

### 前端
- `MainBoard` 四步工作台
- 数据源、变量、规则、结果的 Pinia 状态管理
- 本机文件选择框接入
- 变量池“添加单个变量 / 添加组合变量”子页签
- Excel 数据源的 Sheet / 列名下拉提取
- 变量详情弹窗与可滚动列预览
- 纯静态规则模板配置区
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
npm run dev
```

## 默认访问地址
- 前端工作台：`http://127.0.0.1:5173`
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
npm run dev
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
- 使用 `D:\projact_samo\GameDatas\datas_qa88\IAPConfig.xls` 与 `D:\projact_samo\GameDatas\datas_qa88\items.xls` 完成一次真实执行链路验证
- 使用运行中的本地服务再次验证 qa88 配置表链路，结果为：
  - `msg = "Execution Completed"`
  - `failed_sources = []`
  - `total_rows_scanned = 5410`
  - `abnormal_results = 11`

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
- SVN 同步能力
- CSV 数据源的变量池下拉提取
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

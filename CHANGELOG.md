# 更新日志

文档更新时间：2026-04-03 16:03

## [Unreleased]

### 变更
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

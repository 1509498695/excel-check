# 更新日志

文档更新时间：2026-04-10 16:21

## [Unreleased]

### 变更
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

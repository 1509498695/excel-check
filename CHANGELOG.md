# 更新日志

本日志按 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/) 风格收口，按版本而不是分钟级流水维护。  
分钟级历史日记仍在 [docs/archive/PROJECT_RECORD.md](docs/archive/PROJECT_RECORD.md)，本文件不再追加。

## [Unreleased]

- 修复个人校验 `/` 与项目校验 `/fixed-rules` 在执行校验后首次打开 `多组串行校验` / `多组映射校验` 编辑弹窗时，已配置筛选、判定和映射字段未立即回显的问题。
- 个人校验 `/` 与项目校验 `/fixed-rules` 的 `多组映射校验` 从字段检查模型改为“筛选条件 + 筛选失败排除行号范围”模型：每条筛选独立检查失败行，命中排除范围的数据从异常结果中移除；旧 `field_checks / field / ranges / default_expected_value` 配置废弃，需重新配置筛选后保存。
- 个人校验 `/` 与项目校验 `/fixed-rules` 的 `等于 / 不等于 + 固定值` 场景新增 `规则集` 模式，可用英文逗号配置多个固定值；单变量、组合分支和多组串行校验均按同一语义执行。
- 个人校验 `/` 页右上角新增蓝色 `系统使用说明` 入口；个人设置 `/profile` 的同名入口同步改为主按钮颜色。
- 个人校验 `/` 与项目校验 `/fixed-rules` 的默认规则名称分隔符统一：比较值和 `包含 (in)` 引用变量自动命名改用 `-` 拼接，不再生成 `大于+0` 这类名称。
- 规范重构第一阶段：新增 `docs/STANDARDS.md`、Ruff / ESLint / Prettier 配置、统一检查脚本和前端共享 API 类型，作为后续前后端命名与接口治理基线。
- 个人校验 `/` 与项目校验 `/fixed-rules` 的结果区新增 Excel 导出：按当前 `result_id` 导出全量结果，工作簿包含 `统计摘要` 与 `异常明细` 两个页签，并继续按用户 / 项目隔离权限。
- 数据源类型入口收口：CSV 与飞书仍未完整接入，新增数据源下拉中统一显示为“占位”并禁用选择，历史配置仍可展示和删除。
- 修复项目校验 `/fixed-rules` 添加 SVN Excel 变量后保存配置报错的问题：后端配置规范化现允许本地 Excel 与 SVN Excel 变量来源保持一致。
- 空数据状态视觉优化：增强共享 `EmptyState`，统一数据源、变量池、规则和结果模块的居中图标、主文案与辅助说明展示。
- 全局基础 UI 细节统一：按钮、输入框、表格、状态标签、卡片、空态和操作链接增加最终覆盖层，收口到新版 SaaS 设计系统。
- 个人设置 `/profile` 页面新版 UI 对齐：账号信息、修改密码、我的项目三段模块切到新版 SaaS 设置页风格，密码修改与项目切换逻辑保持不变。
- 管理后台 `/admin` 页面新版 UI 对齐：页面头右侧搜索与新建项目入口、统计卡、项目列表、项目详情和项目成员三段模块切到新版 SaaS 后台风格，项目与成员管理逻辑保持不变。
- 项目校验 `/fixed-rules` 页面新版 UI 对齐：复用个人校验页的页面头、步骤条、统计卡、分段模块、规则区、表格与结果空态样式，修正规则模块序号为 `03`，业务事件与接口保持不变。
- 个人校验 `/` 页面新版 UI 精修：页面头、步骤条、统计卡、四个主模块、规则空态与结果执行区进一步贴近新版 SaaS 参考稿，业务数据流与执行事件保持不变。
- 前端通用 UI 组件体系整理：新增 `AppCard / StatusBadge / PrimaryButton / SecondaryButton / GhostButton / MetricCard`，并将个人校验、项目校验、管理后台、个人设置的页面骨架统一到新版 SaaS 卡片、按钮、表格、状态胶囊与空态风格。
- 浏览器上传 Excel / CSV 的默认落盘目录调整为 `backend/.runtime_uploads/local_excel/<project_id>/<user_id>/`，继续保留项目与用户隔离。
- 个人校验 `/` 与项目校验 `/fixed-rules` 的 `数据源路径管理` 收口为仅管理远端 SVN 目录 URL；本地 Excel / CSV 不再提供本地路径替换管理，历史本地路径配置字段继续保留兼容。
- 本机共享部署升级：新增 `scripts/start-local-deploy.ps1`，支持前端构建后由 FastAPI 单服务托管；后端监听、端口、前端产物目录、CORS、上传大小、JWT 密钥与默认管理员密码均可通过环境变量配置。
- 数据源新增浏览器上传链路：`POST /api/v1/sources/upload` 支持 `.xlsx/.xls/.csv`，按当前项目与用户隔离保存到 `backend/.runtime_uploads/local_excel/`，远程访问用户无需依赖服务器本机 `tkinter` 文件选择框。
- 默认管理员播种策略收口：启动时继续确保唯一默认超级管理员存在，但已有 `admin` 不再被每次启动强制重置密码；首次共享部署建议设置 `DEFAULT_SUPER_ADMIN_PASSWORD`。
- 用户可见命名统一：侧边栏、页面头部、结果面板与稳定文档中的“工作台 / 固定规则”统一更名为“个人校验 / 项目校验”；路由路径与内部实现名保持不变。
- 文档重整：根 `README.md` 收口为 6 节骨架；新建 `docs/ARCHITECTURE.md`、`docs/MODULES.md` 集中沉淀稳定文档；`PROJECT_RECORD.md` 与 `需求文档.md` 归档到 `docs/archive/`。
- 管理后台修复：超级管理员在成员表中调整自己的归属项目后，前端会立即调用现有项目切换接口，同步 JWT 与当前项目上下文，不再停留在旧项目。
- 工作台规则弹窗新增单变量选项 `包含 (in)`；前端以变量池中的单个变量作为基础字典下拉，保存时复用现有 `cross_table_mapping` 执行语义。
- 个人校验 `/` 与项目校验 `/fixed-rules` 单变量规则新增 `顺序校验`：按原始行序校验数值连续性，支持升序 / 降序、步长、自首行自动起始或手动指定起始值。
- 个人校验 `/` 与项目校验 `/fixed-rules` 的“新增规则”弹窗现统一支持 3 类入口：`单一变量校验`、`组合分支校验`、`跨组变量校验`；新规则 `dual_composite_compare` 可按外层 Key 关联两个组合变量，再对多个 Value 字段执行 AND 比较。
- `dual_composite_compare` 新增 `key_check_mode` 与多条字段比较配置：可选“基准变量为准”或“双向检查”，比对项支持 `等于 / 不等于 / 大于 / 小于 / 非空`，异常会明确标出 Key、左右字段和值。
- 规则弹窗交互收口：新增规则时先选择 `单一变量校验 / 组合分支校验 / 跨组变量校验`，再按规则类型过滤目标变量列表；切换规则类型会自动清理不兼容的变量与表单残留值。
- 新增 `multi_composite_pipeline_check`：个人校验 `/` 与项目校验 `/fixed-rules` 的规则弹窗现支持第 4 类入口 `多组串行校验`；规则支持 1..N 个组合变量节点，单节点时退化为“前置过滤 + 最终判定”，多节点时按顺序执行并在首个失败节点短路后续节点。
- 新增 `multi_composite_mapping_check`：个人校验 `/` 与项目校验 `/fixed-rules` 的规则弹窗现支持第 5 类入口 `多组映射校验`；每个组合变量节点可配置目标字段、筛选条件与 Excel 行号闭区间期望值映射，多节点独立执行并汇总全部异常，不影响既有多组串行校验。
- `composite_condition_check` 的展示名统一收口为 `组合分支校验`；其全局筛选与分支筛选新增字符串 `包含`，语义为“字段值包含固定片段”，仅作用于筛选层，不影响单变量 `包含 (in)`、分支校验与跨组变量校验。
- `组合分支校验` 的全局筛选与分支筛选进一步新增字符串 `不包含`，语义为“字段值不包含固定片段”；与 `包含` 一样只支持固定值右侧，不进入分支校验，也不影响单变量 `包含 (in)` 与跨组变量校验。
- 单一变量校验新增 `正则校验`（`regex_check`），可直接输入正则表达式按完整匹配校验整格内容；`组合分支校验` 的分支校验条件同步新增 `正则校验` 断言，用于按字段格式校验命中分支的记录。
- 组合变量弹窗新增 `Key 后追加序号` 复选框；开启后会按原始行序生成 `原值_序号` 的唯一键，并在预览、保存、执行三条链路保持同一口径。
- 组合变量弹窗进一步收口：仅当当前 `Key 列` 存在重复值时才显示 `Key 后追加序号`；编辑历史上已启用该选项的变量时，复选框会继续显示并保持回填。
- 修复项目校验 `/fixed-rules` 中 `组合分支校验` 的保存链路：前端提交前会正确保留筛选操作符 `contains` 的比较值，不再把 `全局筛选 contains + 分支筛选 contains + 分支校验 not_null` 误保存为“缺少比较值”。
- 工作台数据源弹窗修复：`POST /api/v1/sources/local-pick` 改为以独立子进程驱动 `tkinter` 文件选择框，避免在 uvicorn 主进程里残留 Tcl 解释器与窗口焦点资源；用户在选完本地配置表后立即修改「数据源标识」时，整页不再被卡住，连续多次选择文件也不会越用越慢。
- SVN 数据源（HTTP）打通：用户在数据源弹窗里选「SVN（推荐 HTTP 链接）」，输入目录 URL 后弹窗浏览选择 `.xls/.xlsx` 文件即可保存；后端新增 `POST /api/v1/sources/svn-list / svn-credentials / svn-refresh`，凭据按当前登录用户与 host 维度 Fernet 加密落 `<runtime>/svn-credentials.json`，远端 URL 落到 `<runtime>/svn-cache/<host>/<key>/` 后复用统一执行引擎；变量池下拉与 `/api/v1/engine/execute`、`/api/v1/fixed-rules/{execute,svn-update}` 都自动支持 SVN 远端文件，命中默认 60s TTL 时不重复访问 SVN。SVN 业务级鉴权失败用 HTTP 403 表达，避免与登录态过期混淆；远端 host 通过 `settings.svn_url_allowlist`（默认 `samosvn`）做 SSRF 兜底。
- SVN 凭据弹窗支持可配置“测试目录 URL”，并按当前登录用户 + host 维度持久化记忆；`samosvn` 默认回填 `https://samosvn/data/project/samo/GameDatas/`，测试连接会先保存凭据与测试目录，再对该目录执行一次 `svn list`。后端继续把 `forbidden` 归类为权限/鉴权失败，前端会给出更准确的权限提示。
- SVN 凭据弹窗再次打开时，现会按当前登录用户 + host 读取并回填已保存的用户名、密码与测试目录 URL；host 列表接口继续不返回 password，密码仅通过单 host 详情接口回填到当前弹窗，避免浏览器自动填充把密码显示成别的值。
- 页面刷新后，步骤 1 的远端 SVN 数据源现会主动加载当前登录用户已保存的 SVN host 凭据列表；状态列按 `检测中 / 已就绪 / 待授权 / 状态未知` 实时收口，不再因为内存中的凭据列表尚未加载而误报 `待授权`。
- 修复步骤 2 变量弹窗的前端错误拦截：SVN Excel 数据源不再被误判为“仅本地 Excel 可提取字段”，个人校验与项目校验现在都可直接基于 SVN `.xls/.xlsx` 数据源添加单变量和组合变量；CSV 仍继续显示不支持字段映射提取。
- 数据源弹窗交互调整：本地 Excel 与 SVN Excel 现支持“先选文件，再自动回填数据源标识”；若标识为空，系统会按 Excel 文件名生成只含字母、数字与下划线的默认标识。若自动生成的标识与现有数据源重复，则要求用户手动修改后再保存，不再强制“先填标识再选文件”。
- 步骤 1 的 `路径替换` 现升级为 `数据源路径管理`：弹窗拆成 `本地路径 / SVN 路径` 两组，分别管理本地目录与远端 SVN 目录 URL；两组都支持保存目录列表、一键替换文件名前目录，并在替换后立即刷新受影响数据源与变量预览。
- 路径管理的持久化模型同步拆分为本地 / SVN 两套预设：工作台配置新增本地与 SVN 两组目录列表；项目校验配置版本从 `5` 升到 `6`，旧单组路径列表会自动迁移到本地路径分组。
- `数据源路径管理` 弹窗的已保存目录列表现改为标准 B 端交互列表：支持按组行内新增、编辑、删除目录预设，当前选择以徽标标记，删除前有二次确认；本地路径与 SVN 路径两组都继续沿用原有整批预校验后再替换的安全链路。

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
- 规则类型 `composite_condition_check`：组合分支校验，支持「全局筛选 + 分支筛选 + 分支校验」结构；筛选操作符覆盖 `eq / ne / gt / lt / not_null / contains`，分支校验操作符覆盖 `eq / ne / gt / lt / not_null / unique / duplicate_required`。
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

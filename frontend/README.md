# Excel Check Frontend

Excel Check 的前端子项目：`Vue 3 + TypeScript + Vite + Pinia + Element Plus + Tailwind v3`。

> 项目级说明、架构与协议请看根目录 [../README.md](../README.md) 与 [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)，本子项目 README 只覆盖前端如何安装、启动、构建与目录速查。

## 安装与启动

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

默认开发地址：<http://127.0.0.1:5173>，Vite 代理后端 <http://127.0.0.1:8000>。

## 构建生产包

```powershell
cd frontend
npm run build
```

构建产物输出到 `frontend/dist/`，构建过程同时执行 `vue-tsc` 类型检查。

## 本机共享部署

本机部署给其他同网段用户访问时，不需要单独启动 Vite。回到项目根目录执行：

```powershell
.\scripts\start-local-deploy.ps1
```

脚本会先执行前端构建，再由 FastAPI 托管 `frontend/dist/`，访问地址为 `http://<本机局域网IP>:8000`。前端所有 API 继续使用相对路径 `/api/v1/...`。

远程用户添加本地 Excel 数据源时，请使用数据源弹窗里的「上传文件」。CSV 与飞书当前仍为占位入口，新增数据源下拉中会显示“占位”并禁用选择；弹窗里的「服务器选择」只会在服务所在机器弹出文件框，手动输入路径也必须是服务所在机器或共享盘可访问的路径。

## 目录速查

```text
frontend/src
├── api/                # HTTP 封装：apiFetch、auth、admin、workbench、fixedRules
├── components
│   ├── shell/          # 共享 UI 组件：PageHeader / AppCard / SectionHeader / StatusBadge / Button / MetricCard / DataTable / EmptyState
│   └── workbench/      # 个人校验业务组件：DataSourcePanel / VariablePoolPanel / WorkbenchRuleOrchestrationPanel / ResultBoardPanel
├── router/             # vue-router：/login /register / /fixed-rules /admin /profile
├── store/              # Pinia：auth / workbench / fixedRules
├── types/              # TypeScript 类型：workbench / fixedRules / auth
├── utils/              # ruleOrchestrationModel / taskTree / workbenchMeta / apiFetch
├── views/              # 页面入口：MainBoard / FixedRulesBoard / AdminView / ProfileView / LoginView / RegisterView
├── App.vue             # 应用壳：ec-* 左侧固定边栏 + 右侧独立滚动工作区
├── main.ts             # 入口
└── style.css           # 全局 token 与共享 utility（统一收口在此）
```

更细的「文件 → 作用」对照请看 [../docs/MODULES.md](../docs/MODULES.md)。

## 设计 token

- 色板：`bg-canvas=#F6F8FC / bg-card=#FFFFFF / bg-subtle=#F3F7FF / ink-{900,700,500,300} / border-line=#E5EAF3 / accent=#0F62FE / accent-soft=#EAF2FF / accent-ink=#004EEB / success=#12B76A / warning=#FF7A1A / danger=#EF4444`。
- 边框层级：模块外框 `border-gray-200`，单元格 / 表格内部 `border-gray-100`，强调态 `border-blue-500`。
- 圆角：`rounded-field=8px`、`rounded-card=18px`，大面板使用 `--radius-xl=24px`。
- 阴影：卡片默认 `--shadow-card`，悬停 `--shadow-card-hover`，主按钮 `--shadow-button`。
- 字体：`Inter + Noto Sans SC + JetBrains Mono`（KPI 大数字使用等宽）。
- `corePlugins.preflight = false`：避免与 Element Plus 冲突；浏览器默认样式（如 `dd { margin-left: 40px }`）需要在组件内显式覆盖。

## 通用 UI 组件

- `components/shell` 承载新版 SaaS 视觉组件：页面头、白色卡片、分段标题、状态胶囊、三类按钮、指标卡、表格与空态。
- 旧组件 `StatusDot / StatPill` 保留为兼容包装，新页面优先使用 `StatusBadge / MetricCard`。
- `EmptyState` 支持 `table / panel / result` 三种空态场景和 `source / variable / rule / result` 图标语义，表格空数据应优先使用它而不是单行纯文本。
- 页面级视觉替换应优先复用这些组件，不直接复制卡片、按钮、状态标签和表格样式。
- `style.css` 末尾保留 `Global UI Final Polish` 最终覆盖层，用于统一 Element Plus、旧 `ec-*` 类和新版 `ui-*` 组件的按钮、输入框、表格、标签、卡片、空态与链接细节。
- 个人校验 `/` 使用 `personal-check-*` 专用类、项目校验 `/fixed-rules` 使用 `project-check-*` 专用类，对步骤条、统计卡、工作区表格、规则区和结果空态做参考稿级视觉精修；两者共享同一套 SaaS 工作台视觉基线。
- 个人校验 `/` 与项目校验 `/fixed-rules` 共享 `ResultBoardPanel`：执行后可导出 Excel，文件包含 `统计摘要` 与 `异常明细` 两个页签，导出的是当前 `result_id` 的全量结果而不是当前分页。
- 管理后台 `/admin` 使用 `admin-dashboard-*` 专用类，对页面头操作区、统计卡、项目列表卡片、详情表格和成员表格做新版后台视觉精修。
- 个人设置 `/profile` 使用 `profile-settings-*` 专用类，对账号信息、横向密码表单、我的项目表格和状态标签做新版设置页视觉精修。

## 联调流程

详见根 [../README.md](../README.md) 第 4 节「最短联调」。

规则编排补充：

- 个人校验步骤 3 的单变量规则弹窗现已支持 `包含 (in)`。
- 个人校验步骤 3 与项目校验 `/fixed-rules` 的单变量规则弹窗都支持 `顺序校验`。
- 个人校验步骤 3 与项目校验 `/fixed-rules` 的规则弹窗现统一支持 4 类入口：`单一变量校验`、`组合分支校验`、`跨组变量校验`、`多组串行校验`。
- 规则弹窗会先选择规则类型，再按类型过滤目标变量：单一变量校验只显示单变量，组合分支校验 / 跨组变量校验 / 多组串行校验只显示组合变量。
- 单一变量校验新增 `正则校验`，输入正则表达式后会按完整匹配校验整格内容。
- `多组串行校验` 支持 1..N 个组合变量节点：单节点时执行“前置过滤 + 最终判定”，多节点时按顺序串行执行；首个失败节点会输出该节点的全部异常并停止后续节点。
- `顺序校验` 按原始表格行序逐行检查数值连续性，支持升序 / 降序、步长，以及自动首行 / 手动起始值。
- `跨组变量校验` 会先按两个组合变量的外层 Key 关联，再按配置的多条字段比较规则做 AND 校验；当前支持 `等于 / 不等于 / 大于 / 小于 / 非空`，并可切换 `基准变量为准 / 双向检查` 两种 Key 校验方式。
- 选择 `包含 (in)` 后，“比较值”会从文本输入切换为变量池中的单个变量下拉。
- 该规则前端保存时会复用现有 `cross_table_mapping` 执行语义，不新增后端接口。
- `组合分支校验` 的全局筛选与分支筛选现支持字符串 `包含 / 不包含`，语义为“字段值包含 / 不包含固定片段”；这两个操作符都只允许固定值右侧，不进入分支校验，也不影响单变量 `包含 (in)`。
- `组合分支校验` 的分支校验条件新增 `正则校验`，适合直接校验字段格式是否符合指定模式。
- `组合分支校验` 保存时会正确保留 `contains` 的比较值；像“全局筛选 contains + 分支筛选 contains + 分支校验 not_null”这类混合配置已可正常保存。
- 添加组合变量时，只有当前 `Key 列` 存在重复值，才会显示“Key 后追加序号”；开启后会按原始行序把键生成为 `原值_序号`，用于处理原始 Key 列存在重复值的场景。编辑已有变量时，如果历史上已启用该选项，复选框会继续显示，方便查看和取消。

管理后台补充：

- 超级管理员在 `/admin` 的成员表中调整**自己的**归属项目后，前端会自动调用现有项目切换接口，同步左下角当前项目与后续页面上下文。
- 调整其他成员的归属项目时，不会影响当前登录管理员自己的当前项目。

SVN 数据源接入：

- 在「新增数据源」弹窗里把类型切到 `SVN（推荐 HTTP 链接）`，默认进入「远端 URL」子模式；输入目录 URL（例如 `https://samosvn/data/project/samo/GameDatas/datas_qa88/`）后点「浏览此目录」即可在弹窗里挑选 `.xls/.xlsx` 文件。
- 本地 Excel 与 SVN Excel 现在都支持“先选文件，再自动回填数据源标识”；若当时标识为空，会按文件名自动生成一个只含字母、数字与下划线的标识。若自动生成值与现有数据源重复，页面会提示你手动修改后再保存。
- 步骤 2 的字段映射与变量添加现同时支持本地 Excel 和 SVN Excel；CSV 与飞书入口当前显示为“占位”并禁用新增。
- 步骤 1 头部的 `数据源路径管理` 现只管理远端 SVN 目录 URL；本地 Excel 推荐通过上传文件重新接入，不再提供本地路径替换管理。
- SVN 路径替换会先做整批预校验：数据源元数据和受影响变量预览只要有一项失败，就整批回滚，不会把坏路径保存进配置。
- 首次访问某 host 时会弹出「配置 SVN 凭据」弹窗：用户名 / 密码会按当前登录用户与 host 维度加密落到 `<runtime>/svn-credentials.json`，凭据保存后会自动重新触发一次浏览。
- 再次打开同一 host 的「配置 SVN 凭据」弹窗时，会回填上次保存的用户名、密码与测试目录 URL；host 列表接口仍不返回密码，密码仅在按 host 读取详情时回填到当前用户自己的弹窗表单。
- `samosvn` 的“测试目录 URL”默认回填为 `https://samosvn/data/project/samo/GameDatas/`；你也可以改成别的 SVN 目录并保存。系统会按当前登录用户与 host 记住这个目录，“测试连接”会先保存凭据，再对当前输入的目录执行一次 `svn list`。
- 页面刷新后，步骤 1 的远端 SVN 数据源会主动拉取当前登录用户已保存的 SVN host 凭据列表；状态列会按 `检测中 → 已就绪 / 待授权 / 状态未知` 的真实加载结果更新，不再依赖手动打开弹窗后才纠正状态。
- SVN 业务级鉴权失败用 HTTP 403 表达，不会让前端误以为登录态过期；首次拉取 `~400 文件目录` 通常需要 1–3 秒（取决于网络），后续命中本地缓存即时返回，60 秒 TTL 内重复执行不再访问 SVN。
- 若需要强制刷新缓存或浏览到子目录的文件：picker 支持回到入口目录后再下钻 1 层；`/fixed-rules` 的 SVN 更新按钮会同时刷新本地工作副本和远端缓存目录。

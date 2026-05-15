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

## 规范检查

```powershell
cd frontend
npm run lint
npm run format:check
```

前端命名、接口类型和组件分层规范以 [../docs/STANDARDS.md](../docs/STANDARDS.md) 为准。

## 本机共享部署

本机部署给其他同网段用户访问时，不需要单独启动 Vite。回到项目根目录执行：

```powershell
.\scripts\start-local-deploy.ps1
```

脚本会先执行前端构建，再由 FastAPI 托管 `frontend/dist/`，访问地址为 `http://<本机局域网IP>:8000`。前端所有 API 继续使用相对路径 `/api/v1/...`。

远程用户添加本地 Excel 数据源时，请使用数据源弹窗里的「上传文件」。CSV 数据源已不再支持，飞书当前仍为占位入口且禁用选择；弹窗里的「服务器选择」只会在服务所在机器弹出文件框，手动输入路径也必须是服务所在机器或共享盘可访问的路径。

## 目录速查

```text
frontend/src
├── api/                # HTTP 封装：apiFetch、auth、admin、workbench、fixedRules、ai
├── components
│   ├── profile/        # 个人设置业务组件：AI 模型配置等
│   ├── shell/          # 共享 UI 组件：PageHeader / AppCard / SectionHeader / StatusBadge / Button / MetricCard / DataTable / EmptyState
│   └── workbench/      # 个人校验业务组件：DataSourcePanel / VariablePoolPanel / WorkbenchRuleOrchestrationPanel / WorkbenchAiRulePanel / WorkbenchRuleImportDrawer / ResultBoardPanel
├── router/             # vue-router：/login /register / /fixed-rules /admin /profile /user-guide
├── store/              # Pinia：auth / workbench / fixedRules / ai
├── styles/             # 全局样式模块：shared / workbench / personal-check / fixed-rules / admin / profile / auth / user-guide / ai-rule
├── types/              # TypeScript 类型：api / workbench / fixedRules / auth / ai
├── utils/              # ruleOrchestrationModel / taskTree / workbenchMeta / apiFetch
├── views/              # 页面入口：MainBoard / FixedRulesBoard / AdminView / ProfileView / UserGuideView / LoginView / RegisterView
├── App.vue             # 应用壳：ec-* 左侧固定边栏 + 右侧独立滚动工作区
├── main.ts             # 入口
└── style.css           # Tailwind 指令入口；具体全局样式按域拆到 styles/
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
- `style.css` 仅保留 Tailwind 指令；全局 token、Element Plus 校准、旧 `ec-*`、新版 `ui-*`、页面专用样式和最终覆盖层按原 cascade 顺序拆到 `src/styles/`。其中 `shared-final.css` 保留 `Global UI Final Polish`，用于统一按钮、输入框、表格、标签、卡片、空态与链接细节。
- 个人校验 `/` 使用 `personal-check-*` 专用类、项目校验 `/fixed-rules` 使用 `project-check-*` 专用类，对步骤条、统计卡、工作区表格、规则区和结果空态做参考稿级视觉精修；两者共享同一套 SaaS 工作台视觉基线。
- 个人校验 `/` 与项目校验 `/fixed-rules` 共享 `ResultBoardPanel`：执行后可导出 Excel，文件包含 `统计摘要` 与 `异常明细` 两个页签，导出的是当前 `result_id` 的全量结果而不是当前分页；规则可选配置 `结果显示字段`，异常明细表和导出会展示该字段值。
- 管理后台 `/admin` 使用 `admin-dashboard-*` 专用类，对页面头操作区、统计卡、项目列表卡片、详情表格和成员表格做新版后台视觉精修。
- 个人设置 `/profile` 使用 `profile-settings-*` 专用类，对账号信息、横向密码表单、我的项目表格和状态标签做新版设置页视觉精修。

## 联调流程

详见根 [../README.md](../README.md) 第 4 节「最短联调」。

系统使用说明入口：

- `/user-guide` 面向新用户提供快速上手指南，按“个人校验首跑 -> 项目校验复用 -> 数据源 / 变量 / 规则 -> 结果查看 -> FAQ”组织内容。
- 个人校验页和个人设置页均提供“系统使用说明”入口，可在新页签打开后按目录跳转章节。

规则编排补充：

- 个人校验步骤 3 的规则区包含 `手动规则编排 / 智能添加规则` 两个页签。智能页签现在保留「目标变量」多选、规则描述输入框和“允许 AI 自动补齐数据源/变量”开关：默认关闭时用户先从变量池选择一个或多个变量，再用推荐格式描述规则，AI 只基于所选变量生成草稿；开启后目标变量可不选，但描述中需要包含配置表路径、Sheet 和字段线索，AI 才会补齐数据源 / 变量。输入框上方提供两类辅助入口：基于已选变量 `single/composite`、字段、组合列和 Key 自动生成的推荐规则，以及默认收起、可按需展开的系统内置规则模板 / 常用案例。点击模板或推荐卡片只会预填描述和解析线索，仍需用户手动点击 AI 校验、执行预校验并确认添加。优化提示词里的“未识别到 Key 字段”会被视为占位说明，不会写入 Key 线索；已有组合变量覆盖规则字段时会直接复用并按变量池真实列名回写，新增变量会按表头精确匹配、`trim` 唯一匹配和保守唯一相似匹配进行纠偏，无法唯一匹配时仍提示补充。AI 校验结果会以解释卡展示 `ready / needs_input / rejected`：说明为什么匹配到某个规则类型、还缺什么、点击哪里修复，以及不可添加时可如何改写为当前支持规则。ready 草稿的预校验结果会继续聚合异常原因、规则名、定位样例和修复建议；发现异常或数据源失败时，可点击“带调整建议重新生成”把这些反馈作为临时 extra_hints 重新生成草稿。结果为 `needs_input` 且自动补齐开启时，可点击“一键补齐并添加”重新生成草稿：后端会对未保存的数据源临时读取表头，Key 只使用用户明确输入或 `INT_ID / INT_Id / ID`，预校验通过后一次性保存数据源、组合变量和规则，不会立即执行正式校验。信息仍不足时结果区会提示补充完整描述，或关闭自动补齐并选择已有变量池变量。后端覆盖当前 10 类已有规则，草稿会先用临时 TaskTree 在面板内执行预校验，不会直接改配置；`ready` 且预校验成功后才可添加并立即保存，`rejected` 会展示当前规则库缺失能力和扩展建议。
- 手动规则勾选后可点“导入项目校验”打开宽体导入抽屉：抽屉先调用项目校验导入预检，展示规则、数据源和变量映射；匹配到项目已有数据源时默认只读复用，改为自定义源只影响本次导入草稿。若项目变量池已有同名但绑定不同的变量，可在变量映射表修改本次导入的目标变量标签，重新预检通过后会新增对应变量并同步改写规则引用；重复或不兼容项会跳过不覆盖。
- AI 模型配置在 `/profile`，支持 OpenAI-compatible、Anthropic Messages、Gemini generateContent 三类协议预设；内置 OpenAI、DeepSeek、通义千问、Kimi、智谱 GLM、OpenRouter、小米 MiMo、小米 MiMo 会员等选项，也可使用自定义 OpenAI 兼容配置。前端只展示连接状态和跳转入口，API Key 明文不回显。
- 个人校验步骤 3 的单变量规则弹窗现已支持 `包含 (in)`。
- 个人校验步骤 3 与项目校验 `/fixed-rules` 的单变量规则弹窗都支持 `顺序校验`。
- 个人校验步骤 3 与项目校验 `/fixed-rules` 的规则弹窗现统一支持 5 类入口：`单一变量校验`、`组合分支校验`、`跨组变量校验`、`多组串行校验`、`多组映射校验`。
- 规则弹窗会先选择规则类型，再按类型过滤目标变量：单一变量校验只显示单变量，组合分支校验 / 跨组变量校验只显示组合变量；多组串行校验 / 多组映射校验不显示顶部目标变量，变量只在每个节点内选择。
- 每条规则可选 `结果显示字段`：单变量规则只能选择当前列，组合类规则可选择当前组合变量的 Key 或组合列，多组串行 / 多组映射按节点选择；未选择时结果列为空。
- `等于 / 不等于 + 固定值` 支持切换 `固定值 / 规则集`；选择规则集后用英文逗号配置多个值，例如 `0,1,2`，命中任一值即视为等于，命中任一值即触发不等于异常。
- 单一变量校验新增 `正则校验`，输入正则表达式后会按完整匹配校验整格内容。
- `多组串行校验` 支持 1..N 个组合变量节点：单节点时执行“前置过滤 + 最终判定”，多节点时按顺序串行执行；首个失败节点会输出该节点的全部异常并停止后续节点。
- `多组映射校验` 支持 1..N 个组合变量节点：每个节点内的多条筛选条件都是独立检查项；某行未通过筛选时会先进入异常结果，再按该筛选的“筛选失败排除行号范围 + 判定值”判断是否移除。判定值固定比较当前筛选字段，支持英文逗号多值，例如 `0,1,2`；节点之间不短路，全部执行后汇总异常，适合“少数 Excel 行号不满足筛选但符合业务预期”的配置校验。
- `顺序校验` 按原始表格行序逐行检查数值连续性，支持升序 / 降序、步长，以及自动首行 / 手动起始值。
- `跨组变量校验` 在组合条件段选择“基准变量”和“目标变量（变量 2）”，会先对左右组合变量分别应用可选筛选，再按左右“关联 Key 字段”关联并按多条字段比较规则做 AND 校验；当前支持 `等于 / 不等于 / 大于 / 小于 / 非空`，并可切换 `基准变量为准 / 双向检查` 两种 Key 校验方式。同一组合变量也可拆成左右筛选子集后比较，但左右筛选都必须至少 1 条。关联 Key 默认 `__key__` 兼容旧规则；当组合变量启用 `Key 后追加序号` 时，可改选 `INT_Level` 等业务字段实现按原始字段对齐。
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

- 在「新增数据源」弹窗里默认选中 `SVN（推荐 HTTP 链接）`，并进入「远端 URL」子模式；点击 `SVN 文件 URL` 输入框可从「数据源路径管理」已保存的 SVN 目录建议中选择，也可直接手动输入目录 URL，再点「浏览此目录」在弹窗里挑选 `.xls/.xlsx` 文件。
- 本地 Excel 与 SVN Excel 现在都支持“先选文件，再自动回填数据源标识”；若当时标识为空，会按文件名自动生成一个只含字母、数字与下划线的标识。若自动生成值与现有数据源重复，页面会提示你手动修改后再保存。
- 步骤 2 的字段映射与变量添加现同时支持本地 Excel 和 SVN Excel；CSV 数据源已不再支持，飞书入口当前显示为“占位”并禁用新增。
- 步骤 1 头部的 `数据源路径管理` 现只管理远端 SVN 目录 URL；本地 Excel 推荐通过上传文件重新接入，不再提供本地路径替换管理。
- SVN 路径替换会先做整批预校验：数据源元数据和受影响变量预览只要有一项失败，就整批回滚，不会把坏路径保存进配置。
- 首次访问某 host 时会弹出「配置 SVN 凭据」弹窗：用户名 / 密码会按当前登录用户与 host 维度加密落到 `<runtime>/svn-credentials.json`，凭据保存后会自动重新触发一次浏览。
- 再次打开同一 host 的「配置 SVN 凭据」弹窗时，会回填上次保存的用户名、密码与测试目录 URL；host 列表接口仍不返回密码，密码仅在按 host 读取详情时回填到当前用户自己的弹窗表单。
- `samosvn` 的“测试目录 URL”默认回填为 `https://samosvn/data/project/samo/GameDatas/`；你也可以改成别的 SVN 目录并保存。系统会按当前登录用户与 host 记住这个目录，“测试连接”会先保存凭据，再对当前输入的目录执行一次 `svn list`。
- 页面刷新后，步骤 1 的远端 SVN 数据源会主动拉取当前登录用户已保存的 SVN host 凭据列表；状态列会按 `检测中 → 已就绪 / 待授权 / 状态未知` 的真实加载结果更新，不再依赖手动打开弹窗后才纠正状态。
- SVN 业务级鉴权失败用 HTTP 403 表达，不会让前端误以为登录态过期；首次拉取 `~400 文件目录` 通常需要 1–3 秒（取决于网络），后续命中本地缓存即时返回，60 秒 TTL 内重复执行不再访问 SVN。
- 若需要强制刷新缓存或浏览到子目录的文件：picker 支持回到入口目录后再下钻 1 层；个人校验 `/` 与项目校验 `/fixed-rules` 的 SVN 更新按钮都会先保存当前配置，再刷新本地工作副本和远端缓存目录。

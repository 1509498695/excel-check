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

## 目录速查

```text
frontend/src
├── api/                # HTTP 封装：apiFetch、auth、admin、workbench、fixedRules
├── components
│   ├── shell/          # 共享展示组件：PageHeader / SectionHeader / StatPill / StatusDot / EmptyState / DataTable
│   └── workbench/      # 个人校验业务组件：DataSourcePanel / VariablePoolPanel / WorkbenchRuleOrchestrationPanel / ResultBoardPanel
├── router/             # vue-router：/login /register / /fixed-rules /admin /profile
├── store/              # Pinia：auth / workbench / fixedRules
├── types/              # TypeScript 类型：workbench / fixedRules / auth
├── utils/              # ruleOrchestrationModel / taskTree / workbenchMeta / apiFetch
├── views/              # 页面入口：MainBoard / FixedRulesBoard / AdminView / ProfileView / LoginView / RegisterView
├── App.vue             # 应用壳：左侧固定边栏 + 右侧独立滚动工作区
├── main.ts             # 入口
└── style.css           # 全局 token 与共享 utility（统一收口在此）
```

更细的「文件 → 作用」对照请看 [../docs/MODULES.md](../docs/MODULES.md)。

## 设计 token

- 色板：`bg-canvas / bg-card / bg-subtle / ink-{900,700,500,300} / border-line / accent / accent-soft / accent-ink / success / warning / danger`。
- 边框层级：模块外框 `border-gray-200`，单元格 / 表格内部 `border-gray-100`，强调态 `border-blue-500`。
- 圆角：`rounded-field=6px`、`rounded-card=12px`。
- 字体：`Inter + Noto Sans SC + JetBrains Mono`（KPI 大数字使用等宽）。
- `corePlugins.preflight = false`：避免与 Element Plus 冲突；浏览器默认样式（如 `dd { margin-left: 40px }`）需要在组件内显式覆盖。

## 联调流程

详见根 [../README.md](../README.md) 第 4 节「最短联调」。

规则编排补充：

- 个人校验步骤 3 的单变量规则弹窗现已支持 `包含 (in)`。
- 个人校验步骤 3 与项目校验 `/fixed-rules` 的单变量规则弹窗都支持 `顺序校验`。
- 个人校验步骤 3 与项目校验 `/fixed-rules` 的规则弹窗现统一支持 3 类入口：`单变量校验`、`组合条件校验`、`双组合变量比对`。
- 规则弹窗会先选择规则类型，再按类型过滤目标变量：单变量校验只显示单变量，组合条件校验与双组合变量比对只显示组合变量。
- 单变量校验新增 `正则校验`，输入正则表达式后会按完整匹配校验整格内容。
- `顺序校验` 按原始表格行序逐行检查数值连续性，支持升序 / 降序、步长，以及自动首行 / 手动起始值。
- `双组合变量比对` 会先按两个组合变量的外层 Key 关联，再按配置的多条字段比较规则做 AND 校验；当前支持 `等于 / 不等于 / 大于 / 小于 / 非空`，并可切换 `基准变量为准 / 双向检查` 两种 Key 校验方式。
- 选择 `包含 (in)` 后，“比较值”会从文本输入切换为变量池中的单个变量下拉。
- 该规则前端保存时会复用现有 `cross_table_mapping` 执行语义，不新增后端接口。
- `组合条件校验` 的全局筛选与分支筛选现支持字符串 `包含 / 不包含`，语义为“字段值包含 / 不包含固定片段”；这两个操作符都只允许固定值右侧，不进入分支校验，也不影响单变量 `包含 (in)`。
- `组合条件校验` 的分支校验条件新增 `正则校验`，适合直接校验字段格式是否符合指定模式。
- `组合条件校验` 保存时会正确保留 `contains` 的比较值；像“全局筛选 contains + 分支筛选 contains + 分支校验 not_null”这类混合配置已可正常保存。
- 添加组合变量时，只有当前 `Key 列` 存在重复值，才会显示“Key 后追加序号”；开启后会按原始行序把键生成为 `原值_序号`，用于处理原始 Key 列存在重复值的场景。编辑已有变量时，如果历史上已启用该选项，复选框会继续显示，方便查看和取消。

管理后台补充：

- 超级管理员在 `/admin` 的成员表中调整**自己的**归属项目后，前端会自动调用现有项目切换接口，同步左下角当前项目与后续页面上下文。
- 调整其他成员的归属项目时，不会影响当前登录管理员自己的当前项目。

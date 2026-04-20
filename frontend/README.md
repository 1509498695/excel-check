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
│   └── workbench/      # 工作台业务组件：DataSourcePanel / VariablePoolPanel / WorkbenchRuleOrchestrationPanel / ResultBoardPanel
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

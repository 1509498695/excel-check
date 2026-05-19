# Excel Check Frontend

Excel Check 前端子项目使用 `Vue 3 + TypeScript + Vite + Pinia + Element Plus + Tailwind v3`。项目级说明、架构和协议请看 [../README.md](../README.md) 与 [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)。

## 安装与启动

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

默认开发地址：<http://127.0.0.1:5173>。开发期 API 通过 Vite 代理到 <http://127.0.0.1:8000>。

## 构建与检查

```powershell
cd frontend
npm run lint
npm run format:check
npm run build
```

`npm run build` 会先执行 `vue-tsc` 类型检查，再输出生产包到 `frontend/dist/`。

## 本机共享部署

本机部署给同网段用户访问时，不需要单独启动 Vite。回到项目根目录执行：

```powershell
.\scripts\start-local-deploy.ps1
```

脚本会构建前端并由 FastAPI 托管 `frontend/dist/`，访问地址为 `http://<本机局域网IP>:8000`。前端 API 继续使用相对路径 `/api/v1/...`。

远程用户添加 Excel 数据源时应使用“上传文件”。“服务器选择”和手动路径只适合服务所在机器或共享盘路径。

## 目录速查

```text
frontend/src
├── api/           # HTTP 封装：auth / admin / workbench / fixedRules / ai
├── components/    # shell 共享组件与各业务组件
├── router/        # vue-router 与认证守卫
├── store/         # Pinia：auth / workbench / fixedRules / ai
├── styles/        # token、Element Plus 校准、页面域样式
├── types/         # API 与业务类型
├── utils/         # taskTree、规则模型、apiFetch、AI 输入草稿工具
├── views/         # 页面入口
├── App.vue        # 应用壳
├── main.ts        # 入口
└── style.css      # Tailwind 指令入口
```

更细的文件职责见 [../docs/MODULES.md](../docs/MODULES.md)。

## 设计约定

- 页面布局优先复用 `components/shell/` 的页面头、卡片、按钮、状态、表格和空态组件。
- 业务组件只处理当前业务域，不复制全局按钮、表格和状态样式。
- `style.css` 只保留 Tailwind 指令；全局 token 和页面域样式按 `src/styles/` 拆分。
- `corePlugins.preflight = false`，避免 Tailwind reset 与 Element Plus 冲突。
- API 请求集中在 `src/api/`，接口类型集中在 `src/types/`，跨模块响应类型复用 `types/api.ts`。
- 提交给后端的历史 wire 字段保持原名，例如 `pathOrUrl`、`source_id`、`rule_type`。

## 联调入口

完整联调步骤见根目录 [../README.md](../README.md) 的“最短联调”。规则能力、AI 智能添加规则、SVN 和接口契约见 [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)。

## AI 智能添加规则

- 个人校验步骤 03 的「查看配置」会以只读规则配置预览展示 AI 草稿，字段结构尽量对齐手动新增/编辑规则弹窗。
- 预览会合并当前变量池变量和 AI 草稿待新增变量；JSON 原始结构保留在折叠调试区，默认不展开。

# Excel Check

文档更新时间：2026-05-19 18:05

> 当前稳定文档入口：本 README、[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)、[docs/MODULES.md](docs/MODULES.md)、[docs/STANDARDS.md](docs/STANDARDS.md)、[frontend/README.md](frontend/README.md) 与 [CHANGELOG.md](CHANGELOG.md)。历史需求、进度日记和一次性重构方案已归档到 [docs/archive/](docs/archive/)。

Excel Check 是面向配置表校验场景的多用户 Web 应用。系统把数据源、变量池、规则编排和执行结果统一在同一个 `TaskTree` 上，支持个人临时校验和项目长期复用两条业务线。

## 1. 当前能力

- 多用户认证与项目隔离：支持超级管理员、项目管理员、普通用户；默认管理员为 `admin / 123456`。
- 个人校验 `/`：四步流程，数据源 → 变量池 → 规则编排 → 结果；执行统一走 `POST /api/v1/engine/execute`。
- 项目校验 `/fixed-rules`：按项目保存长期规则配置，支持从个人校验导入规则、执行、结果分页和 Excel 导出。
- 管理后台 `/admin`：项目管理、成员角色/归属调整、密码重置。
- 个人设置 `/profile`：账号信息、密码修改、项目切换、个人 AI 模型配置。
- 数据源：本地 Excel、浏览器上传 Excel、SVN Excel；CSV 已不再支持，飞书为占位入口。
- 规则能力：当前支持 10 类规则，覆盖单字段、固定值、正则、顺序、跨表映射、组合分支、双组比较、多组串行和多组映射。
- 智能添加规则：个人校验步骤 03 支持基于已选变量和规则描述生成 `ready / needs_input / rejected` 草稿；`ready` 草稿必须先预校验，再由用户确认写入配置。详细契约见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 2. 技术栈与地址

| 层 | 技术 |
|---|---|
| 后端 | FastAPI、SQLAlchemy Async、SQLite、python-jose、bcrypt、httpx |
| 前端 | Vue 3、TypeScript、Vite、Pinia、Element Plus、Tailwind v3 |
| 数据读取 | pandas、openpyxl、xlrd、SVN CLI |

默认开发地址：

- 前端：<http://127.0.0.1:5173>
- 后端健康检查：<http://127.0.0.1:8000/health>
- 后端 OpenAPI：<http://127.0.0.1:8000/docs>
- API 前缀：`/api/v1`

## 3. 快速开始

安装后端依赖：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

安装前端依赖：

```powershell
cd frontend
npm install
```

启动后端：

```powershell
python backend/run.py
```

启动前端：

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

启动时会自动初始化 SQLite、创建默认项目 `默认项目` 与默认管理员。

## 4. 本机共享部署

用于“服务在本机运行，其他同网段用户通过浏览器访问”的场景。前端会先构建到 `frontend/dist/`，再由 FastAPI 统一托管。

```powershell
.\scripts\start-local-deploy.ps1
```

脚本默认监听 `0.0.0.0:8000`。远程用户添加 Excel 数据源时应使用“上传文件”；服务器文件选择和手动路径只适合服务所在机器或共享盘路径。

建议首次共享前设置：

```powershell
$env:JWT_SECRET_KEY="替换为一段固定随机字符串"
$env:DEFAULT_SUPER_ADMIN_PASSWORD="替换默认管理员密码"
```

常用环境变量：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `APP_HOST` | `127.0.0.1` | 后端监听地址，共享部署脚本会设为 `0.0.0.0`。 |
| `APP_PORT` | `8000` | 后端端口。 |
| `FRONTEND_DIST_DIR` | `frontend/dist` | 前端生产包目录。 |
| `CORS_ALLOW_ORIGINS` | `*` | 允许来源，逗号分隔。 |
| `MAX_UPLOAD_MB` | `50` | 单个上传文件大小上限。 |
| `DB_URL` | SQLite 运行库 | 后续内网部署可切换外部数据库。 |

## 5. 测试与构建

```powershell
python -m pytest backend/tests -q
```

```powershell
cd frontend
npm run lint
npm run build
```

一键规范检查：

```powershell
.\scripts\check-standards.ps1
```

## 6. 最短联调

1. 启动后端和前端。
2. 打开 <http://127.0.0.1:5173/login>，使用 `admin / 123456` 登录。
3. 进入个人校验 `/`，按 01 → 02 → 03 添加 Excel 数据源、变量和规则。
4. 点击执行校验，确认结果区展示统计块、异常明细和导出入口。
5. 可选：在 `/profile` 配置 AI 模型后，到 03「智能添加规则」生成草稿，完成预校验后确认添加。

## 7. API 速览

| 模块 | 常用入口 |
|---|---|
| 健康检查 | `GET /health` |
| 认证 | `POST /api/v1/auth/login`、`GET /api/v1/auth/me`、`POST /api/v1/auth/switch-project/{project_id}` |
| 数据源 | `GET /api/v1/sources/capabilities`、`POST /api/v1/sources/upload`、`POST /api/v1/sources/metadata`、`POST /api/v1/sources/column-preview` |
| 个人校验 | `GET/PUT /api/v1/workbench/config`、`POST /api/v1/workbench/svn-update`、`POST /api/v1/engine/execute` |
| AI 规则助手 | `GET/PUT/DELETE /api/v1/ai/providers/me`、`POST /api/v1/ai/agents/rule-draft`、`POST /api/v1/ai/agents/rule-prompt-optimize`、`GET/DELETE /api/v1/ai/drafts` |
| 项目校验 | `GET/PUT /api/v1/fixed-rules/config`、`POST /api/v1/fixed-rules/import-preview`、`POST /api/v1/fixed-rules/import-from-workbench`、`POST /api/v1/fixed-rules/execute` |
| 管理后台 | `/api/v1/admin/projects*`、`/api/v1/admin/projects/{id}/members*`、`POST /api/v1/admin/users/{id}/reset-password` |

完整协议见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 8. 文档入口

- 架构与协议：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- 模块速查：[docs/MODULES.md](docs/MODULES.md)
- 开发规范：[docs/STANDARDS.md](docs/STANDARDS.md)
- 前端说明：[frontend/README.md](frontend/README.md)
- 版本日志：[CHANGELOG.md](CHANGELOG.md)
- 历史归档：[docs/archive/](docs/archive/)

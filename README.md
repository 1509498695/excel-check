# Excel Check

> 历史变更与早期 SDD 已搬到 [docs/archive/](docs/archive/)；本 README、[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)、[docs/MODULES.md](docs/MODULES.md) 与 [CHANGELOG.md](CHANGELOG.md) 是当前唯一稳定文档。

面向配置表校验场景的多用户 Web 应用：把数据源、变量池、规则编排和执行结果统一在同一个 `TaskTree` 上，支持「个人校验临时编排」与「项目校验长期复用」两条业务线。

## 1. 当前关键能力

- JWT 认证 + 三级角色（超级管理员 / 项目管理员 / 普通用户），默认超级管理员 `admin / 123456`。
- 多项目数据隔离：项目校验按 `project_id`、个人校验配置按 `project_id + user_id`。
- 个人校验 `/`：四步工作流（数据源 → 变量池 → 规则编排 → 结果），构建 `TaskTree` 走 `POST /api/v1/engine/execute`。
- 项目校验 `/fixed-rules`：独立 `version=4` 配置，可保存数据源 / 变量 / 规则组 / 规则，支持 `SVN 更新`。
- 管理后台 `/admin`：项目 CRUD、成员角色与归属调整、密码重置；项目管理员可额外查看默认项目，但默认项目里的删号操作仍仅超级管理员可用；超级管理员可在后台成员表的本人行调整自己的归属项目，保存后前端会自动切换当前项目到新的归属项目。
- 个人设置 `/profile`：账号信息、密码修改、项目切换。
- 已支持规则类型：`not_null`、`unique`、`fixed_value_compare`、`sequence_order_check`、`cross_table_mapping`、`composite_condition_check`、`dual_composite_compare`；其中个人校验与项目校验的规则弹窗现支持 3 类入口：单变量校验、组合变量校验、双组合变量比对。`dual_composite_compare` 会先按两个组合变量的外层 Key 关联，再按多条字段比对规则执行 AND 校验。
- 数据源能力：本地 Excel（`.xlsx` / `.xls`）、本地 CSV；飞书与 SVN 作为独立 source 类型当前为占位。

## 2. 技术栈与默认地址

- 后端：FastAPI + SQLAlchemy（异步）+ SQLite + bcrypt + python-jose。
- 前端：Vue 3 + TypeScript + Pinia + Element Plus + Tailwind v3。
- 默认服务地址：
  - 前端：<http://127.0.0.1:5173>
  - 后端健康检查：<http://127.0.0.1:8000/health>
  - 后端 OpenAPI：<http://127.0.0.1:8000/docs>
- API 前缀：`/api/v1`。

## 3. 快速开始

### 3.1 安装依赖

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

```powershell
cd frontend
npm install
```

### 3.2 启动后端

```powershell
python backend/run.py
```

启动时会自动初始化 SQLite、创建默认项目 `默认项目` 与默认管理员 `admin / 123456`。

### 3.3 启动前端

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

### 3.4 测试与构建

```powershell
python -m pytest backend/tests -q
cd frontend
npm run build
```

## 4. 最短联调（5 步）

1. 启动后端 + 前端。
2. 浏览器打开 <http://127.0.0.1:5173/login>，使用 `admin / 123456` 登录。
3. 进入个人校验 `/`，按 01 → 02 → 03 顺序：
   - 01 新增本地 Excel 数据源（建议 `backend/tests/data/minimal_rules.xlsx`）。
   - 02 添加变量（来源 → Sheet → 列名 → 期望类型）。
   - 03 在规则组里新增规则（单变量校验 / 组合变量校验 / 双组合变量比对）。
     - 双组合变量比对：先选“基准变量”和“目标变量”，再配置 Key 校验方式与多条字段比对规则。
4. 点击 03 模块底部「执行校验」。
5. 结果区会展示 4 个统计块（扫描总行数 / 失败数据源 / 异常结果 / 执行耗时）+ 异常明细表。

## 5. API 速览

完整协议请看 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) 第 5 章；常用入口：

| 模块 | 入口 |
|---|---|
| 健康检查 | `GET /health` |
| 认证 | `POST /api/v1/auth/{register,login,change-password}`、`GET /api/v1/auth/me`、`POST /api/v1/auth/switch-project/{project_id}` |
| 数据源 | `GET /api/v1/sources/capabilities`、`POST /api/v1/sources/{local-pick,metadata,column-preview,composite-preview}` |
| 个人校验 | `POST /api/v1/engine/execute`、`GET/PUT /api/v1/workbench/config` |
| 项目校验 | `GET/PUT /api/v1/fixed-rules/config`、`POST /api/v1/fixed-rules/{svn-update,execute}` |
| 管理后台 | `/api/v1/admin/projects*`、`/api/v1/admin/projects/{id}/members*`、`POST /api/v1/admin/users/{id}/reset-password` |

## 6. 相关文档

- 架构与协议：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- 模块速查：[docs/MODULES.md](docs/MODULES.md)
- 版本日志：[CHANGELOG.md](CHANGELOG.md)
- 前端子项目：[frontend/README.md](frontend/README.md)
- 历史快照：[docs/archive/](docs/archive/)

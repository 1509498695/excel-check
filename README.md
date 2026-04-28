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
- 已支持规则类型：`not_null`、`unique`、`fixed_value_compare`、`regex_check`、`sequence_order_check`、`cross_table_mapping`、`composite_condition_check`、`dual_composite_compare`、`multi_composite_pipeline_check`；其中个人校验与项目校验的规则弹窗现支持 4 类入口：单一变量校验、组合分支校验、跨组变量校验、多组串行校验。弹窗会先选规则类型，再按类型过滤目标变量；单一变量校验新增 `正则校验`，组合分支校验的分支校验条件也支持 `正则校验`，两者都按完整匹配校验整格内容。`composite_condition_check` 的全局筛选和分支筛选已支持字符串 `包含 / 不包含`，`dual_composite_compare` 会先按两个组合变量的外层 Key 关联，再按多条字段比对规则执行 AND 校验。`multi_composite_pipeline_check` 支持 1..N 个组合变量节点：单节点时退化为“前置过滤 + 最终判定”，多节点时按顺序执行，首个失败节点会输出全部异常并短路后续节点。添加组合变量时还可按原始行序生成 `原值_序号` 的唯一键；只有当前 Key 列存在重复值，才会显示“Key 后追加序号”。
- 项目校验 `/fixed-rules` 的 `组合分支校验` 保存链路已修复：当全局筛选或分支筛选使用字符串 `包含` 时，前端会保留比较值并按正确协议提交，不再误报“缺少比较值”。
- 数据源能力：本地 Excel（`.xlsx` / `.xls`）、SVN Excel（远端 URL / 工作副本）；CSV 与飞书入口当前显示为“占位”并禁用新增，步骤 2 的字段映射与变量提取支持本地 Excel / SVN Excel。
- 数据源弹窗支持“先选文件，再自动回填数据源标识”：本地 Excel 与 SVN Excel 选中文件后，若标识为空，会按文件名自动生成仅含字母、数字与下划线的标识；若与已有标识重复，则需手动修改后再保存。

## 2. 技术栈与默认地址

- 后端：FastAPI + SQLAlchemy（异步）+ SQLite + bcrypt + python-jose。
- 前端：Vue 3 + TypeScript + Pinia + Element Plus + Tailwind v3。
- 默认开发地址：
  - 前端：<http://127.0.0.1:5173>
  - 后端健康检查：<http://127.0.0.1:8000/health>
  - 后端 OpenAPI：<http://127.0.0.1:8000/docs>
- 本机共享部署地址：前端构建后由后端单服务托管，其他同网段用户访问 `http://<本机局域网IP>:8000`。
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

### 3.4 本机共享部署

适用于“服务部署在本机，其他同网段用户通过浏览器访问”的场景。前端会先构建到 `frontend/dist/`，再由 FastAPI 统一托管，只开放一个后端端口。

```powershell
.\scripts\start-local-deploy.ps1
```

脚本默认监听 `0.0.0.0:8000`，启动后会打印本机局域网访问地址。远程用户添加 Excel 数据源时应使用「上传文件」，上传文件会落到 `backend/.runtime_uploads/local_excel/<project_id>/<user_id>/`；CSV 与飞书当前仍为占位入口，新增数据源下拉中会禁用选择；「服务器选择」与手动路径只适合服务所在机器或共享盘路径。

建议首次共享前固定设置：

```powershell
$env:JWT_SECRET_KEY="替换为一段固定随机字符串"
$env:DEFAULT_SUPER_ADMIN_PASSWORD="替换默认管理员密码"
```

可选环境变量：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `APP_HOST` | `127.0.0.1` | 后端监听地址，共享部署脚本会设为 `0.0.0.0`。 |
| `APP_PORT` | `8000` | 后端端口。 |
| `FRONTEND_DIST_DIR` | `frontend/dist` | 前端生产包目录。 |
| `CORS_ALLOW_ORIGINS` | `*` | 开发 / 反代场景允许的来源，逗号分隔。 |
| `MAX_UPLOAD_MB` | `50` | 单个上传文件大小上限。 |
| `DB_URL` | SQLite 运行库 | 后续内网部署可切换外部数据库。 |

### 3.5 测试与构建

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
   - 03 在规则组里新增规则（先选单一变量校验 / 组合分支校验 / 跨组变量校验 / 多组串行校验，再从过滤后的变量列表中选择目标变量）。
     - 跨组变量校验：先选“基准变量”和“目标变量”，再配置 Key 校验方式与多条字段比对规则。
     - 多组串行校验：可只配置 1 个组合变量节点，也可追加多个节点；每个节点先做前置过滤，再做最终判定，首个失败节点会短路后续节点。
4. 点击 03 模块底部「执行校验」。
5. 结果区会展示 4 个统计块（扫描总行数 / 失败数据源 / 异常结果 / 执行耗时）+ 异常明细表，并可导出包含“统计摘要 / 异常明细”的 Excel。

## 5. API 速览

完整协议请看 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) 第 5 章；常用入口：

| 模块 | 入口 |
|---|---|
| 健康检查 | `GET /health` |
| 认证 | `POST /api/v1/auth/{register,login,change-password}`、`GET /api/v1/auth/me`、`POST /api/v1/auth/switch-project/{project_id}` |
| 数据源 | `GET /api/v1/sources/capabilities`、`POST /api/v1/sources/{local-pick,metadata,column-preview,composite-preview}` |
| 个人校验 | `POST /api/v1/engine/execute`、`GET /api/v1/engine/results/{result_id}`、`GET /api/v1/engine/results/{result_id}/export`、`GET/PUT /api/v1/workbench/config` |
| 项目校验 | `GET/PUT /api/v1/fixed-rules/config`、`POST /api/v1/fixed-rules/{svn-update,execute}`、`GET /api/v1/fixed-rules/results/{result_id}`、`GET /api/v1/fixed-rules/results/{result_id}/export` |
| 管理后台 | `/api/v1/admin/projects*`、`/api/v1/admin/projects/{id}/members*`、`POST /api/v1/admin/users/{id}/reset-password` |

## 6. 相关文档

- 架构与协议：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- 模块速查：[docs/MODULES.md](docs/MODULES.md)
- 版本日志：[CHANGELOG.md](CHANGELOG.md)
- 前端子项目：[frontend/README.md](frontend/README.md)
- 历史快照：[docs/archive/](docs/archive/)

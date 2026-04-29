# Excel Check 架构设计

> 本文档替代原 `需求文档.md`（已归档到 [archive/需求文档.md](archive/需求文档.md)），作为当前唯一的稳定 SDD。  
> 所有公告 / 分钟级变更不再写在本文档；版本演进请看 [../CHANGELOG.md](../CHANGELOG.md)。  
> 模块对照表请看 [MODULES.md](MODULES.md)。

## 1. 系统目标与边界

Excel Check 解决游戏 / 配置类项目中「同一份配置表反复需要被多个规则校验」的工程问题。设计目标：

- 把「数据源 / 变量 / 规则」抽象成统一的 `TaskTree`，所有执行入口共享同一个执行引擎与同一份结果协议。
- 区分两种使用场景：
  - **临时编排**（个人校验 `/`）：项目配置不持久化到项目校验配置，刷新即丢；适合一次性排查。
  - **长期复用**（项目校验 `/fixed-rules`）：按 `project_id` 持久化到 `version=6` 配置，可反复执行，可接 SVN 拉新。
- 多用户多项目隔离：项目校验配置按 `project_id` 隔离，个人校验配置按 `project_id + user_id` 隔离。

明确不做：

- 不做飞书数据源真实业务化读取（仅占位）。
- 不做多配置集切换；`regex_check` 与结果导出已接入个人校验和项目校验。
- 不做 SaaS 化部署；本轮只支持本机共享部署，远程用户文件通过上传进入服务端，`local-pick` 仍仅适合服务所在机器的桌面联调。
- SVN 远端 URL 接入仅承诺 `http(s)://`，不做 `svn://` / `svn+ssh://`，且 URL 必须指向单文件（`.xls/.xlsx`）。

## 2. 技术栈与运行约束

| 层 | 选择 |
|:---|:---|
| 后端 | Python 3.10+、FastAPI、SQLAlchemy 异步、SQLite（运行时数据库 `backend/.runtime/excel_check.db`） |
| 认证 | python-jose（JWT）+ bcrypt；默认管理员 `admin / 123456` 启动时固定播种 |
| 数据读取 | pandas + openpyxl（`.xlsx`）+ xlrd（`.xls`） |
| 外部能力 | TortoiseSVN CLI 自动探测（Windows）、tkinter 文件对话框（本地拾取） |
| 前端 | Vue 3 + TypeScript + Vite + Pinia + Element Plus + Tailwind v3 |
| 设计系统 | Tailwind v3 token + 共享 shell 组件；`corePlugins.preflight = false`（兼容 Element Plus） |

运行约束：

- 接口前缀统一 `/api/v1`；OpenAPI 在 `/docs`。
- 本地文件选择经后端 `tkinter` 弹窗拿到真实绝对路径写回前端，不走浏览器 `<input type="file">`。
- 本机共享部署支持前端生产包由 FastAPI 托管：`frontend/dist` 存在时，`/api/v1/*`、`/health`、`/docs` 保持后端路由，其余路径回退到 `index.html`。
- 远程浏览器可通过 `/api/v1/sources/upload` 上传 `.xlsx/.xls/.csv`，文件按 `<runtime_uploads>/local_excel/<project_id>/<user_id>/` 隔离保存，再复用现有 `DataSource.pathOrUrl` 与统一执行引擎。
- SQLite 运行时数据库由后端启动时自动建表与播种默认数据，无需手工迁移脚本。
- 本机共享部署通过 `APP_HOST / APP_PORT / FRONTEND_DIST_DIR / CORS_ALLOW_ORIGINS / MAX_UPLOAD_MB / JWT_SECRET_KEY / DEFAULT_SUPER_ADMIN_PASSWORD / DB_URL` 预留后续内网部署配置入口；本轮不引入容器、反代、HTTPS 或外部数据库。

## 3. 当前关键能力

### 3.1 已闭环

- 多用户认证：注册 / 登录 / 当前用户 / 修改密码 / 切换项目；JWT 携带；前端 `apiFetch` 统一注入与 `401` 跳登录。
- 三级角色：超级管理员、项目管理员、普通用户；项目管理员可进入受限版 `/admin`。
- 多项目数据隔离：项目校验按 `project_id`、个人校验配置按 `project_id + user_id`。
- 个人校验四步工作流：数据源 → 变量池 → 规则编排 → 结果。
- 项目校验页独立 `version=6` 配置：`sources / variables / groups / rules` 一体化保存，并兼容历史路径替换字段。
- 10 类规则：`not_null / unique / regex_check / sequence_order_check / fixed_value_compare / cross_table_mapping / composite_condition_check / dual_composite_compare / multi_composite_pipeline_check / multi_composite_mapping_check`。
- 组合变量：同一数据源同 Sheet 的多列组合，支持 `key_column` 与 JSON 映射。
- 统一执行结果协议：4 字段 `meta` + N 行 `abnormal_results`。
- SVN 数据源（HTTP）打通：用户在数据源弹窗里粘贴目录 URL，弹窗浏览选择 `.xls/.xlsx`，凭据按当前登录用户与 host 维度加密落盘；远端 URL 落到 `<runtime>/svn-cache/<host>/<key>/` 并复用统一执行引擎。`/api/v1/fixed-rules/svn-update` 同时支持本地工作副本与远端缓存目录。
- 全站统一视觉：`PageHeader / SectionHeader / StatPill / DataTable / EmptyState` 共享组件。

### 3.2 占位 / 未闭环

- `feishu` 数据源：仅返回 `NotImplementedError` 占位。
- CSV 数据源的变量池下拉提取：未开放（CSV 仍可参与执行）。
- 多配置集切换：未开放。
- SVN 远端 URL 仅支持单文件 `.xls/.xlsx`（不做目录级 svn 数据源、不做分支切换）。

## 4. 数据模型

### 4.1 `TaskTree`（执行入参）

```python
# backend/app/api/schemas.py
class DataSource:
    id: str
    type: Literal["local_excel", "local_csv", "feishu", "svn"]
    path: str | None
    url: str | None
    pathOrUrl: str | None
    token: str | None

class VariableTag:
    tag: str
    source_id: str
    sheet: str
    variable_kind: Literal["single", "composite"] = "single"
    column: str | None              # single
    columns: list[str] | None       # composite
    key_column: str | None          # composite
    expected_type: Literal["int", "str", "json"] | None

class ValidationRule:
    rule_id: str | None
    rule_type: str
    params: dict[str, Any]

class TaskTree:
    sources: list[DataSource]
    variables: list[VariableTag]
    rules: list[ValidationRule]
```

所有模型 `extra="forbid"`，未知字段直接 `422`。

### 4.2 `FixedRulesConfig`（项目校验页持久化）

当前版本 `version = 6`，结构（简化）：

```text
{
  "version": 6,
  "configured": true,
  "sources":   [DataSource, ...],
  "variables": [VariableTag, ...],
  "groups":    [{ group_id, group_name, builtin? }, ...],
  "rules":     [{
    rule_id, group_id, rule_name,
    target_variable_tag,
    rule_type: "fixed_value_compare" | "regex_check" | "sequence_order_check" | "not_null" | "unique" | "cross_table_mapping" | "composite_condition_check" | "dual_composite_compare" | "multi_composite_pipeline_check" | "multi_composite_mapping_check",
    operator?: "eq" | "ne" | "gt" | "lt",      # 仅 fixed_value_compare
    expected_value?: str,                      # 仅 fixed_value_compare
    reference_variable_tag?: str,             # 仅 cross_table_mapping，前端“包含 (in)”引用的基础字典变量
    composite_config?: CompositeRuleConfig,    # 仅 composite_condition_check
    pipeline_config?: MultiCompositePipelineConfig,
    mapping_config?: MultiCompositeMappingConfig
  }, ...]
}
```

`CompositeRuleConfig` 由 `global_filters[]` 与 `branches[]` 组成，每个 branch 含 `filters[]`（命中条件）与 `assertions[]`（校验条件）。`multi_composite_pipeline_check` 与 `multi_composite_mapping_check` 的 `target_variable_tag` 仅作为旧协议兼容字段保存为首个节点变量，实际校验依赖 `pipeline_config.nodes[].variable_tag` / `mapping_config.nodes[].variable_tag`。

旧版 `version 2 / 3 / 4 / 5` 在读取时自动迁移到 `version = 6`，无需手工干预。

### 4.3 `AbnormalResult`（执行结果元素）

```python
{
    "level": "error" | "warning" | ...,
    "rule_name": str,            # 固定规则优先使用用户配置的规则名称
    "location": str,             # 形如 sheet -> column
    "row_index": int,            # Excel 实际行号 = pandas 索引 + 2
    "raw_value": Any,            # 原始单元格值
    "message": str,
}
```

### 4.4 统一响应协议

所有执行入口（`/engine/execute` 与 `/fixed-rules/execute`）返回相同结构：

```python
# backend/app/utils/formatter.py
{
    "code": 200,
    "msg": "Execution Completed",
    "meta": {
        "execution_time_ms": int,
        "total_rows_scanned": int,
        "failed_sources": [str],
    },
    "data": {
        "abnormal_results": [AbnormalResult, ...],
    },
}
```

固定规则配置读取额外允许 `meta.config_issues: [{ source_id, message }]`，作为非阻断告警。

## 5. API 协议

所有接口前缀 `/api/v1`，详细字段见 [backend/app/api/schemas.py](../backend/app/api/schemas.py) 与 [backend/app/api/fixed_rules_schemas.py](../backend/app/api/fixed_rules_schemas.py)。

### 5.1 认证 `/auth`

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| `POST` | `/auth/register` | 注册（可选 project_id）。普通用户默认不会自动晋升超级管理员。 |
| `POST` | `/auth/login` | 登录返回 JWT；默认管理员失败时受控自修复并重试一次。 |
| `GET` | `/auth/me` | 当前用户、当前项目、当前角色、可访问项目列表。 |
| `POST` | `/auth/switch-project/{project_id}` | 切换当前项目，签发新 JWT。 |
| `POST` | `/auth/change-password` | 修改本人密码。 |

### 5.2 管理后台 `/admin`

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| `GET` | `/admin/projects` | 列出当前用户可管理项目（超级管理员见全部；项目管理员额外包含默认项目）。 |
| `POST` | `/admin/projects` | 创建项目（仅超级管理员）。 |
| `PUT` | `/admin/projects/{project_id}` | 修改项目名称 / 描述。 |
| `DELETE` | `/admin/projects/{project_id}` | 删除项目（默认项目禁止删除）；返回 `204`。 |
| `GET` | `/admin/projects/{id}/members` | 列出成员，含归属项目；项目管理员可查看默认项目成员。 |
| `PUT` | `/admin/projects/{id}/members/{user_id}/role` | 调整成员在该项目内的角色；默认项目对项目管理员开放该非删除操作。 |
| `PUT` | `/admin/projects/{id}/members/{user_id}/project` | 调整成员归属项目；普通用户仍按单项目收口，超级管理员仅可调整自己的归属项目并自动补目标项目 `admin` 角色，其他成员不能调整超管归属；当前登录超管在管理后台调整本人归属后，前端会自动切换当前项目。 |
| `DELETE` | `/admin/projects/{id}/members/{user_id}` | 默认项目内 = 删除账号（仅超级管理员）；其他项目内 = 迁回默认项目。 |
| `POST` | `/admin/users/{user_id}/reset-password` | 重置指定用户密码。 |
| `GET` | `/admin/projects-public` | 公开的项目列表（注册页选项）。 |

### 5.3 数据源 `/sources`

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| `GET` | `/sources/capabilities` | 当前后端能力声明。 |
| `POST` | `/sources/local-pick` | 调起本机 tkinter 弹窗，返回真实绝对路径。 |
| `POST` | `/sources/upload` | 浏览器上传 `.xlsx/.xls/.csv` 到服务端运行目录，返回可复用为数据源路径的绝对路径。 |
| `POST` | `/sources/metadata` | 读取 Excel 数据源的 Sheet/列名结构（local_excel + svn HTTP）。 |
| `POST` | `/sources/column-preview` | 读取指定列的预览数据。 |
| `POST` | `/sources/composite-preview` | 同 Sheet 多列组合的 JSON 映射预览。 |
| `POST` | `/sources/svn-list` | 列出 SVN 远端目录条目（`svn list --xml`），目录 URL 不在 host 白名单时拒绝。 |
| `POST` | `/sources/svn-credentials` | 保存当前登录用户某 host 的 SVN 用户名/密码（Fernet 加密落盘）。 |
| `GET` | `/sources/svn-credentials` | 列出当前登录用户已保存的 SVN host（不返回密码）。 |
| `DELETE` | `/sources/svn-credentials/{host}` | 删除某 host 凭据。 |
| `POST` | `/sources/svn-refresh` | 强制刷新某 SVN 远端 URL 数据源缓存（绕 TTL）。 |

> SVN 业务级鉴权失败统一用 HTTP 403 表达（带 `category=auth_failed`），不会触发前端 `apiFetch` 的「自动跳登录」逻辑；HTTP 401 仅用于真正的登录态过期。

### 5.4 个人校验 `/engine` `/workbench`

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| `POST` | `/engine/execute` | 入参 `TaskTree`，出参统一响应协议。 |
| `GET` | `/workbench/config` | 读取当前用户在当前项目下的个人校验配置。 |
| `PUT` | `/workbench/config` | 保存个人校验配置（前端 2 秒防抖自动调用）。 |

### 5.5 项目校验 `/fixed-rules`

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| `GET` | `/fixed-rules/config` | 读取当前项目的项目校验配置；可能附带 `meta.config_issues`。 |
| `PUT` | `/fixed-rules/config` | 保存配置（严格校验）。 |
| `POST` | `/fixed-rules/svn-update` | 汇总规则路径，按父目录去重统一执行 SVN 更新。 |
| `POST` | `/fixed-rules/execute` | 服务端聚合临时 `TaskTree` 后复用主引擎；返回统一响应协议。 |

## 6. 前端三页结构

### 6.1 个人校验 `/`

[MainBoard.vue](../frontend/src/views/MainBoard.vue)：4 个全宽通栏模块，每个模块头都使用 `SectionHeader variant="workbench"`。

| 步骤 | 组件 | 职责 |
|:---|:---|:---|
| 01 数据源 | [DataSourcePanel.vue](../frontend/src/components/workbench/DataSourcePanel.vue) | CRUD 数据源、本地路径选择 |
| 02 变量池 | [VariablePoolPanel.vue](../frontend/src/components/workbench/VariablePoolPanel.vue) | 单变量 / 组合变量、Sheet/列下拉、详情弹窗 |
| 03 规则编排 | [WorkbenchRuleOrchestrationPanel.vue](../frontend/src/components/workbench/WorkbenchRuleOrchestrationPanel.vue) | 规则组导航 + 规则 CRUD + 弹窗（单变量支持 `eq / ne / gt / lt / not_null / unique / 包含(in)`，组合变量支持条件分支、跨组比对、多组串行与多组映射） |
| 04 结果 | [ResultBoardPanel.vue](../frontend/src/components/workbench/ResultBoardPanel.vue) | 4 统计块 + 异常明细表 |

个人校验编排不持久化，刷新即丢；`workbench` store 在主要状态变更后 2 秒防抖自动调用 `PUT /workbench/config`。

### 6.2 项目校验页 `/fixed-rules`

[FixedRulesBoard.vue](../frontend/src/views/FixedRulesBoard.vue)：与个人校验同套 4 步骨架（顶部 Stepper + KPI + 01–04 模块）；规则区复用 `WorkbenchRuleOrchestrationPanel` 同款样式但走自己的 `useFixedRulesStore`；结果区直接复用 `ResultBoardPanel`。

### 6.3 管理后台 `/admin` 与个人设置 `/profile`

| 页面 | 组成 |
|:---|:---|
| `/admin` | KPI（项目数 / 当前项目成员 / 超级管理员 / 我的归属项目）+ 单列三模块（项目列表 / 项目详情 / 项目成员），项目卡片 `border-blue-500 + bg-blue-50` 选中态，成员表用极浅 `border-gray-100` 网格线；项目管理员也可在后台选中默认项目，但默认项目中的删除成员入口仍受限。 |
| `/profile` | 全宽 3 模块：账号信息（横向 4 列描述列表）/ 修改密码（`max-w-md` 表单 + 左对齐保存按钮）/ 我的项目（4 列等宽表格）。 |

## 7. 规则引擎

### 7.1 三层架构

```
backend/app/rules/
├── domain/
│   ├── value.py        # 值规范化、空判断、numpy 标量降级
│   ├── result.py       # AbnormalResult 值对象 + dict 构造
│   └── operators.py    # 5 种 operator 在筛选 / 断言两套语义下的判定
├── infrastructure/
│   └── tag_extractor.py # 各 rule_type 的依赖 tag 提取器
├── handlers/
│   ├── basics.py       # not_null / unique
│   ├── cross.py        # cross_table_mapping
│   ├── fixed.py        # fixed_value_compare / regex / sequence / 组合类规则
│   └── __init__.py     # 副作用 import 触发 @register_rule 注册
└── engine_core.py
```

### 7.2 注册模型

```python
# engine_core.py
class RuleSpec:
    handler:         Callable[[RuleExecutionContext], list[AbnormalResult]]
    dependent_tags:  Callable[[ValidationRule], list[str]]

@register_rule("composite_condition_check", dependent_tags=by_target_tag)
def handle_composite(ctx): ...
```

`execute_api._extract_rule_tags` 直接走 `RULE_REGISTRY[rule_type].dependent_tags(rule)`，避免与 handler 真实依赖之间漂移。依赖失败 source 的规则会被 `_filter_executable_rules` 一致跳过，不阻断整次执行。

### 7.3 当前支持的 10 类规则

| `rule_type` | 适用变量 | 说明 |
|:---|:---|:---|
| `not_null` | 单变量 | 非空校验，`level=error` |
| `unique` | 单变量 | 唯一校验，`level=warning` |
| `regex_check` | 单变量 | 按正则表达式完整匹配整格内容 |
| `sequence_order_check` | 单变量 | 按原始行序检查数值连续性 |
| `fixed_value_compare` | 单变量 | 与常量值的 `eq / ne / gt / lt` 比较 |
| `cross_table_mapping` | 单变量 | 跨表映射（值需在另一变量集合中）；个人校验规则弹窗中的 `包含 (in)` 前端保存时复用该规则 |
| `composite_condition_check` | 组合变量 | 全局筛选 + 分支筛选 + 分支校验，校验操作符覆盖 `eq / ne / gt / lt / not_null / regex / unique / duplicate_required` |
| `dual_composite_compare` | 组合变量 | 按外层 Key 关联两个组合变量，再执行多字段 AND 比较 |
| `multi_composite_pipeline_check` | 组合变量 | 1..N 个组合变量节点串行执行，首个失败节点短路后续节点 |
| `multi_composite_mapping_check` | 组合变量 | 1..N 个组合变量节点独立执行；每条筛选条件独立检查失败行，并可按筛选失败排除行号范围移除预期异常 |

`multi_composite_mapping_check` 使用独立 `mapping_config`，不复用 `pipeline_config`：`nodes[].variable_tag` 选择组合变量，`nodes[].filters[]` 是多组映射专用筛选检查；每条筛选在 `CompositeCondition` 字段基础上增加 `exclusion_ranges[]`。执行时逐条筛选独立判断：通过筛选则无异常，未通过筛选则检查当前 Excel 行号是否命中该筛选的“筛选失败排除行号范围”；命中即移除该条异常，不命中则保留。旧版 `field_checks / field / ranges / default_expected_value` 仅做读取容错，不再执行或保存。

## 8. 多用户与项目隔离

### 8.1 用户与项目关系

- `User`：含 `is_super_admin: bool`、`primary_project_id: int | null`（主归属项目）。
- `UserProjectRole`：多对多关系表，`role ∈ {admin, user}`，描述用户在某项目内的角色。
- 登录 / `/auth/me` 当前项目按主归属项目优先选择，不再依赖 `roles[0]`。
- 普通用户始终保持单归属项目，归属调整在管理后台完成；项目管理员的归属项目仍不允许在后台调整；超级管理员仅允许在后台调整自己的归属项目，且会自动补齐目标项目 `admin` 角色记录。
- 当前登录超级管理员在管理后台调整本人归属项目成功后，前端会立刻调用现有 `switch-project` 接口刷新 JWT 和当前项目，不需要再去个人设置手动切换。

### 8.2 数据隔离

| 资源 | 隔离维度 |
|:---|:---|
| 项目校验配置 `FixedRulesConfigRecord` | `project_id` |
| 个人校验配置 `WorkbenchConfigRecord` | `project_id + user_id` |
| 数据源 / 变量 / 规则（运行时） | 在所选项目下加载，跨项目不可见 |

切换项目走 SPA 内 `useWorkbenchStore.loadFromServer + useFixedRulesStore.resetState/loadConfig`，不再整页刷新。

### 8.3 默认项目

- 系统保留项目 `默认项目`，启动时自动创建；任何角色都禁止删除。
- 项目管理员进入管理后台时可额外看到默认项目，用于查看成员、调角色与调归属；默认项目中的成员删除仍只允许超级管理员。
- 超级管理员可在管理后台成员表的本人行执行“调整归属项目”；除本人外，任何成员都不能调整超级管理员归属项目。
- 删除自定义项目时，成员自动迁移到默认项目并降为普通用户；若成员已存在角色记录则保留。

## 9. 异常处理与性能

### 9.1 异常处理策略

| 场景 | 当前处理 |
|:---|:---|
| 本地文件不存在 / 不可读 | `400` + 中文错误描述 |
| `.xls` 缺 `xlrd` / `.xlsx` 缺 `openpyxl` | `400` 提示安装对应依赖 |
| 规则引用未知 tag | `400` |
| 规则依赖失败数据源 | 该规则跳过，不阻断整次执行；失败 source 进入 `meta.failed_sources` |
| 固定规则配置：路径失效 / Sheet / 列不存在 | 读取走 `meta.config_issues` 非阻断；保存与执行仍严格 `400` |
| `svn` CLI 缺失 / 非工作副本 | 明确中文错误 |
| 飞书读取 | `NotImplementedError` 占位 |
| 默认管理员登录失败 | 触发受控自修复并重试一次 |

### 9.2 性能策略

- Excel / CSV 读取优先 `usecols`，按列裁剪。
- 多数据源读取使用线程池并发。
- 规则执行采用 pandas 列级运算。
- 统一响应结构避免重复转换成本。
- 行号统一口径：`Excel 行号 = pandas 索引 + 2`（pandas 从 0 开始 + Excel 第 1 行通常为表头）。

### 9.3 安全与运行约束

- `local-pick` 依赖桌面环境与 `tkinter`；无桌面服务环境不适用。
- 多人访问本机服务时，访问者电脑上的文件必须走浏览器上传；手动本地路径与 `local-pick` 都指向服务所在机器或共享盘。
- 上传目录 `backend/.runtime_uploads/local_excel/` 当前不做自动清理、不做病毒扫描；管理员需要按磁盘空间定期维护。
- bcrypt 密码哈希；JWT 由 `python-jose` 编解码；token 经 `apiFetch` 统一注入，`401` 自动跳登录。
- 默认管理员策略：启动时确保存在唯一默认超级管理员 `admin`；首次创建使用 `DEFAULT_SUPER_ADMIN_PASSWORD`（未设置时为 `123456`），已有 admin 不再被每次启动强制重置密码。
- SVN 远端 URL 通过 `settings.svn_url_allowlist`（默认 `samosvn`，可经环境变量 `SVN_URL_ALLOWLIST` 多 host 覆盖）做 SSRF 兜底；`/sources/svn-list/svn-refresh` 与 `/fixed-rules/svn-update` 都共享同一份白名单。
- SVN 凭据按当前登录用户与 host 维度独立保存；密码使用 `cryptography.fernet` 加密落 `<runtime>/svn-credentials.json`，密钥落 `<runtime>/.svn-key`（类 Unix 自动 `chmod 0600`，Windows 上由文件系统权限保护）；任何 `svn list/checkout/update` 子进程都显式 `--username/--password`，不依赖 `%APPDATA%/Subversion/auth/` 跨用户共享缓存。
- SVN 缓存 TTL 默认 60 秒；变量池/执行命中 TTL 内不再访问远端 SVN，超时或 `force_refresh=True`（`/sources/svn-refresh`、`/fixed-rules/svn-update`）会重新 `svn update`。

## 10. 已知遗留与不支持

- `feishu` 数据源真实接入未实现。
- CSV 数据源的变量池元数据下拉未开放（CSV 仍可参与执行）。
- 固定规则模块多配置集切换未实现。
- 多用户协同编辑冲突处理未实现（按防抖最后写入胜出）。
- 暂无 Alembic / Liquibase 数据库迁移脚本，数据库 schema 演进依赖启动时 `init_db()`。
- 没有 Playwright / UI 自动化基线，目前以 `pytest backend/tests + npm run build + 6 路由 200` 为最终验收口径。
- SVN 远端接入仅承诺 `http(s)://` + 单文件 `.xls/.xlsx`；不做 `svn://` / `svn+ssh://`、目录级 svn 数据源、`svn switch` 切分支；`<runtime>/svn-cache/` 目录无定时清理策略，需手动维护。

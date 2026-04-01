# 项目记录文档

## 记录时间

- 日期：2026-04-01
- 项目目录：`D:\project\excel-check`

## 本次记录目的

记录当前仓库从后端骨架、执行主流程到规则引擎与测试补充的阶段性进展，便于后续继续开发和回溯项目状态。

## 本次完成事项

基于当前工作区状态，可以确认此前已经完成了这些基础能力：

1. 搭建后端目录结构与启动入口
2. 提供健康检查与基础 API 骨架
3. 实现本地 Excel/CSV 变量提取
4. 打通 `POST /api/v1/engine/execute` 主干流程
5. 实现 `not_null`、`unique`、`cross_table_mapping` 三类基础规则

## 当前项目状态

当前项目已处于“后端 MVP 可运行”阶段，特点如下：

- 可以启动 FastAPI 服务
- 可以读取本地 Excel/CSV
- 可以执行基础规则
- 可以返回统一异常结构
- 已支持失败 source 降级
- 已具备最小接口测试基础

## 下一步建议

建议优先推进以下事项：

1. 为 `feishu` 和 `svn` 补真实接入或更明确的占位策略
2. 增加更多规则和测试覆盖
3. 补统一测试配置
4. 再启动前端联调

## 进度记录 2026-04-01

### 本次完成

- 新增最小测试数据文件 `backend/tests/data/minimal_rules.xlsx`
- 新增接口级后端测试文件 `backend/tests/test_execute_api.py`
- 覆盖空值、重复值、跨表映射缺失三类规则场景
- 覆盖未注册规则、非法参数、非法 `source_id` 三类错误场景
- 在 `backend/requirements.txt` 中补充 `pytest` 和 `httpx`
- 更新 `README.md`，补充测试说明、本地运行方式和当前缺失环境说明

### 规范化调整

- 将测试入口统一放入 `backend/tests`
- 将最小样例数据收敛到 `backend/tests/data`
- 保持测试直接调用真实接口 `POST /api/v1/engine/execute`，避免只验证内部函数

### 当前状态

- 仓库已经具备最小后端测试结构
- 测试依赖已经写入依赖清单，但本机若尚未重新安装，仍需要手动安装
- 目前还没有 `pytest.ini`、`pyproject.toml` 等统一测试配置文件

### 下一步建议

1. 执行 `pip install -r backend/requirements.txt`
2. 执行 `python -m pytest backend/tests -q`
3. 若后续测试规模扩大，再补统一测试配置文件

## 进度记录 2026-04-01

### 本次完成

- 重新检查当前项目运行环境与测试依赖状态
- 确认 `fastapi`、`uvicorn`、`pandas`、`openpyxl`、`requests`、`pytest`、`httpx`、`xlrd` 已安装
- 实际执行 `python -m pytest backend/tests -q` 并通过，结果为 `4 passed in 0.84s`
- 更新 `README.md`，将“环境缺失”的旧结论修正为“当前环境已满足运行和测试”

### 规范化调整

- 统一 README 中环境说明、测试说明与当前真实状态
- 将环境说明从“安装指引口径”调整为“本次核验结论口径”
- 保持项目记录按日期追加，不覆盖既有历史内容

### 当前状态

- 当前后端运行环境已满足现阶段项目需要
- 当前最小后端测试已可直接运行并通过
- 当前仍缺少的是统一测试配置文件和持续集成配置，而不是核心运行依赖

### 下一步建议

1. 补 `pytest.ini` 或 `pyproject.toml` 统一测试配置
2. 扩展更多规则与 source 降级测试
3. 在后续功能迭代时持续追加 `PROJECT_RECORD.md`

## 进度记录 2026-04-01 16:34

### 本次目标

- 按新版 `$govern-project-standards-cn` 流程，将项目文档升级为分钟级进度记录格式。
- 同步 README 当前整体进度，明确已完成功能、占位功能和未开始功能。

### 本次完成

- 为 `README.md` 增加分钟级 `文档更新时间` 字段。
- 更新 `README.md` 当前未实现内容，明确 `feishu`、`svn`、`regex` 的占位状态。
- 在 `README.md` 中新增“当前项目进度概览”，拆分为已完成功能、已实现但未打通/占位功能、未开始功能。
- 在 `PROJECT_RECORD.md` 中追加分钟级记录块，并按新模板补充本次治理记录。

### 当前项目进度

#### 已完成功能

- FastAPI 后端服务可启动，并提供 `GET /health`、`GET /api/v1/sources/capabilities`、`POST /api/v1/engine/execute` 三个核心接口。
- 本地 Excel/CSV 变量提取工具已实现，并已接入执行主流程。
- `not_null`、`unique`、`cross_table_mapping` 三类基础规则已可执行。
- source 级失败降级已接入执行流程，失败 source 会进入 `meta.failed_sources`。
- `backend/tests` 已具备最小接口测试和样例数据。

#### 已实现但未打通/占位功能

- `backend/app/loaders/feishu_reader.py` 已预留飞书读取入口，但当前仍为占位实现。
- `backend/app/loaders/svn_manager.py` 已预留 SVN 同步入口，但当前仍为占位实现。
- `regex` 规则处理器已注册，但当前仍未实现真实校验逻辑。

#### 未开始功能

- 更丰富的规则类型和规则组合能力。
- 前端工作台与联调页面。
- 统一的测试配置、代码规范配置和持续集成流程。

### 规范化调整

- 将项目进度记录从“按日追加”升级为“按分钟追加”。
- 统一 README 与 PROJECT_RECORD 的状态表达口径，避免把占位能力误写成未实现或已完成。
- 将项目文档从“阶段性描述”收敛为“当前全貌 + 本次变更”的双视角。

### 文档同步

- 更新 `README.md`：补 `文档更新时间`、当前项目进度概览、占位模块状态和工程化状态说明。
- 更新 `PROJECT_RECORD.md`：追加分钟级记录块，并同步当前项目整体进度。

### 未完成项与风险

- 当前仍缺少 `pytest.ini`、`pyproject.toml`、`ruff` / `.flake8` 等统一工程化配置。
- 飞书、SVN、`regex` 规则仍为占位或未完成能力，后续推进时需要继续同步文档状态。
- 当前项目状态说明基于 2026-04-01 16:34 的工作区扫描结果，后续功能迭代后需要继续追加分钟级记录。

### 下一步建议

1. 优先实现 `feishu` 或 `svn` 其中一个数据源的可测试最小版本。
2. 完成 `regex` 规则处理器，并补对应接口测试。
3. 补充 `pytest.ini` 或 `pyproject.toml`，统一测试与代码规范配置。

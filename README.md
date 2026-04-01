# Excel Check

文档更新时间：2026-04-01 16:34

## 项目简介

Excel Check 是一个面向企业级配置表的自动化检查与动态规则校验工作台后端项目。当前仓库已经具备后端主干执行流程，可以接收前端传入的 `TaskTree`，完成本地 Excel/CSV 变量提取、规则执行和统一结果返回。

当前实现重点放在后端 MVP：

- 本地 `Excel/CSV` 数据源读取
- 规则注册表与基础规则执行
- `POST /api/v1/engine/execute` 主干流程
- 基础接口测试与最小样例数据

## 技术栈

- Python 3.12
- FastAPI
- Uvicorn
- Pandas
- OpenPyXL
- Pytest
- HTTPX
- Requests

## 当前已实现内容

基于当前代码扫描和实际验证，可以确认以下能力已经可用：

- 提供 `GET /health` 健康检查接口
- 提供 `GET /api/v1/sources/capabilities` 数据源能力接口
- 提供 `POST /api/v1/engine/execute` 执行接口
- 定义 `TaskTree`、`DataSource`、`VariableTag`、`ValidationRule` 等请求模型
- 支持本地 `Excel/CSV` 按 `source + sheet + column` 精确提取变量列
- 支持规则注册表按 `rule_type` 动态分发
- 已实现三类基础规则：
  - `not_null`
  - `unique`
  - `cross_table_mapping`
- 已支持 source 级降级处理：
  - 单个 source 加载失败时写入 `meta.failed_sources`
  - 其他 source 和可执行规则继续运行
- 已补最小测试数据和接口级后端测试

## 当前未实现内容

以下能力当前仍处于占位或待实现状态：

- 飞书数据源真实接入：当前 `backend/app/loaders/feishu_reader.py` 仍为占位实现
- SVN 同步与冲突解析：当前 `backend/app/loaders/svn_manager.py` 仍为占位实现
- 更丰富的规则类型：当前 `regex` 规则处理器仍为占位实现
- 前端工作台
- 完整的测试配置文件和 CI 流程

## 当前项目进度概览

### 已完成功能

- FastAPI 后端可正常启动，并提供 `health`、`capabilities`、`execute` 三个核心接口
- 本地 `Excel/CSV` 变量提取工具已实现，并已接入 `POST /api/v1/engine/execute` 主流程
- `not_null`、`unique`、`cross_table_mapping` 三类规则已可执行
- source 级失败降级已接入执行流程，失败 source 会写入 `meta.failed_sources`
- 最小接口测试、测试数据和错误场景测试已补齐

### 已实现但未打通/占位功能

- 飞书数据源读取入口已预留，但当前仍为占位实现
- SVN 同步入口已预留，但当前仍为占位实现
- `regex` 规则类型已注册，但当前仍未实现真实校验逻辑

### 未开始功能

- 更丰富的规则类型和组合规则能力
- 前端工作台与联调页面
- 统一的测试配置、代码规范配置和持续集成流程

## 目录结构

```text
excel-check
├── backend
│   ├── app
│   │   ├── api
│   │   ├── loaders
│   │   ├── rules
│   │   └── utils
│   ├── tests
│   │   └── data
│   ├── config.py
│   ├── requirements.txt
│   └── run.py
├── PROJECT_RECORD.md
└── README.md
```

主要目录职责：

- `backend/app/api`：接口路由与请求模型
- `backend/app/loaders`：数据源读取层
- `backend/app/rules`：规则注册表与规则实现
- `backend/app/utils`：通用工具与响应格式化
- `backend/tests`：后端测试
- `backend/tests/data`：最小测试数据

## 安装依赖

建议先创建虚拟环境，再安装依赖：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

## 启动项目

在项目根目录执行：

```powershell
python backend/run.py
```

默认地址：

- 服务地址：`http://127.0.0.1:8000`
- 健康检查：`http://127.0.0.1:8000/health`
- Swagger 文档：`http://127.0.0.1:8000/docs`

## 关键接口

### `GET /health`

用于健康检查。

示例响应：

```json
{
  "code": 200,
  "msg": "ok",
  "data": {
    "status": "healthy",
    "service": "excel-check-backend"
  }
}
```

### `GET /api/v1/sources/capabilities`

用于返回当前后端已声明的数据源能力。

示例响应：

```json
{
  "code": 200,
  "msg": "ok",
  "data": {
    "source_types": ["local_excel", "local_csv", "feishu", "svn"],
    "implemented": false
  }
}
```

### `POST /api/v1/engine/execute`

用于接收前端构造的 `TaskTree` 并执行加载与规则校验。

示例请求：

```json
{
  "sources": [
    {
      "id": "src_test",
      "type": "local_excel",
      "path": "D:/project/excel-check/backend/tests/data/minimal_rules.xlsx"
    }
  ],
  "variables": [
    {
      "tag": "[items-id]",
      "source_id": "src_test",
      "sheet": "items",
      "column": "ID"
    },
    {
      "tag": "[drops-ref]",
      "source_id": "src_test",
      "sheet": "drops",
      "column": "RefID"
    }
  ],
  "rules": [
    {
      "rule_type": "not_null",
      "params": {
        "target_tags": ["[items-id]"]
      }
    },
    {
      "rule_type": "unique",
      "params": {
        "target_tags": ["[items-id]"]
      }
    },
    {
      "rule_type": "cross_table_mapping",
      "params": {
        "dict_tag": "[items-id]",
        "target_tag": "[drops-ref]"
      }
    }
  ]
}
```

示例响应：

```json
{
  "code": 200,
  "msg": "Execution Completed",
  "meta": {
    "execution_time_ms": 18,
    "total_rows_scanned": 8,
    "failed_sources": []
  },
  "data": {
    "abnormal_results": [
      {
        "level": "error",
        "rule_name": "not_null",
        "location": "[items-id] -> ID",
        "row_index": 5,
        "raw_value": null,
        "message": "该字段不能为空。"
      }
    ]
  }
}
```

## 测试

当前仓库已补最小测试数据和接口级后端测试：

- 测试文件：[test_execute_api.py](D:/project/excel-check/backend/tests/test_execute_api.py)
- 测试数据：[minimal_rules.xlsx](D:/project/excel-check/backend/tests/data/minimal_rules.xlsx)

覆盖场景：

- 空值
- 重复值
- 跨表映射缺失
- 未注册规则返回 `400`
- 非法规则参数返回 `400`
- 非法 `source_id` 返回 `400`

本地运行测试：

```powershell
python -m pytest backend/tests -q
```

已实测结果：

```text
4 passed in 0.84s
```

## 当前工程化状态

基于当前仓库文件和测试结构，可以确认当前已经具备最小运行与测试基础：

- `backend/requirements.txt` 已包含运行与测试所需的核心依赖
- `backend/tests` 已存在接口级测试与最小样例数据
- `python -m pytest backend/tests -q` 已有通过记录

当前仍待补充的是工程化配置，而不是核心功能能力，例如：

- `pytest.ini`
- `pyproject.toml`
- `ruff` / `.flake8` 等规范配置
- 持续集成配置

## 后续建议

建议下一阶段按这个顺序推进：

1. 为 `feishu` 和 `svn` 增加可测试的最小实现或更明确的降级测试
2. 补更多规则类型和规则参数校验测试
3. 增加 `pytest.ini` 或 `pyproject.toml`
4. 增加 `PROJECT_RECORD.md` 的持续更新

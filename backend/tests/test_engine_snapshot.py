"""引擎执行接口黑盒快照基线测试。

本模块只针对 `POST /api/v1/engine/execute` 的对外响应做字节级快照断言，
作为后续重构（PR-2 物理移动 / 拆分阶段）的安全网。

约定：
- 不依赖 conftest 的认证或数据库 fixture（执行接口不需要鉴权）。
- 写快照与读快照前都会把 ``meta.execution_time_ms`` 强制归零，规避毫秒级
  抖动，其余字段全部按字节比对。
- 快照文件统一使用 ``sort_keys=True / ensure_ascii=False / indent=2`` 序列化，
  并通过 ``newline="\n"`` 保留 LF 行尾，避免 Windows 写出 CRLF。
- 设置环境变量 ``UPDATE_ENGINE_SNAPSHOT=1`` 时改为写入快照（用于首次落盘或
  授权刷新）；默认走断言模式。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from httpx import ASGITransport, AsyncClient

from backend.run import app


DATA_DIR = Path(__file__).resolve().parent / "data"
SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots" / "engine"
MINIMAL_XLSX = DATA_DIR / "minimal_rules.xlsx"
SNAPSHOT_ENGINE_XLSX = DATA_DIR / "snapshot_engine.xlsx"
MISSING_SOURCE_PATH = DATA_DIR / "this_path_must_not_exist_snapshot.xlsx"

UPDATE_SNAPSHOT = os.environ.get("UPDATE_ENGINE_SNAPSHOT") == "1"


def _ensure_snapshot_engine_xlsx() -> None:
    """构建 S2 / S3 共用的干净测试数据集。

    - ``values`` sheet 用于 S2 的 ``fixed_value_compare``，仅含整数，避免 NaN
      被 FastAPI 序列化时拒绝。
    - ``items`` sheet 用于 S3 的 ``composite_condition_check``，覆盖 4 类
      assertion 的命中分支。
    """
    if SNAPSHOT_ENGINE_XLSX.exists() and not UPDATE_SNAPSHOT:
        return

    SNAPSHOT_ENGINE_XLSX.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(SNAPSHOT_ENGINE_XLSX, engine="openpyxl") as writer:
        pd.DataFrame({"ID": [1, 2, 2, 3, 5]}).to_excel(
            writer,
            sheet_name="values",
            index=False,
        )
        pd.DataFrame(
            {
                "INT_ID": [100001, 100002, 100003, 100004, 100005, 100006],
                "INT_Faction": [0, 0, 0, 1, 1, 2],
                "INT_Group": [100001, 100001, 999, 200, 300, 400],
            }
        ).to_excel(writer, sheet_name="items", index=False)


def _normalize_response(payload: dict[str, Any]) -> dict[str, Any]:
    """把易抖动字段统一归零，保证快照可重复。"""
    cloned = json.loads(json.dumps(payload))
    meta = cloned.get("meta")
    if isinstance(meta, dict):
        meta["execution_time_ms"] = 0
    return cloned


def _serialize_snapshot(payload: dict[str, Any]) -> str:
    """快照序列化口径：稳定排序 + 中文不转义 + 行尾 LF。"""
    return (
        json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    )


def _snapshot_path(case_id: str) -> Path:
    return SNAPSHOT_DIR / f"{case_id}.json"


def _print_case_summary(case_id: str, payload: dict[str, Any]) -> None:
    """在终端打印每个 case 的关键摘要，便于 PR 审查时一眼看清基线。"""
    code = payload.get("code")
    msg = payload.get("msg")
    meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    abnormal_count = (
        len(data["abnormal_results"])
        if isinstance(data, dict) and isinstance(data.get("abnormal_results"), list)
        else 0
    )
    print(
        f"[engine-snapshot] case={case_id} "
        f"code={code} "
        f"msg={msg!r} "
        f"total_rows_scanned={meta.get('total_rows_scanned')} "
        f"failed_sources={meta.get('failed_sources')} "
        f"abnormal_results={abnormal_count}"
    )


def _assert_or_update_snapshot(case_id: str, response_payload: dict[str, Any]) -> None:
    """根据 ``UPDATE_ENGINE_SNAPSHOT`` 环境变量切换写 / 读模式。"""
    normalized = _normalize_response(response_payload)
    serialized = _serialize_snapshot(normalized)

    snapshot_path = _snapshot_path(case_id)
    if UPDATE_SNAPSHOT:
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(serialized, encoding="utf-8", newline="\n")
    else:
        assert snapshot_path.exists(), (
            f"快照文件缺失：{snapshot_path}。"
            "首次落盘请执行 `UPDATE_ENGINE_SNAPSHOT=1 pytest backend/tests/test_engine_snapshot.py`。"
        )
        expected = snapshot_path.read_text(encoding="utf-8")
        assert serialized == expected, (
            f"快照 {case_id} 与基线不一致；如确认是预期变更，请在评审通过后用 "
            "`UPDATE_ENGINE_SNAPSHOT=1` 重新生成。"
        )

    _print_case_summary(case_id, normalized)


async def _post_execute(payload: dict[str, Any]) -> dict[str, Any]:
    """统一打 ``POST /api/v1/engine/execute``，返回 200 响应体。"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/api/v1/engine/execute", json=payload)

    assert response.status_code == 200, (
        f"engine/execute 非 200：status={response.status_code} body={response.text}"
    )
    return response.json()


# --------------------------------------------------------------------------- #
# S1 主工作台基线：not_null + unique + cross_table_mapping
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_engine_snapshot_s1_main_baseline() -> None:
    """S1：复用 minimal_rules.xlsx，锁住三类基础规则的统一响应基线。"""
    payload = {
        "sources": [
            {
                "id": "src_main",
                "type": "local_excel",
                "path": str(MINIMAL_XLSX),
            }
        ],
        "variables": [
            {
                "tag": "[items-id]",
                "source_id": "src_main",
                "sheet": "items",
                "column": "ID",
            },
            {
                "tag": "[drops-ref]",
                "source_id": "src_main",
                "sheet": "drops",
                "column": "RefID",
            },
        ],
        "rules": [
            {
                "rule_type": "not_null",
                "params": {"target_tags": ["[items-id]"]},
            },
            {
                "rule_type": "unique",
                "params": {"target_tags": ["[items-id]"]},
            },
            {
                "rule_type": "cross_table_mapping",
                "params": {
                    "dict_tag": "[items-id]",
                    "target_tag": "[drops-ref]",
                },
            },
        ],
    }

    response_payload = await _post_execute(payload)
    _assert_or_update_snapshot("S1", response_payload)


# --------------------------------------------------------------------------- #
# S2 固定规则单值比较：fixed_value_compare 的 4 个 operator 各一条
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_engine_snapshot_s2_fixed_value_compare_operators() -> None:
    """S2：通过统一执行接口直接构造固定规则注入形态，覆盖 eq/ne/gt/lt。"""
    _ensure_snapshot_engine_xlsx()

    payload = {
        "sources": [
            {
                "id": "src_snap",
                "type": "local_excel",
                "path": str(SNAPSHOT_ENGINE_XLSX),
            }
        ],
        "variables": [
            {
                "tag": "[snap-values-id]",
                "source_id": "src_snap",
                "sheet": "values",
                "column": "ID",
                "expected_type": "str",
            }
        ],
        "rules": [
            {
                "rule_type": "fixed_value_compare",
                "params": {
                    "target_tag": "[snap-values-id]",
                    "operator": "eq",
                    "expected_value": "1",
                    "rule_name": "ID 必须等于 1",
                    "location": "values -> ID",
                },
            },
            {
                "rule_type": "fixed_value_compare",
                "params": {
                    "target_tag": "[snap-values-id]",
                    "operator": "ne",
                    "expected_value": "2",
                    "rule_name": "ID 不应等于 2",
                    "location": "values -> ID",
                },
            },
            {
                "rule_type": "fixed_value_compare",
                "params": {
                    "target_tag": "[snap-values-id]",
                    "operator": "gt",
                    "expected_value": "1",
                    "rule_name": "ID 必须大于 1",
                    "location": "values -> ID",
                },
            },
            {
                "rule_type": "fixed_value_compare",
                "params": {
                    "target_tag": "[snap-values-id]",
                    "operator": "lt",
                    "expected_value": "3",
                    "rule_name": "ID 必须小于 3",
                    "location": "values -> ID",
                },
            },
        ],
    }

    response_payload = await _post_execute(payload)
    _assert_or_update_snapshot("S2", response_payload)


# --------------------------------------------------------------------------- #
# S3 固定规则组合分支：composite_condition_check 同时覆盖 4 类 assertion
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_engine_snapshot_s3_composite_condition_check() -> None:
    """S3：组合变量条件分支校验，覆盖 global_filters + branch.filters + 4 类 assertion。"""
    _ensure_snapshot_engine_xlsx()

    composite_config = {
        "global_filters": [
            {
                "condition_id": "global-key-gt",
                "field": "__key__",
                "operator": "gt",
                "value_source": "literal",
                "expected_value": "100000",
            }
        ],
        "branches": [
            {
                "branch_id": "branch-faction-zero",
                "filters": [
                    {
                        "condition_id": "branch-1-filter-faction",
                        "field": "INT_Faction",
                        "operator": "eq",
                        "value_source": "literal",
                        "expected_value": "0",
                    }
                ],
                "assertions": [
                    {
                        "condition_id": "branch-1-assert-eq-key",
                        "field": "INT_Group",
                        "operator": "eq",
                        "value_source": "field",
                        "expected_field": "__key__",
                    },
                    {
                        "condition_id": "branch-1-assert-not-null",
                        "field": "INT_Group",
                        "operator": "not_null",
                    },
                    {
                        "condition_id": "branch-1-assert-unique",
                        "field": "INT_Group",
                        "operator": "unique",
                    },
                ],
            },
            {
                "branch_id": "branch-faction-other",
                "filters": [
                    {
                        "condition_id": "branch-2-filter-faction",
                        "field": "INT_Faction",
                        "operator": "ne",
                        "value_source": "literal",
                        "expected_value": "0",
                    }
                ],
                "assertions": [
                    {
                        "condition_id": "branch-2-assert-duplicate",
                        "field": "INT_Group",
                        "operator": "duplicate_required",
                    }
                ],
            },
        ],
    }

    payload = {
        "sources": [
            {
                "id": "src_snap",
                "type": "local_excel",
                "path": str(SNAPSHOT_ENGINE_XLSX),
            }
        ],
        "variables": [
            {
                "tag": "[snap-items-composite]",
                "source_id": "src_snap",
                "sheet": "items",
                "variable_kind": "composite",
                "columns": ["INT_ID", "INT_Faction", "INT_Group"],
                "key_column": "INT_ID",
                "expected_type": "json",
            }
        ],
        "rules": [
            {
                "rule_type": "composite_condition_check",
                "params": {
                    "target_tag": "[snap-items-composite]",
                    "rule_name": "派系与分组组合校验",
                    "composite_config": composite_config,
                },
            }
        ],
    }

    response_payload = await _post_execute(payload)
    _assert_or_update_snapshot("S3", response_payload)


# --------------------------------------------------------------------------- #
# S4 失败 source 降级：依赖失败 source 的规则被跳过，其余规则继续执行
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_engine_snapshot_s4_failed_source_degradation() -> None:
    """S4：一个 source 文件不存在，依赖它的规则被跳过；不依赖它的规则继续执行。"""
    payload = {
        "sources": [
            {
                "id": "src_good",
                "type": "local_excel",
                "path": str(MINIMAL_XLSX),
            },
            {
                "id": "src_bad",
                "type": "local_excel",
                "path": str(MISSING_SOURCE_PATH),
            },
        ],
        "variables": [
            {
                "tag": "[items-id]",
                "source_id": "src_good",
                "sheet": "items",
                "column": "ID",
            },
            {
                "tag": "[bad-col]",
                "source_id": "src_bad",
                "sheet": "items",
                "column": "ID",
            },
        ],
        "rules": [
            {
                "rule_type": "not_null",
                "params": {"target_tags": ["[items-id]"]},
            },
            {
                "rule_type": "not_null",
                "params": {"target_tags": ["[bad-col]"]},
            },
        ],
    }

    response_payload = await _post_execute(payload)
    _assert_or_update_snapshot("S4", response_payload)

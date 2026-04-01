"""执行接口测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from backend.run import app


TEST_DATA_PATH = Path(__file__).resolve().parent / "data" / "minimal_rules.xlsx"


@pytest.mark.anyio
async def test_execute_engine_returns_three_rule_results() -> None:
    """验证一次请求能同时覆盖空值、重复值和跨表映射缺失。"""
    payload = {
        "sources": [
            {
                "id": "src_test",
                "type": "local_excel",
                "path": str(TEST_DATA_PATH),
            }
        ],
        "variables": [
            {
                "tag": "[items-id]",
                "source_id": "src_test",
                "sheet": "items",
                "column": "ID",
            },
            {
                "tag": "[drops-ref]",
                "source_id": "src_test",
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

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/api/v1/engine/execute", json=payload)

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["msg"] == "Execution Completed"
    assert payload["meta"]["total_rows_scanned"] > 0
    assert payload["meta"]["failed_sources"] == []

    abnormal_results = payload["data"]["abnormal_results"]
    assert isinstance(abnormal_results, list)
    assert any(
        item["rule_name"] == "not_null" and item["level"] == "error"
        for item in abnormal_results
    )
    assert any(
        item["rule_name"] == "unique" and item["level"] == "warning"
        for item in abnormal_results
    )
    assert any(
        item["rule_name"] == "cross_table_mapping" and item["level"] == "error"
        for item in abnormal_results
    )

    for item in abnormal_results:
        assert set(item) == {
            "level",
            "rule_name",
            "location",
            "row_index",
            "raw_value",
            "message",
        }


@pytest.mark.anyio
async def test_execute_engine_returns_400_for_unsupported_rule() -> None:
    """验证未注册规则类型会返回 400。"""
    payload = {
        "sources": [
            {
                "id": "src_test",
                "type": "local_excel",
                "path": str(TEST_DATA_PATH),
            }
        ],
        "variables": [
            {
                "tag": "[items-id]",
                "source_id": "src_test",
                "sheet": "items",
                "column": "ID",
            }
        ],
        "rules": [{"rule_type": "missing_rule", "params": {}}],
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/api/v1/engine/execute", json=payload)

    assert response.status_code == 400
    assert "Unsupported rule_type" in response.json()["detail"]


@pytest.mark.anyio
async def test_execute_engine_returns_400_for_invalid_rule_params() -> None:
    """验证非法规则参数会返回 400。"""
    payload = {
        "sources": [
            {
                "id": "src_test",
                "type": "local_excel",
                "path": str(TEST_DATA_PATH),
            }
        ],
        "variables": [
            {
                "tag": "[items-id]",
                "source_id": "src_test",
                "sheet": "items",
                "column": "ID",
            }
        ],
        "rules": [
            {
                "rule_type": "not_null",
                "params": {"target_tags": "not-a-list"},
            }
        ],
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/api/v1/engine/execute", json=payload)

    assert response.status_code == 400
    assert "params.target_tags" in response.json()["detail"]


@pytest.mark.anyio
async def test_execute_engine_returns_400_for_unknown_source_id() -> None:
    """验证变量引用不存在的 source_id 会返回 400。"""
    payload = {
        "sources": [
            {
                "id": "src_test",
                "type": "local_excel",
                "path": str(TEST_DATA_PATH),
            }
        ],
        "variables": [
            {
                "tag": "[bad-source]",
                "source_id": "src_missing",
                "sheet": "items",
                "column": "ID",
            }
        ],
        "rules": [],
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/api/v1/engine/execute", json=payload)

    assert response.status_code == 400
    assert "unknown source_id" in response.json()["detail"]

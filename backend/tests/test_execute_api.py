"""执行接口测试。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.api import source_api
from backend.run import app


TEST_DATA_PATH = Path(__file__).resolve().parent / "data" / "minimal_rules.xlsx"


def _create_composite_test_workbook(target_path: Path) -> Path:
    """创建组合变量测试所需的最小 Excel 文件。"""
    with pd.ExcelWriter(target_path, engine="openpyxl") as writer:
        pd.DataFrame(
            {
                "ID": [1, 2, 3],
                "ItemName": ["Gold", "Wood", "Stone"],
                "Desc": ["黄金+100", "木头+200", "石头+300"],
            }
        ).to_excel(writer, sheet_name="items", index=False)
        pd.DataFrame({"RefID": [1, 2, 9]}).to_excel(
            writer,
            sheet_name="drops",
            index=False,
        )

    return target_path


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


@pytest.mark.anyio
async def test_local_pick_returns_real_selected_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证本地文件选择接口会返回真实路径，不会复制文件。"""

    monkeypatch.setattr(
        source_api,
        "_show_local_file_dialog",
        lambda source_type: str(TEST_DATA_PATH) if source_type == "local_excel" else "",
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/sources/local-pick",
            json={"source_type": "local_excel"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["msg"] == "ok"
    assert payload["data"]["source_type"] == "local_excel"
    assert payload["data"]["selected_path"] == str(TEST_DATA_PATH.resolve())


@pytest.mark.anyio
async def test_local_pick_returns_cancelled_when_user_closes_dialog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证用户取消选择时接口会返回 cancelled。"""

    monkeypatch.setattr(source_api, "_show_local_file_dialog", lambda _source_type: "")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/sources/local-pick",
            json={"source_type": "local_excel"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 204
    assert payload["msg"] == "cancelled"
    assert payload["data"]["selected_path"] == ""


@pytest.mark.anyio
async def test_source_metadata_returns_excel_sheet_and_column_structure() -> None:
    """验证变量池元数据接口会返回 Excel 的 Sheet 与列结构。"""

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/sources/metadata",
            json={
                "id": "src_test",
                "type": "local_excel",
                "path": str(TEST_DATA_PATH),
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["source_id"] == "src_test"
    assert payload["data"]["source_type"] == "local_excel"
    assert payload["data"]["sheets"] == [
        {"name": "items", "columns": ["ID", "Name"]},
        {"name": "drops", "columns": ["RefID"]},
    ]


@pytest.mark.anyio
async def test_source_metadata_rejects_csv_for_variable_pool_dropdown(
    tmp_path: Path,
) -> None:
    """验证 CSV 数据源会被明确拦截。"""

    csv_path = tmp_path / "sample.csv"
    csv_path.write_text("id\n1\n", encoding="utf-8")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/sources/metadata",
            json={
                "id": "src_csv",
                "type": "local_csv",
                "path": str(csv_path),
            },
        )

    assert response.status_code == 400
    assert "变量池下拉提取第一版仅支持 Excel 数据源" in response.json()["detail"]


@pytest.mark.anyio
async def test_column_preview_returns_top_rows_for_variable_detail() -> None:
    """验证列预览接口会返回变量详情页签所需的前几行数据。"""

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/sources/column-preview",
            json={
                "source": {
                    "id": "src_test",
                    "type": "local_excel",
                    "path": str(TEST_DATA_PATH),
                },
                "sheet": "items",
                "column": "ID",
                "limit": 3,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["source_id"] == "src_test"
    assert payload["data"]["sheet"] == "items"
    assert payload["data"]["column"] == "ID"
    assert payload["data"]["preview_limit"] == 3
    assert payload["data"]["total_rows"] == 5
    assert payload["data"]["preview_rows"] == [
        {"row_index": 2, "value": 1},
        {"row_index": 3, "value": 2},
        {"row_index": 4, "value": 2},
    ]


@pytest.mark.anyio
async def test_column_preview_without_limit_returns_full_column_for_detail_dialog() -> None:
    """验证详情弹窗在不传 limit 时会返回当前列的完整预览。"""

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/sources/column-preview",
            json={
                "source": {
                    "id": "src_test",
                    "type": "local_excel",
                    "path": str(TEST_DATA_PATH),
                },
                "sheet": "items",
                "column": "ID",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["source_path"] == str(TEST_DATA_PATH)
    assert payload["data"]["total_rows"] == 5
    assert payload["data"]["loaded_rows"] == 5
    assert payload["data"]["loaded_all_rows"] is True
    assert payload["data"]["preview_limit"] == 5
    assert payload["data"]["preview_rows"] == [
        {"row_index": 2, "value": 1},
        {"row_index": 3, "value": 2},
        {"row_index": 4, "value": 2},
        {"row_index": 5, "value": None},
        {"row_index": 6, "value": "   "},
    ]


@pytest.mark.anyio
async def test_composite_preview_returns_json_mapping_for_same_sheet(
    tmp_path: Path,
) -> None:
    """验证组合变量预览接口会返回 key->object 的完整 JSON 映射。"""

    workbook_path = _create_composite_test_workbook(tmp_path / "composite_preview.xlsx")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/sources/composite-preview",
            json={
                "source": {
                    "id": "src_combo",
                    "type": "local_excel",
                    "path": str(workbook_path),
                },
                "sheet": "items",
                "columns": ["ID", "ItemName", "Desc"],
                "key_column": "ID",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["variable_kind"] == "composite"
    assert payload["data"]["sheet"] == "items"
    assert payload["data"]["columns"] == ["ID", "ItemName", "Desc"]
    assert payload["data"]["key_column"] == "ID"
    assert payload["data"]["total_rows"] == 3
    assert payload["data"]["loaded_rows"] == 3
    assert payload["data"]["mapping"] == {
        "1": {"ItemName": "Gold", "Desc": "黄金+100"},
        "2": {"ItemName": "Wood", "Desc": "木头+200"},
        "3": {"ItemName": "Stone", "Desc": "石头+300"},
    }


@pytest.mark.anyio
async def test_execute_engine_accepts_composite_variable_without_breaking_rules(
    tmp_path: Path,
) -> None:
    """验证 TaskTree 中包含组合变量时，现有三类规则仍可对单变量正常执行。"""

    workbook_path = _create_composite_test_workbook(tmp_path / "composite_execute.xlsx")

    payload = {
        "sources": [
            {
                "id": "src_combo",
                "type": "local_excel",
                "path": str(workbook_path),
            }
        ],
        "variables": [
            {
                "tag": "[items-id]",
                "source_id": "src_combo",
                "sheet": "items",
                "variable_kind": "single",
                "column": "ID",
            },
            {
                "tag": "[drops-ref]",
                "source_id": "src_combo",
                "sheet": "drops",
                "variable_kind": "single",
                "column": "RefID",
            },
            {
                "tag": "[items-json]",
                "source_id": "src_combo",
                "sheet": "items",
                "variable_kind": "composite",
                "columns": ["ID", "ItemName", "Desc"],
                "key_column": "ID",
                "expected_type": "json",
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
    response_payload = response.json()
    assert response_payload["msg"] == "Execution Completed"
    assert response_payload["meta"]["failed_sources"] == []
    assert response_payload["meta"]["total_rows_scanned"] > 0
    assert any(
        item["rule_name"] == "cross_table_mapping" and item["raw_value"] == 9
        for item in response_payload["data"]["abnormal_results"]
    )

"""执行接口测试。"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

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


def _create_dual_composite_test_workbook(target_path: Path) -> Path:
    """创建双组合变量关联比对测试所需的 Excel 文件。"""
    with pd.ExcelWriter(target_path, engine="openpyxl") as writer:
        pd.DataFrame(
            {
                "INT_ID": [10001, 10002],
                "INT_ConditionType": [4, 3],
                "INT_RequireRule": [1, 1],
            }
        ).to_excel(writer, sheet_name="left_items", index=False)
        pd.DataFrame(
            {
                "INT_ID": [10001, 10002],
                "INT_ConditionType": [5, 3],
                "INT_RequireRule": [1, 1],
            }
        ).to_excel(writer, sheet_name="right_items", index=False)

    return target_path


def _create_paginated_test_workbook(target_path: Path) -> Path:
    """创建用于执行结果分页测试的 Excel 文件。"""
    with pd.ExcelWriter(target_path, engine="openpyxl") as writer:
        pd.DataFrame({"ID": list(range(1, 11))}).to_excel(
            writer,
            sheet_name="items",
            index=False,
        )
        pd.DataFrame({"RefID": list(range(1, 46))}).to_excel(
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
async def test_execute_engine_filters_rules_by_selected_ids() -> None:
    """验证 selected_rule_ids 只会执行被勾选的规则。"""
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
                "rule_id": "rule-not-null",
                "rule_type": "not_null",
                "params": {"target_tags": ["[items-id]"]},
            },
            {
                "rule_id": "rule-unique",
                "rule_type": "unique",
                "params": {"target_tags": ["[items-id]"]},
            },
            {
                "rule_id": "rule-cross",
                "rule_type": "cross_table_mapping",
                "params": {
                    "dict_tag": "[items-id]",
                    "target_tag": "[drops-ref]",
                },
            },
        ],
        "selected_rule_ids": ["rule-cross"],
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/api/v1/engine/execute", json=payload)

    assert response.status_code == 200
    abnormal_results = response.json()["data"]["abnormal_results"]
    assert abnormal_results
    assert all(item["rule_name"] == "cross_table_mapping" for item in abnormal_results)


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


def test_show_local_file_dialog_returns_subprocess_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证子进程方案下，正常返回时取真实路径并去除两端空白。"""

    captured_args: dict[str, Any] = {}

    def fake_run(args: list[str], **kwargs: Any) -> SimpleNamespace:
        captured_args["args"] = args
        captured_args["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout=" C:/tmp/example.xlsx \n", stderr="")

    monkeypatch.setattr(source_api.subprocess, "run", fake_run)

    result = source_api._show_local_file_dialog("local_excel")

    assert result == "C:/tmp/example.xlsx"
    assert captured_args["args"][0] == source_api.sys.executable
    assert captured_args["kwargs"]["timeout"] == source_api._PICKER_SUBPROCESS_TIMEOUT_SECONDS
    assert captured_args["kwargs"]["capture_output"] is True


def test_show_local_file_dialog_returns_empty_when_user_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证用户在子进程弹窗中取消时，函数返回空串。"""

    monkeypatch.setattr(
        source_api.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    assert source_api._show_local_file_dialog("local_csv") == ""


def test_show_local_file_dialog_raises_runtime_error_on_subprocess_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证子进程超时会被转换为 RuntimeError，由路由层映射成 500。"""

    def raise_timeout(*_args: Any, **_kwargs: Any) -> SimpleNamespace:
        raise subprocess.TimeoutExpired(cmd="python", timeout=1)

    monkeypatch.setattr(source_api.subprocess, "run", raise_timeout)

    with pytest.raises(RuntimeError, match="超时"):
        source_api._show_local_file_dialog("local_excel")


def test_show_local_file_dialog_raises_runtime_error_on_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证子进程异常退出时，会带上 stderr 抛出 RuntimeError。"""

    monkeypatch.setattr(
        source_api.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="tk init failed",
        ),
    )

    with pytest.raises(RuntimeError, match="tk init failed"):
        source_api._show_local_file_dialog("local_excel")


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


@pytest.mark.anyio
async def test_execute_engine_supports_dual_composite_compare(tmp_path: Path) -> None:
    """验证个人校验执行接口支持双组合变量按 Key 关联后比较字段值。"""
    workbook_path = _create_dual_composite_test_workbook(tmp_path / "dual_composite_rules.xlsx")

    payload = {
        "sources": [
            {
                "id": "src_dual",
                "type": "local_excel",
                "path": str(workbook_path),
            }
        ],
        "variables": [
            {
                "tag": "[left-json]",
                "source_id": "src_dual",
                "sheet": "left_items",
                "variable_kind": "composite",
                "columns": ["INT_ID", "INT_ConditionType", "INT_RequireRule"],
                "key_column": "INT_ID",
                "expected_type": "json",
            },
            {
                "tag": "[right-json]",
                "source_id": "src_dual",
                "sheet": "right_items",
                "variable_kind": "composite",
                "columns": ["INT_ID", "INT_ConditionType", "INT_RequireRule"],
                "key_column": "INT_ID",
                "expected_type": "json",
            },
        ],
        "rules": [
            {
                "rule_id": "rule-dual",
                "rule_type": "dual_composite_compare",
                "params": {
                    "target_tag": "[left-json]",
                    "reference_tag": "[right-json]",
                    "key_check_mode": "baseline_only",
                    "rule_name": "双组合变量比对",
                    "comparisons": [
                        {
                            "comparison_id": "compare-condition-type",
                            "left_field": "INT_ConditionType",
                            "operator": "eq",
                            "right_field": "INT_ConditionType",
                        },
                        {
                            "comparison_id": "compare-require-rule",
                            "left_field": "INT_RequireRule",
                            "operator": "eq",
                            "right_field": "INT_RequireRule",
                        },
                    ],
                },
            }
        ],
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/api/v1/engine/execute", json=payload)

    assert response.status_code == 200
    abnormal_results = response.json()["data"]["abnormal_results"]
    assert len(abnormal_results) == 1
    assert abnormal_results[0]["rule_name"] == "双组合变量比对"
    assert "Key 10001" in abnormal_results[0]["message"]


@pytest.mark.anyio
async def test_execute_engine_persists_latest_result_and_supports_server_side_pagination(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证个人校验执行后会返回第一页结果，并支持按 result_id 翻页。"""
    workbook_path = _create_paginated_test_workbook(tmp_path / "paged_execute.xlsx")
    payload = {
        "sources": [
            {
                "id": "src_test",
                "type": "local_excel",
                "path": str(workbook_path),
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
                "rule_id": "rule-cross",
                "rule_type": "cross_table_mapping",
                "params": {
                    "dict_tag": "[items-id]",
                    "target_tag": "[drops-ref]",
                },
            }
        ],
        "selected_rule_ids": ["rule-cross"],
        "page": 1,
        "size": 20,
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers=auth_headers,
    ) as client:
        execute_response = await client.post("/api/v1/engine/execute", json=payload)

        assert execute_response.status_code == 200
        execute_payload = execute_response.json()
        assert execute_payload["msg"] == "Execution Completed"
        assert execute_payload["meta"]["result_id"] > 0
        assert execute_payload["data"]["page"] == 1
        assert execute_payload["data"]["size"] == 20
        assert execute_payload["data"]["total"] == 35
        assert len(execute_payload["data"]["list"]) == 20
        assert execute_payload["data"]["abnormal_results"] == execute_payload["data"]["list"]

        result_id = execute_payload["meta"]["result_id"]
        page_two_response = await client.get(
            f"/api/v1/engine/results/{result_id}",
            params={"page": 2, "size": 20},
        )

    assert page_two_response.status_code == 200
    page_two_payload = page_two_response.json()
    assert page_two_payload["meta"]["result_id"] == result_id
    assert page_two_payload["data"]["page"] == 2
    assert page_two_payload["data"]["size"] == 20
    assert page_two_payload["data"]["total"] == 35
    assert len(page_two_payload["data"]["list"]) == 15
    assert page_two_payload["data"]["list"][0]["raw_value"] == 31

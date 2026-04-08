"""固定规则模块接口测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.fixed_rules import service as fixed_rules_service
from backend.config import Settings
from backend.run import app


def _create_fixed_rules_workbook(
    target_path: Path,
    values: list[object],
    *,
    desc_prefix: str = "item",
) -> Path:
    """创建固定规则测试所需的最小 Excel 文件。"""
    with pd.ExcelWriter(target_path, engine="openpyxl") as writer:
        pd.DataFrame(
            {
                "INT_ID": values,
                "DESC": [f"{desc_prefix}-{index}" for index, _ in enumerate(values, start=1)],
            }
        ).to_excel(writer, sheet_name="items", index=False)

    return target_path


def _build_v2_payload(
    workbook_path: Path,
    *,
    expected_value: str = "0",
    operator: str = "gt",
) -> dict[str, object]:
    """构建一份最小可用的 v2 固定规则配置。"""
    return {
        "version": 2,
        "configured": True,
        "groups": [
            {"group_id": "ungrouped", "group_name": "未分组", "builtin": True},
            {"group_id": "basic-checks", "group_name": "基础校验", "builtin": False},
        ],
        "rules": [
            {
                "rule_id": "rule-int-id",
                "group_id": "basic-checks",
                "rule_name": "INT_ID 必须满足阈值",
                "binding": {
                    "file_path": str(workbook_path),
                    "sheet": "items",
                    "column": "INT_ID",
                },
                "operator": operator,
                "expected_value": expected_value,
            }
        ],
    }


@pytest.fixture
def isolated_fixed_rules_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """把固定规则配置文件重定向到测试临时目录。"""
    config_path = tmp_path / "fixed-rules" / "default.json"
    monkeypatch.setattr(
        fixed_rules_service,
        "settings",
        Settings(
            fixed_rules_config_path=config_path,
            runtime_dir=tmp_path / ".runtime",
        ),
    )
    return config_path


@pytest.mark.anyio
async def test_get_fixed_rules_config_returns_default_when_missing(
    isolated_fixed_rules_config: Path,
) -> None:
    """验证未保存配置时会返回新版默认空结构。"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/fixed-rules/config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["version"] == 2
    assert payload["data"]["configured"] is False
    assert payload["data"]["groups"] == [
        {
            "group_id": "ungrouped",
            "group_name": "未分组",
            "builtin": True,
        }
    ]
    assert payload["data"]["rules"] == []


@pytest.mark.anyio
async def test_put_fixed_rules_config_persists_valid_v2_payload(
    tmp_path: Path,
    isolated_fixed_rules_config: Path,
) -> None:
    """验证合法的新版固定规则配置可以保存并再次读取。"""
    workbook_path = _create_fixed_rules_workbook(tmp_path / "fixed_rules.xlsx", [1, 2, 3])
    payload = _build_v2_payload(workbook_path)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        save_response = await client.put("/api/v1/fixed-rules/config", json=payload)
        get_response = await client.get("/api/v1/fixed-rules/config")

    assert save_response.status_code == 200
    assert isolated_fixed_rules_config.exists() is True

    get_payload = get_response.json()
    rule = get_payload["data"]["rules"][0]
    assert get_payload["data"]["configured"] is True
    assert rule["binding"]["file_path"] == str(workbook_path.resolve())
    assert rule["binding"]["sheet"] == "items"
    assert rule["binding"]["column"] == "INT_ID"


@pytest.mark.anyio
async def test_get_fixed_rules_config_migrates_legacy_payload(
    tmp_path: Path,
    isolated_fixed_rules_config: Path,
) -> None:
    """验证旧版单文件配置在读取时会自动迁移为规则级绑定。"""
    workbook_path = _create_fixed_rules_workbook(tmp_path / "legacy.xlsx", [1, 2, 3])
    legacy_payload = {
        "version": 1,
        "configured": True,
        "file_path": str(workbook_path),
        "sheet": "items",
        "columns": ["INT_ID"],
        "svn_enabled": False,
        "groups": [{"group_id": "ungrouped", "group_name": "未分组", "builtin": True}],
        "rules": [
            {
                "rule_id": "legacy-rule",
                "group_id": "ungrouped",
                "rule_name": "INT_ID 必须大于 0",
                "column": "INT_ID",
                "operator": "gt",
                "expected_value": "0",
            }
        ],
    }
    isolated_fixed_rules_config.parent.mkdir(parents=True, exist_ok=True)
    isolated_fixed_rules_config.write_text(
        json.dumps(legacy_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/fixed-rules/config")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["version"] == 2
    assert payload["rules"][0]["binding"] == {
        "file_path": str(workbook_path.resolve()),
        "sheet": "items",
        "column": "INT_ID",
    }


@pytest.mark.anyio
async def test_put_fixed_rules_config_rejects_unknown_column(
    tmp_path: Path,
    isolated_fixed_rules_config: Path,
) -> None:
    """验证规则绑定引用不存在列时会返回 400。"""
    workbook_path = _create_fixed_rules_workbook(tmp_path / "invalid_rule.xlsx", [1, 2, 3])
    payload = _build_v2_payload(workbook_path)
    payload["rules"][0]["binding"]["column"] = "UNKNOWN_COL"

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.put("/api/v1/fixed-rules/config", json=payload)

    assert response.status_code == 400
    assert "UNKNOWN_COL" in response.json()["detail"]


@pytest.mark.anyio
async def test_execute_fixed_rules_passes_gt_zero_rule(
    tmp_path: Path,
    isolated_fixed_rules_config: Path,
) -> None:
    """验证 `INT_ID > 0` 的固定规则在合法数据上返回 0 条异常。"""
    workbook_path = _create_fixed_rules_workbook(tmp_path / "gt_zero.xlsx", [1, 2, 3])
    payload = _build_v2_payload(workbook_path, expected_value="0", operator="gt")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        save_response = await client.put("/api/v1/fixed-rules/config", json=payload)
        execute_response = await client.post("/api/v1/fixed-rules/execute")

    assert save_response.status_code == 200
    assert execute_response.status_code == 200
    execute_payload = execute_response.json()
    assert execute_payload["msg"] == "Execution Completed"
    assert execute_payload["meta"]["total_rows_scanned"] == 3
    assert execute_payload["data"]["abnormal_results"] == []


@pytest.mark.anyio
async def test_execute_fixed_rules_reports_threshold_and_non_numeric_rows(
    tmp_path: Path,
    isolated_fixed_rules_config: Path,
) -> None:
    """验证固定规则会返回比较失败和非数值异常。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "gt_threshold.xlsx",
        [1, "oops", 5],
    )
    payload = _build_v2_payload(workbook_path, expected_value="2", operator="gt")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        await client.put("/api/v1/fixed-rules/config", json=payload)
        execute_response = await client.post("/api/v1/fixed-rules/execute")

    assert execute_response.status_code == 200
    abnormal_results = execute_response.json()["data"]["abnormal_results"]
    assert any(item["raw_value"] == 1 for item in abnormal_results)
    assert any(item["raw_value"] == "oops" for item in abnormal_results)
    assert any("数值" in item["message"] for item in abnormal_results)
    assert all(item["location"] == "items -> INT_ID" for item in abnormal_results)


@pytest.mark.anyio
async def test_execute_fixed_rules_supports_multiple_bound_files_in_one_run(
    tmp_path: Path,
    isolated_fixed_rules_config: Path,
) -> None:
    """验证多文件规则可以在一次执行中聚合运行。"""
    workbook_a = _create_fixed_rules_workbook(tmp_path / "items_a.xlsx", [1, 2, 3], desc_prefix="a")
    workbook_b = _create_fixed_rules_workbook(tmp_path / "items_b.xlsx", [10, 20, 30], desc_prefix="b")
    payload = {
        "version": 2,
        "configured": True,
        "groups": [
            {"group_id": "ungrouped", "group_name": "未分组", "builtin": True},
            {"group_id": "mixed", "group_name": "混合校验", "builtin": False},
        ],
        "rules": [
            {
                "rule_id": "rule-a",
                "group_id": "mixed",
                "rule_name": "A 文件 INT_ID > 0",
                "binding": {
                    "file_path": str(workbook_a),
                    "sheet": "items",
                    "column": "INT_ID",
                },
                "operator": "gt",
                "expected_value": "0",
            },
            {
                "rule_id": "rule-b",
                "group_id": "mixed",
                "rule_name": "B 文件 DESC 必须等于 b-1",
                "binding": {
                    "file_path": str(workbook_b),
                    "sheet": "items",
                    "column": "DESC",
                },
                "operator": "eq",
                "expected_value": "b-1",
            },
        ],
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        await client.put("/api/v1/fixed-rules/config", json=payload)
        execute_response = await client.post("/api/v1/fixed-rules/execute")

    assert execute_response.status_code == 200
    execute_payload = execute_response.json()
    abnormal_results = execute_payload["data"]["abnormal_results"]
    assert execute_payload["meta"]["total_rows_scanned"] == 6
    assert any(item["rule_name"] == "B 文件 DESC 必须等于 b-1" for item in abnormal_results)
    assert all(item["rule_name"] != "A 文件 INT_ID > 0" for item in abnormal_results)


@pytest.mark.anyio
async def test_fixed_rules_svn_update_deduplicates_working_copies(
    tmp_path: Path,
    isolated_fixed_rules_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证 SVN 更新会按目录去重后统一执行。"""
    dir_a = tmp_path / "svn-a"
    dir_b = tmp_path / "svn-b"
    dir_a.mkdir()
    dir_b.mkdir()
    workbook_a1 = _create_fixed_rules_workbook(dir_a / "items_a1.xlsx", [1, 2, 3])
    workbook_a2 = _create_fixed_rules_workbook(dir_a / "items_a2.xlsx", [4, 5, 6])
    workbook_b = _create_fixed_rules_workbook(dir_b / "items_b.xlsx", [7, 8, 9])
    payload = {
        "version": 2,
        "configured": True,
        "groups": [{"group_id": "ungrouped", "group_name": "未分组", "builtin": True}],
        "rules": [
            {
                "rule_id": "rule-a1",
                "group_id": "ungrouped",
                "rule_name": "A1",
                "binding": {
                    "file_path": str(workbook_a1),
                    "sheet": "items",
                    "column": "INT_ID",
                },
                "operator": "gt",
                "expected_value": "0",
            },
            {
                "rule_id": "rule-a2",
                "group_id": "ungrouped",
                "rule_name": "A2",
                "binding": {
                    "file_path": str(workbook_a2),
                    "sheet": "items",
                    "column": "INT_ID",
                },
                "operator": "gt",
                "expected_value": "0",
            },
            {
                "rule_id": "rule-b",
                "group_id": "ungrouped",
                "rule_name": "B",
                "binding": {
                    "file_path": str(workbook_b),
                    "sheet": "items",
                    "column": "INT_ID",
                },
                "operator": "gt",
                "expected_value": "0",
            },
        ],
    }
    called_working_copies: list[str] = []

    def fake_update(working_copy: Path) -> dict[str, str]:
        called_working_copies.append(str(working_copy))
        return {
            "output": f"updated:{working_copy.name}",
            "used_executable": "svn.exe",
        }

    monkeypatch.setattr(fixed_rules_service, "update_svn_working_copy", fake_update)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        await client.put("/api/v1/fixed-rules/config", json=payload)
        response = await client.post("/api/v1/fixed-rules/svn-update")

    assert response.status_code == 200
    response_payload = response.json()["data"]
    assert response_payload["total_paths"] == 2
    assert response_payload["updated_paths"] == 2
    assert len(called_working_copies) == 2
    assert str(dir_a) in called_working_copies
    assert str(dir_b) in called_working_copies


@pytest.mark.anyio
async def test_fixed_rules_svn_update_returns_clear_error_when_cli_missing(
    tmp_path: Path,
    isolated_fixed_rules_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证当前环境缺少 svn CLI 时会返回明确提示。"""
    workbook_path = _create_fixed_rules_workbook(tmp_path / "svn_sample.xlsx", [1, 2, 3])
    payload = _build_v2_payload(workbook_path)

    def raise_missing_cli(_: Path) -> dict[str, str]:
        raise NotImplementedError(
            "当前环境未检测到 svn 命令，请先安装 SVN CLI，或在后端配置中指定 svn 可执行文件路径。"
        )

    monkeypatch.setattr(fixed_rules_service, "update_svn_working_copy", raise_missing_cli)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        await client.put("/api/v1/fixed-rules/config", json=payload)
        response = await client.post("/api/v1/fixed-rules/svn-update")

    assert response.status_code == 400
    assert "svn 命令" in response.json()["detail"]

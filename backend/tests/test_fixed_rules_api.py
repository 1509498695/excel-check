"""固定规则模块接口测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.fixed_rules import service as fixed_rules_service
from backend.run import app
from backend.tests.conftest import seed_fixed_rules_config


def _auth_client_ctx(headers: dict[str, str]):
    """返回带认证 headers 的 AsyncClient 上下文。"""
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers=headers,
    )


def _create_fixed_rules_workbook(
    target_path: Path,
    columns: dict[str, list[object]],
    *,
    sheet_name: str = "items",
) -> Path:
    """创建固定规则测试所需的最小 Excel 文件。"""
    with pd.ExcelWriter(target_path, engine="openpyxl") as writer:
        pd.DataFrame(columns).to_excel(writer, sheet_name=sheet_name, index=False)

    return target_path


def _create_fixed_rules_paged_workbook(target_path: Path) -> Path:
    """创建用于项目校验结果分页测试的 Excel 文件。"""
    dict_values = list(range(1, 11))
    repeated_dict_values = [dict_values[index % len(dict_values)] for index in range(45)]
    with pd.ExcelWriter(target_path, engine="openpyxl") as writer:
        pd.DataFrame(
            {
                "INT_ID": list(range(1, 46)),
                "DICT_ID": repeated_dict_values,
            }
        ).to_excel(writer, sheet_name="items", index=False)

    return target_path


def _build_single_tag(source_id: str, sheet: str, column: str) -> str:
    return f"[{source_id}-{sheet}-{column}]"


def _build_composite_tag(source_id: str, sheet: str, tag: str) -> str:
    return f"[{source_id}-{sheet}-{tag}]"


def _build_composite_variable(
    source_id: str = "items-source",
    *,
    tag: str = "faction-group-map",
    append_index_to_key: bool = False,
) -> dict[str, object]:
    return {
        "tag": _build_composite_tag(source_id, "items", tag),
        "source_id": source_id,
        "sheet": "items",
        "variable_kind": "composite",
        "columns": ["INT_ID", "INT_Faction", "INT_Group"],
        "key_column": "INT_ID",
        "append_index_to_key": append_index_to_key,
        "expected_type": "json",
    }


def _build_composite_rule(
    target_variable_tag: str,
    *,
    rule_id: str = "rule-composite-branch",
    group_id: str = "basic-checks",
    rule_name: str = "组合变量条件分支校验",
) -> dict[str, object]:
    return {
        "rule_id": rule_id,
        "group_id": group_id,
        "rule_name": rule_name,
        "target_variable_tag": target_variable_tag,
        "rule_type": "composite_condition_check",
        "composite_config": {
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
                            "condition_id": "branch-1-filter",
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
                            "condition_id": "branch-2-filter",
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
        },
    }


def _build_sequence_rule(
    target_variable_tag: str,
    *,
    rule_id: str = "rule-sequence",
    rule_name: str = "INT_ID 顺序校验",
    direction: str = "asc",
    step: str = "1",
    start_mode: str = "auto",
    start_value: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "rule_id": rule_id,
        "group_id": "basic-checks",
        "rule_name": rule_name,
        "target_variable_tag": target_variable_tag,
        "rule_type": "sequence_order_check",
        "sequence_direction": direction,
        "sequence_step": step,
        "sequence_start_mode": start_mode,
    }
    if start_value is not None:
        payload["sequence_start_value"] = start_value
    return payload


def _build_regex_rule(
    target_variable_tag: str,
    *,
    rule_id: str = "rule-regex",
    rule_name: str = "字段正则校验",
    pattern: str = r"(?:\d+(?:-\d+)?:(?:0|1))(?:;\d+(?:-\d+)?:(?:0|1))*",
) -> dict[str, object]:
    return {
        "rule_id": rule_id,
        "group_id": "basic-checks",
        "rule_name": rule_name,
        "target_variable_tag": target_variable_tag,
        "rule_type": "regex_check",
        "expected_value": pattern,
    }


def _create_dual_composite_workbook(
    target_path: Path,
    *,
    left_rows: dict[str, list[object]],
    right_rows: dict[str, list[object]],
) -> Path:
    """创建双组合变量比对测试所需的最小 Excel 文件。"""
    with pd.ExcelWriter(target_path, engine="openpyxl") as writer:
        pd.DataFrame(left_rows).to_excel(writer, sheet_name="left_items", index=False)
        pd.DataFrame(right_rows).to_excel(writer, sheet_name="right_items", index=False)

    return target_path


def _build_dual_composite_rule(
    target_variable_tag: str,
    reference_variable_tag: str,
    *,
    key_check_mode: str = "baseline_only",
    comparisons: list[dict[str, object]] | None = None,
    rule_id: str = "rule-dual-composite-compare",
    group_id: str = "basic-checks",
    rule_name: str = "双组合变量比对",
) -> dict[str, object]:
    return {
        "rule_id": rule_id,
        "group_id": group_id,
        "rule_name": rule_name,
        "target_variable_tag": target_variable_tag,
        "reference_variable_tag": reference_variable_tag,
        "rule_type": "dual_composite_compare",
        "key_check_mode": key_check_mode,
        "comparisons": comparisons
        if comparisons is not None
        else [
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
    }


def _build_v4_payload(
    workbook_path: Path,
    *,
    source_id: str = "items-source",
    groups: list[dict[str, object]] | None = None,
    variables: list[dict[str, object]] | None = None,
    rules: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """构建一份最小可用的 v4 固定规则配置。"""
    int_id_tag = _build_single_tag(source_id, "items", "INT_ID")
    desc_tag = _build_single_tag(source_id, "items", "DESC")

    return {
        "version": 4,
        "configured": True,
        "sources": [
            {
                "id": source_id,
                "type": "local_excel",
                "path": str(workbook_path),
                "pathOrUrl": str(workbook_path),
            }
        ],
        "variables": variables
        if variables is not None
        else [
            {
                "tag": int_id_tag,
                "source_id": source_id,
                "sheet": "items",
                "variable_kind": "single",
                "column": "INT_ID",
                "expected_type": "str",
            },
            {
                "tag": desc_tag,
                "source_id": source_id,
                "sheet": "items",
                "variable_kind": "single",
                "column": "DESC",
                "expected_type": "str",
            },
        ],
        "groups": groups
        if groups is not None
        else [
            {"group_id": "ungrouped", "group_name": "未分组", "builtin": True},
            {"group_id": "basic-checks", "group_name": "基础校验", "builtin": False},
        ],
        "rules": rules
        if rules is not None
        else [
            {
                "rule_id": "rule-int-id",
                "group_id": "basic-checks",
                "rule_name": "INT_ID 必须大于 0",
                "target_variable_tag": int_id_tag,
                "rule_type": "fixed_value_compare",
                "operator": "gt",
                "expected_value": "0",
            }
        ],
    }



@pytest.mark.anyio
async def test_get_fixed_rules_config_returns_default_when_missing(
    auth_headers: dict[str, str],
) -> None:
    """验证未保存配置时会返回 v5 默认空结构。"""
    async with _auth_client_ctx(auth_headers) as client:
        response = await client.get("/api/v1/fixed-rules/config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["version"] == 5
    assert payload["data"]["configured"] is False
    assert payload["data"]["sources"] == []
    assert payload["data"]["variables"] == []
    assert payload["data"]["groups"] == [
        {
            "group_id": "ungrouped",
            "group_name": "未分组",
            "builtin": True,
        }
    ]
    assert payload["data"]["rules"] == []


@pytest.mark.anyio
async def test_get_fixed_rules_config_returns_issues_when_source_path_missing(
    tmp_path: Path,
    auth_headers: dict[str, str],
    test_project_id: int,
) -> None:
    """验证读取失效本地路径时仍返回配置和 config_issues。"""
    missing_workbook_path = tmp_path / "missing.xlsx"
    payload = _build_v4_payload(missing_workbook_path)
    await seed_fixed_rules_config(payload, test_project_id)

    async with _auth_client_ctx(auth_headers) as client:
        response = await client.get("/api/v1/fixed-rules/config")

    assert response.status_code == 200
    response_payload = response.json()
    assert response_payload["data"]["sources"][0]["id"] == "items-source"
    assert response_payload["data"]["variables"][0]["tag"] == "[items-source-items-INT_ID]"
    assert response_payload["meta"]["config_issues"]
    assert any(
        issue["source_id"] == "items-source"
        and str(missing_workbook_path.resolve()) in issue["message"]
        for issue in response_payload["meta"]["config_issues"]
    )


@pytest.mark.anyio
async def test_get_fixed_rules_config_returns_source_issue_without_variables(
    tmp_path: Path,
    auth_headers: dict[str, str],
    test_project_id: int,
) -> None:
    """验证仅保存数据源时，失效路径也会返回 source 级 config_issues。"""
    missing_workbook_path = tmp_path / "missing-source-only.xlsx"
    payload = _build_v4_payload(
        missing_workbook_path,
        variables=[],
        rules=[],
        groups=[{"group_id": "ungrouped", "group_name": "未分组", "builtin": True}],
    )
    await seed_fixed_rules_config(payload, test_project_id)

    async with _auth_client_ctx(auth_headers) as client:
        response = await client.get("/api/v1/fixed-rules/config")

    assert response.status_code == 200
    response_payload = response.json()
    assert response_payload["data"]["sources"][0]["id"] == "items-source"
    assert response_payload["data"]["variables"] == []
    assert response_payload["meta"]["config_issues"]
    assert any(
        issue["source_id"] == "items-source"
        and str(missing_workbook_path.resolve()) in issue["message"]
        for issue in response_payload["meta"]["config_issues"]
    )


@pytest.mark.anyio
async def test_put_and_execute_fixed_rules_still_fail_when_source_path_missing(
    tmp_path: Path,
    auth_headers: dict[str, str],
    test_project_id: int,
) -> None:
    """验证失效路径可保存并返回 config_issues，但执行仍会失败。"""
    missing_workbook_path = tmp_path / "missing-source-only.xlsx"
    payload = _build_v4_payload(
        missing_workbook_path,
        variables=[],
        rules=[],
        groups=[{"group_id": "ungrouped", "group_name": "未分组", "builtin": True}],
    )
    await seed_fixed_rules_config(payload, test_project_id)

    async with _auth_client_ctx(auth_headers) as client:
        save_response = await client.put("/api/v1/fixed-rules/config", json=payload)
        execute_response = await client.post("/api/v1/fixed-rules/execute")

    assert save_response.status_code == 200
    assert execute_response.status_code == 400
    save_payload = save_response.json()
    assert save_payload["meta"]["config_issues"]
    assert any(
        issue["source_id"] == "items-source"
        for issue in save_payload["meta"]["config_issues"]
    )
    assert "items-source" in execute_response.json()["detail"]


@pytest.mark.anyio
async def test_put_fixed_rules_config_persists_valid_v4_payload(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证合法的 v4 固定规则配置可以保存并再次读取。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "fixed_rules.xlsx",
        {"INT_ID": [1, 2, 3], "DESC": ["a", "b", "c"]},
    )
    payload = _build_v4_payload(workbook_path)

    async with _auth_client_ctx(auth_headers) as client:
        save_response = await client.put("/api/v1/fixed-rules/config", json=payload)
        get_response = await client.get("/api/v1/fixed-rules/config")

    assert save_response.status_code == 200

    get_payload = get_response.json()["data"]
    assert get_payload["version"] == 5
    assert get_payload["configured"] is True
    assert get_payload["sources"][0]["id"] == "items-source"
    assert get_payload["variables"][0]["tag"] == "[items-source-items-INT_ID]"
    assert get_payload["rules"][0]["target_variable_tag"] == "[items-source-items-INT_ID]"


@pytest.mark.anyio
async def test_put_fixed_rules_config_supports_cross_table_mapping_round_trip(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证固定规则页可保存并读取“包含 (in)”映射后的 cross_table_mapping 规则。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "fixed_rules_in.xlsx",
        {"INT_ID": [1, 2, 4], "DICT_ID": [1, 2, 3]},
    )
    target_tag = _build_single_tag("items-source", "items", "INT_ID")
    dict_tag = _build_single_tag("items-source", "items", "DICT_ID")
    payload = _build_v4_payload(
        workbook_path,
        variables=[
            {
                "tag": target_tag,
                "source_id": "items-source",
                "sheet": "items",
                "variable_kind": "single",
                "column": "INT_ID",
                "expected_type": "str",
            },
            {
                "tag": dict_tag,
                "source_id": "items-source",
                "sheet": "items",
                "variable_kind": "single",
                "column": "DICT_ID",
                "expected_type": "str",
            },
        ],
        rules=[
            {
                "rule_id": "rule-int-id-in-dict",
                "group_id": "basic-checks",
                "rule_name": "INT_ID 必须包含于 DICT_ID",
                "target_variable_tag": target_tag,
                "rule_type": "cross_table_mapping",
                "reference_variable_tag": dict_tag,
            }
        ],
    )

    async with _auth_client_ctx(auth_headers) as client:
        save_response = await client.put("/api/v1/fixed-rules/config", json=payload)
        get_response = await client.get("/api/v1/fixed-rules/config")

    assert save_response.status_code == 200
    get_payload = get_response.json()["data"]
    assert get_payload["rules"][0]["rule_type"] == "cross_table_mapping"
    assert get_payload["rules"][0]["reference_variable_tag"] == dict_tag


@pytest.mark.anyio
async def test_put_fixed_rules_config_supports_sequence_order_check_round_trip(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证顺序校验规则可以保存并再次读取。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "sequence_round_trip.xlsx",
        {"INT_ID": [10, 11, 12], "DESC": ["a", "b", "c"]},
    )
    target_tag = _build_single_tag("items-source", "items", "INT_ID")
    payload = _build_v4_payload(
        workbook_path,
        rules=[
          _build_sequence_rule(
              target_tag,
              direction="desc",
              step="5",
              start_mode="manual",
              start_value="100",
          )
        ],
    )

    async with _auth_client_ctx(auth_headers) as client:
        save_response = await client.put("/api/v1/fixed-rules/config", json=payload)
        get_response = await client.get("/api/v1/fixed-rules/config")

    assert save_response.status_code == 200
    get_payload = get_response.json()["data"]
    rule = get_payload["rules"][0]
    assert rule["rule_type"] == "sequence_order_check"
    assert rule["sequence_direction"] == "desc"
    assert rule["sequence_step"] == "5"
    assert rule["sequence_start_mode"] == "manual"
    assert rule["sequence_start_value"] == "100"


@pytest.mark.anyio
async def test_put_fixed_rules_config_supports_regex_check_round_trip(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证正则校验规则可以保存并再次读取。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "regex_round_trip.xlsx",
        {
            "DESC": [
                "11005:1;457-458:1;460:1;489-1500:1;488:0",
                "bad-format",
            ]
        },
    )
    target_tag = _build_single_tag("items-source", "items", "DESC")
    payload = _build_v4_payload(
        workbook_path,
        variables=[
            {
                "tag": target_tag,
                "source_id": "items-source",
                "sheet": "items",
                "variable_kind": "single",
                "column": "DESC",
                "expected_type": "str",
            }
        ],
        rules=[
            _build_regex_rule(
                target_tag,
                rule_name="DESC 正则校验",
            )
        ],
    )

    async with _auth_client_ctx(auth_headers) as client:
        save_response = await client.put("/api/v1/fixed-rules/config", json=payload)
        get_response = await client.get("/api/v1/fixed-rules/config")

    assert save_response.status_code == 200
    rule = get_response.json()["data"]["rules"][0]
    assert rule["rule_type"] == "regex_check"
    assert rule["expected_value"] == r"(?:\d+(?:-\d+)?:(?:0|1))(?:;\d+(?:-\d+)?:(?:0|1))*"


@pytest.mark.anyio
async def test_get_fixed_rules_config_migrates_legacy_payload(
    tmp_path: Path,
    auth_headers: dict[str, str],
    test_project_id: int,
) -> None:
    """验证旧版全局单文件配置读取时会自动迁移到 v4。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "legacy.xlsx",
        {"INT_ID": [1, 2, 3], "DESC": ["a", "b", "c"]},
    )
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
    await seed_fixed_rules_config(legacy_payload, test_project_id)

    async with _auth_client_ctx(auth_headers) as client:
        response = await client.get("/api/v1/fixed-rules/config")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["version"] == 5
    assert len(payload["sources"]) == 1
    assert payload["sources"][0]["path"] == str(workbook_path.resolve())
    assert len(payload["variables"]) == 1
    assert payload["rules"][0]["rule_type"] == "fixed_value_compare"
    assert payload["rules"][0]["target_variable_tag"] == payload["variables"][0]["tag"]


@pytest.mark.anyio
async def test_get_fixed_rules_config_migrates_v3_binding_rules(
    tmp_path: Path,
    auth_headers: dict[str, str],
    test_project_id: int,
) -> None:
    """验证旧版 version=3 binding 规则会自动迁移到变量引用结构。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "v3.xlsx",
        {"INT_ID": [1, 2, 3], "DESC": ["a", "b", "c"]},
    )
    v3_payload = {
        "version": 3,
        "configured": True,
        "groups": [{"group_id": "ungrouped", "group_name": "未分组", "builtin": True}],
        "rules": [
            {
                "rule_id": "rule-int-id",
                "group_id": "ungrouped",
                "rule_name": "INT_ID 必须大于 0",
                "binding": {
                    "file_path": str(workbook_path),
                    "sheet": "items",
                    "column": "INT_ID",
                },
                "rule_type": "fixed_value_compare",
                "operator": "gt",
                "expected_value": "0",
            }
        ],
    }
    await seed_fixed_rules_config(v3_payload, test_project_id)

    async with _auth_client_ctx(auth_headers) as client:
        response = await client.get("/api/v1/fixed-rules/config")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["version"] == 5
    assert payload["sources"][0]["id"] == "v3"
    assert payload["variables"][0]["column"] == "INT_ID"
    assert payload["rules"][0]["target_variable_tag"] == "[v3-items-INT_ID]"


@pytest.mark.anyio
async def test_put_fixed_rules_config_rejects_unknown_target_variable(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证规则引用不存在变量时会返回 400。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "invalid_rule.xlsx",
        {"INT_ID": [1, 2, 3], "DESC": ["a", "b", "c"]},
    )
    payload = _build_v4_payload(workbook_path)
    payload["rules"][0]["target_variable_tag"] = "[missing-tag]"

    async with _auth_client_ctx(auth_headers) as client:
        response = await client.put("/api/v1/fixed-rules/config", json=payload)

    assert response.status_code == 400
    assert "missing-tag" in response.json()["detail"]


@pytest.mark.anyio
async def test_put_fixed_rules_config_rejects_composite_variable_binding(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证固定规则只能绑定单个变量。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "composite_only.xlsx",
        {"INT_ID": [1, 2, 3], "DESC": ["a", "b", "c"], "NAME": ["x", "y", "z"]},
    )
    payload = _build_v4_payload(
        workbook_path,
        variables=[
            {
                "tag": "[items-source-items-INT_ID-mapping]",
                "source_id": "items-source",
                "sheet": "items",
                "variable_kind": "composite",
                "columns": ["INT_ID", "DESC", "NAME"],
                "key_column": "INT_ID",
                "expected_type": "json",
            }
        ],
        rules=[
            {
                "rule_id": "rule-composite",
                "group_id": "basic-checks",
                "rule_name": "组合变量不能直接做固定规则",
                "target_variable_tag": "[items-source-items-INT_ID-mapping]",
                "rule_type": "not_null",
            }
        ],
    )

    async with _auth_client_ctx(auth_headers) as client:
        response = await client.put("/api/v1/fixed-rules/config", json=payload)

    assert response.status_code == 400
    assert "rule-composite" in response.json()["detail"]


@pytest.mark.anyio
async def test_put_fixed_rules_config_rejects_sequence_rule_bound_to_composite_variable(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证顺序校验只能绑定单变量。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "sequence_composite_invalid.xlsx",
        {"INT_ID": [1, 2, 3], "DESC": ["a", "b", "c"], "NAME": ["x", "y", "z"]},
    )
    composite_tag = "[items-source-items-INT_ID-mapping]"
    payload = _build_v4_payload(
        workbook_path,
        variables=[
            {
                "tag": composite_tag,
                "source_id": "items-source",
                "sheet": "items",
                "variable_kind": "composite",
                "columns": ["INT_ID", "DESC", "NAME"],
                "key_column": "INT_ID",
                "expected_type": "json",
            }
        ],
        rules=[_build_sequence_rule(composite_tag)],
    )

    async with _auth_client_ctx(auth_headers) as client:
        response = await client.put("/api/v1/fixed-rules/config", json=payload)

    assert response.status_code == 400
    assert "rule-sequence" in response.json()["detail"]


@pytest.mark.anyio
async def test_put_fixed_rules_config_rejects_sequence_rule_with_invalid_step(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证顺序校验的步长必须是大于 0 的数字。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "sequence_invalid_step.xlsx",
        {"INT_ID": [1, 2, 3], "DESC": ["a", "b", "c"]},
    )
    target_tag = _build_single_tag("items-source", "items", "INT_ID")
    payload = _build_v4_payload(
        workbook_path,
        rules=[_build_sequence_rule(target_tag, step="0")],
    )

    async with _auth_client_ctx(auth_headers) as client:
        response = await client.put("/api/v1/fixed-rules/config", json=payload)

    assert response.status_code == 400
    assert "step" in response.json()["detail"]


@pytest.mark.anyio
async def test_put_fixed_rules_config_rejects_sequence_rule_without_manual_start_value(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证手动起始模式必须填写起始值。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "sequence_missing_start.xlsx",
        {"INT_ID": [1, 2, 3], "DESC": ["a", "b", "c"]},
    )
    target_tag = _build_single_tag("items-source", "items", "INT_ID")
    payload = _build_v4_payload(
        workbook_path,
        rules=[_build_sequence_rule(target_tag, start_mode="manual")],
    )

    async with _auth_client_ctx(auth_headers) as client:
        response = await client.put("/api/v1/fixed-rules/config", json=payload)

    assert response.status_code == 400
    assert "start_value" in response.json()["detail"]


@pytest.mark.anyio
async def test_put_fixed_rules_config_accepts_composite_rule_and_round_trips(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "composite_round_trip.xlsx",
        {
            "INT_ID": [100001, 100002, 100003],
            "INT_Faction": [0, 1, 1],
            "INT_Group": [100001, 200, 200],
        },
    )
    composite_variable = _build_composite_variable()
    composite_rule = _build_composite_rule(composite_variable["tag"])
    payload = _build_v4_payload(
        workbook_path,
        variables=[composite_variable],
        rules=[composite_rule],
    )

    async with _auth_client_ctx(auth_headers) as client:
        save_response = await client.put("/api/v1/fixed-rules/config", json=payload)
        get_response = await client.get("/api/v1/fixed-rules/config")

    assert save_response.status_code == 200
    response_payload = get_response.json()["data"]
    assert response_payload["rules"][0]["rule_type"] == "composite_condition_check"
    assert response_payload["rules"][0]["target_variable_tag"] == composite_variable["tag"]
    assert response_payload["rules"][0]["composite_config"]["branches"][0]["assertions"][0]["expected_field"] == "__key__"


@pytest.mark.anyio
async def test_put_fixed_rules_config_accepts_composite_contains_filter_round_trip(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证组合条件校验支持字符串包含筛选。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "composite_contains_round_trip.xlsx",
        {
            "INT_ID": [100001, 100002, 100003],
            "STR_MapType": ["ABCD", "ACD", "BCD"],
            "INT_Faction": [0, 1, 0],
            "INT_Group": [100001, 200, 100003],
        },
    )
    composite_variable = {
        "tag": _build_composite_tag("items-source", "items", "contains-map"),
        "source_id": "items-source",
        "sheet": "items",
        "variable_kind": "composite",
        "columns": ["INT_ID", "STR_MapType", "INT_Faction", "INT_Group"],
        "key_column": "INT_ID",
        "expected_type": "json",
    }
    composite_rule = _build_composite_rule(
        composite_variable["tag"],
        rule_name="组合条件包含筛选",
    )
    composite_rule["composite_config"]["global_filters"] = [
        {
            "condition_id": "global-maptype-contains",
            "field": "STR_MapType",
            "operator": "contains",
            "value_source": "literal",
            "expected_value": "B",
        }
    ]
    composite_rule["composite_config"]["branches"] = [
        {
            "branch_id": "branch-maptype",
            "filters": [
                {
                    "condition_id": "branch-maptype-contains",
                    "field": "STR_MapType",
                    "operator": "contains",
                    "value_source": "literal",
                    "expected_value": "C",
                }
            ],
            "assertions": [
                {
                    "condition_id": "branch-maptype-not-null",
                    "field": "INT_Group",
                    "operator": "not_null",
                }
            ],
        }
    ]
    payload = _build_v4_payload(
        workbook_path,
        variables=[composite_variable],
        rules=[composite_rule],
    )

    async with _auth_client_ctx(auth_headers) as client:
        save_response = await client.put("/api/v1/fixed-rules/config", json=payload)
        get_response = await client.get("/api/v1/fixed-rules/config")

    assert save_response.status_code == 200
    rule = get_response.json()["data"]["rules"][0]
    assert rule["composite_config"]["global_filters"][0]["operator"] == "contains"
    assert rule["composite_config"]["global_filters"][0]["expected_value"] == "B"
    assert rule["composite_config"]["branches"][0]["filters"][0]["operator"] == "contains"


@pytest.mark.anyio
async def test_put_fixed_rules_config_accepts_composite_not_contains_filter_round_trip(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证组合条件校验支持字符串不包含筛选。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "composite_not_contains_round_trip.xlsx",
        {
            "INT_ID": [100001, 100002, 100003],
            "STR_MapType": ["ABCD", "ACD", "XYZ"],
            "INT_Faction": [0, 1, 0],
            "INT_Group": [100001, 200, 100003],
        },
    )
    composite_variable = {
        "tag": _build_composite_tag("items-source", "items", "not-contains-map"),
        "source_id": "items-source",
        "sheet": "items",
        "variable_kind": "composite",
        "columns": ["INT_ID", "STR_MapType", "INT_Faction", "INT_Group"],
        "key_column": "INT_ID",
        "expected_type": "json",
    }
    composite_rule = _build_composite_rule(
        composite_variable["tag"],
        rule_name="组合条件不包含筛选",
    )
    composite_rule["composite_config"]["global_filters"] = [
        {
            "condition_id": "global-maptype-not-contains",
            "field": "STR_MapType",
            "operator": "not_contains",
            "value_source": "literal",
            "expected_value": "B",
        }
    ]
    composite_rule["composite_config"]["branches"] = [
        {
            "branch_id": "branch-maptype-not-contains",
            "filters": [
                {
                    "condition_id": "branch-maptype-not-contains",
                    "field": "STR_MapType",
                    "operator": "not_contains",
                    "value_source": "literal",
                    "expected_value": "Y",
                }
            ],
            "assertions": [
                {
                    "condition_id": "branch-maptype-not-null",
                    "field": "INT_Group",
                    "operator": "not_null",
                }
            ],
        }
    ]
    payload = _build_v4_payload(
        workbook_path,
        variables=[composite_variable],
        rules=[composite_rule],
    )

    async with _auth_client_ctx(auth_headers) as client:
        save_response = await client.put("/api/v1/fixed-rules/config", json=payload)
        get_response = await client.get("/api/v1/fixed-rules/config")

    assert save_response.status_code == 200
    rule = get_response.json()["data"]["rules"][0]
    assert rule["composite_config"]["global_filters"][0]["operator"] == "not_contains"
    assert rule["composite_config"]["global_filters"][0]["expected_value"] == "B"
    assert rule["composite_config"]["branches"][0]["filters"][0]["operator"] == "not_contains"


@pytest.mark.anyio
async def test_put_fixed_rules_config_accepts_composite_regex_assertion_round_trip(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证组合条件校验支持在分支校验中保存正则断言。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "composite_regex_round_trip.xlsx",
        {
            "INT_ID": [100001, 100002],
            "STR_MapType": ["ABCD", "AXYZ"],
            "STR_Config": [
                "11005:1;457-458:1;460:1;489-1500:1;488:0",
                "broken",
            ],
            "INT_Group": [100001, 100002],
        },
    )
    composite_variable = {
        "tag": _build_composite_tag("items-source", "items", "regex-map"),
        "source_id": "items-source",
        "sheet": "items",
        "variable_kind": "composite",
        "columns": ["INT_ID", "STR_MapType", "STR_Config", "INT_Group"],
        "key_column": "INT_ID",
        "expected_type": "json",
    }
    composite_rule = _build_composite_rule(
        composite_variable["tag"],
        rule_name="组合条件正则校验",
    )
    composite_rule["composite_config"]["global_filters"] = []
    composite_rule["composite_config"]["branches"] = [
        {
            "branch_id": "branch-regex-check",
            "filters": [],
            "assertions": [
                {
                    "condition_id": "branch-config-regex",
                    "field": "STR_Config",
                    "operator": "regex",
                    "expected_value": r"(?:\d+(?:-\d+)?:(?:0|1))(?:;\d+(?:-\d+)?:(?:0|1))*",
                }
            ],
        }
    ]
    payload = _build_v4_payload(
        workbook_path,
        variables=[composite_variable],
        rules=[composite_rule],
    )

    async with _auth_client_ctx(auth_headers) as client:
        save_response = await client.put("/api/v1/fixed-rules/config", json=payload)
        get_response = await client.get("/api/v1/fixed-rules/config")

    assert save_response.status_code == 200
    rule = get_response.json()["data"]["rules"][0]
    assertion = rule["composite_config"]["branches"][0]["assertions"][0]
    assert assertion["operator"] == "regex"
    assert assertion["expected_value"] == r"(?:\d+(?:-\d+)?:(?:0|1))(?:;\d+(?:-\d+)?:(?:0|1))*"


@pytest.mark.anyio
async def test_put_fixed_rules_config_rejects_composite_rule_bound_to_single_variable(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "single_cannot_use_composite.xlsx",
        {"INT_ID": [1, 2, 3], "DESC": ["a", "b", "c"]},
    )
    target_tag = _build_single_tag("items-source", "items", "INT_ID")
    payload = _build_v4_payload(
        workbook_path,
        rules=[_build_composite_rule(target_tag, rule_name="单变量不能绑定组合规则")],
    )

    async with _auth_client_ctx(auth_headers) as client:
        response = await client.put("/api/v1/fixed-rules/config", json=payload)

    assert response.status_code == 400
    assert "rule-composite-branch" in response.json()["detail"]


@pytest.mark.anyio
async def test_put_fixed_rules_config_supports_dual_composite_compare_round_trip(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证双组合变量比对规则可以保存并再次读取。"""
    workbook_path = _create_dual_composite_workbook(
        tmp_path / "dual_composite_round_trip.xlsx",
        left_rows={
            "INT_ID": [10001, 10002],
            "INT_ConditionType": [4, 3],
            "INT_RequireRule": [1, 1],
        },
        right_rows={
            "INT_ID": [10001, 10002],
            "INT_ConditionType": [5, 3],
            "INT_RequireRule": [1, 1],
        },
    )
    left_variable = {
        "tag": _build_composite_tag("items-source", "left_items", "left-map"),
        "source_id": "items-source",
        "sheet": "left_items",
        "variable_kind": "composite",
        "columns": ["INT_ID", "INT_ConditionType", "INT_RequireRule"],
        "key_column": "INT_ID",
        "expected_type": "json",
    }
    right_variable = {
        "tag": _build_composite_tag("items-source", "right_items", "right-map"),
        "source_id": "items-source",
        "sheet": "right_items",
        "variable_kind": "composite",
        "columns": ["INT_ID", "INT_ConditionType", "INT_RequireRule"],
        "key_column": "INT_ID",
        "expected_type": "json",
    }
    payload = _build_v4_payload(
        workbook_path,
        variables=[left_variable, right_variable],
        rules=[_build_dual_composite_rule(left_variable["tag"], right_variable["tag"])],
    )

    async with _auth_client_ctx(auth_headers) as client:
        save_response = await client.put("/api/v1/fixed-rules/config", json=payload)
        get_response = await client.get("/api/v1/fixed-rules/config")

    assert save_response.status_code == 200
    rule = get_response.json()["data"]["rules"][0]
    assert rule["rule_type"] == "dual_composite_compare"
    assert rule["target_variable_tag"] == left_variable["tag"]
    assert rule["reference_variable_tag"] == right_variable["tag"]
    assert rule["key_check_mode"] == "baseline_only"
    assert len(rule["comparisons"]) == 2


@pytest.mark.anyio
async def test_put_fixed_rules_config_rejects_dual_composite_compare_bound_to_single_variable(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证双组合变量比对只能绑定组合变量。"""
    workbook_path = _create_dual_composite_workbook(
        tmp_path / "dual_composite_invalid.xlsx",
        left_rows={
            "INT_ID": [10001, 10002],
            "INT_ConditionType": [4, 3],
            "INT_RequireRule": [1, 1],
        },
        right_rows={
            "INT_ID": [10001, 10002],
            "INT_ConditionType": [5, 3],
            "INT_RequireRule": [1, 1],
        },
    )
    single_variable = {
        "tag": _build_single_tag("items-source", "left_items", "INT_ConditionType"),
        "source_id": "items-source",
        "sheet": "left_items",
        "variable_kind": "single",
        "column": "INT_ConditionType",
        "expected_type": "str",
    }
    right_variable = {
        "tag": _build_composite_tag("items-source", "right_items", "right-map"),
        "source_id": "items-source",
        "sheet": "right_items",
        "variable_kind": "composite",
        "columns": ["INT_ID", "INT_ConditionType", "INT_RequireRule"],
        "key_column": "INT_ID",
        "expected_type": "json",
    }
    payload = _build_v4_payload(
        workbook_path,
        variables=[single_variable, right_variable],
        rules=[_build_dual_composite_rule(single_variable["tag"], right_variable["tag"])],
    )

    async with _auth_client_ctx(auth_headers) as client:
        response = await client.put("/api/v1/fixed-rules/config", json=payload)

    assert response.status_code == 400
    assert "不能保存双组合变量比对" in response.json()["detail"]


@pytest.mark.anyio
async def test_put_fixed_rules_config_rejects_composite_rule_without_branches(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "composite_no_branches.xlsx",
        {
            "INT_ID": [100001, 100002],
            "INT_Faction": [0, 1],
            "INT_Group": [100001, 100001],
        },
    )
    composite_variable = _build_composite_variable()
    composite_rule = _build_composite_rule(composite_variable["tag"])
    composite_rule["composite_config"]["branches"] = []
    payload = _build_v4_payload(
        workbook_path,
        variables=[composite_variable],
        rules=[composite_rule],
    )

    async with _auth_client_ctx(auth_headers) as client:
        response = await client.put("/api/v1/fixed-rules/config", json=payload)

    assert response.status_code == 400
    assert "rule-composite-branch" in response.json()["detail"]


@pytest.mark.anyio
async def test_put_fixed_rules_config_rejects_composite_branch_without_assertions(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "composite_no_assertions.xlsx",
        {
            "INT_ID": [100001, 100002],
            "INT_Faction": [0, 1],
            "INT_Group": [100001, 100001],
        },
    )
    composite_variable = _build_composite_variable()
    composite_rule = _build_composite_rule(composite_variable["tag"])
    composite_rule["composite_config"]["branches"][0]["assertions"] = []
    payload = _build_v4_payload(
        workbook_path,
        variables=[composite_variable],
        rules=[composite_rule],
    )

    async with _auth_client_ctx(auth_headers) as client:
        response = await client.put("/api/v1/fixed-rules/config", json=payload)

    assert response.status_code == 400
    assert "rule-composite-branch" in response.json()["detail"]


@pytest.mark.anyio
async def test_put_fixed_rules_config_rejects_unique_in_composite_filters(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "composite_invalid_filter_operator.xlsx",
        {
            "INT_ID": [100001, 100002],
            "INT_Faction": [0, 1],
            "INT_Group": [100001, 100001],
        },
    )
    composite_variable = _build_composite_variable()
    composite_rule = _build_composite_rule(composite_variable["tag"])
    composite_rule["composite_config"]["global_filters"][0]["operator"] = "unique"
    composite_rule["composite_config"]["global_filters"][0].pop("expected_value", None)
    payload = _build_v4_payload(
        workbook_path,
        variables=[composite_variable],
        rules=[composite_rule],
    )

    async with _auth_client_ctx(auth_headers) as client:
        response = await client.put("/api/v1/fixed-rules/config", json=payload)

    assert response.status_code == 400
    assert "rule-composite-branch" in response.json()["detail"]


@pytest.mark.anyio
async def test_put_fixed_rules_config_rejects_contains_in_composite_assertions(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "composite_invalid_contains_assertion.xlsx",
        {
            "INT_ID": [100001, 100002],
            "STR_MapType": ["ABCD", "ACD"],
            "INT_Faction": [0, 1],
            "INT_Group": [100001, 100001],
        },
    )
    composite_variable = {
        "tag": _build_composite_tag("items-source", "items", "contains-assertion-map"),
        "source_id": "items-source",
        "sheet": "items",
        "variable_kind": "composite",
        "columns": ["INT_ID", "STR_MapType", "INT_Faction", "INT_Group"],
        "key_column": "INT_ID",
        "expected_type": "json",
    }
    composite_rule = _build_composite_rule(composite_variable["tag"])
    composite_rule["composite_config"]["branches"][0]["assertions"][0] = {
        "condition_id": "branch-assert-contains",
        "field": "STR_MapType",
        "operator": "contains",
        "value_source": "literal",
        "expected_value": "B",
    }
    payload = _build_v4_payload(
        workbook_path,
        variables=[composite_variable],
        rules=[composite_rule],
    )

    async with _auth_client_ctx(auth_headers) as client:
        response = await client.put("/api/v1/fixed-rules/config", json=payload)

    assert response.status_code == 400
    assert "rule-composite-branch" in response.json()["detail"]


@pytest.mark.anyio
async def test_put_fixed_rules_config_rejects_regex_in_composite_filters(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证组合条件校验不会把正则操作符接受到筛选条件里。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "composite_invalid_regex_filter.xlsx",
        {
            "INT_ID": [100001, 100002],
            "STR_Config": ["ok", "bad"],
            "INT_Faction": [0, 1],
            "INT_Group": [100001, 100001],
        },
    )
    composite_variable = {
        "tag": _build_composite_tag("items-source", "items", "regex-filter-map"),
        "source_id": "items-source",
        "sheet": "items",
        "variable_kind": "composite",
        "columns": ["INT_ID", "STR_Config", "INT_Faction", "INT_Group"],
        "key_column": "INT_ID",
        "expected_type": "json",
    }
    composite_rule = _build_composite_rule(composite_variable["tag"])
    composite_rule["composite_config"]["global_filters"][0] = {
        "condition_id": "global-regex-filter",
        "field": "STR_Config",
        "operator": "regex",
        "expected_value": r".+",
    }
    payload = _build_v4_payload(
        workbook_path,
        variables=[composite_variable],
        rules=[composite_rule],
    )

    async with _auth_client_ctx(auth_headers) as client:
        response = await client.put("/api/v1/fixed-rules/config", json=payload)

    assert response.status_code == 400
    assert "regex" in response.json()["detail"]


@pytest.mark.anyio
async def test_put_fixed_rules_config_rejects_contains_with_field_rhs(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "composite_invalid_contains_field.xlsx",
        {
            "INT_ID": [100001, 100002],
            "STR_MapType": ["ABCD", "ACD"],
            "INT_Faction": [0, 1],
            "INT_Group": [100001, 100001],
        },
    )
    composite_variable = {
        "tag": _build_composite_tag("items-source", "items", "contains-field-map"),
        "source_id": "items-source",
        "sheet": "items",
        "variable_kind": "composite",
        "columns": ["INT_ID", "STR_MapType", "INT_Faction", "INT_Group"],
        "key_column": "INT_ID",
        "expected_type": "json",
    }
    composite_rule = _build_composite_rule(composite_variable["tag"])
    composite_rule["composite_config"]["global_filters"][0] = {
        "condition_id": "global-contains-field",
        "field": "STR_MapType",
        "operator": "contains",
        "value_source": "field",
        "expected_field": "INT_Group",
    }
    payload = _build_v4_payload(
        workbook_path,
        variables=[composite_variable],
        rules=[composite_rule],
    )

    async with _auth_client_ctx(auth_headers) as client:
        response = await client.put("/api/v1/fixed-rules/config", json=payload)

    assert response.status_code == 400
    assert "contains" in response.json()["detail"]


@pytest.mark.anyio
async def test_put_fixed_rules_config_rejects_composite_compare_assertion_without_rhs(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "composite_missing_rhs.xlsx",
        {
            "INT_ID": [100001, 100002],
            "INT_Faction": [0, 1],
            "INT_Group": [100001, 100001],
        },
    )
    composite_variable = _build_composite_variable()
    composite_rule = _build_composite_rule(composite_variable["tag"])
    composite_rule["composite_config"]["branches"][0]["assertions"][0]["value_source"] = "field"
    composite_rule["composite_config"]["branches"][0]["assertions"][0].pop("expected_field", None)
    payload = _build_v4_payload(
        workbook_path,
        variables=[composite_variable],
        rules=[composite_rule],
    )

    async with _auth_client_ctx(auth_headers) as client:
        response = await client.put("/api/v1/fixed-rules/config", json=payload)

    assert response.status_code == 400
    assert "rule-composite-branch" in response.json()["detail"]


@pytest.mark.anyio
async def test_execute_fixed_rules_supports_composite_condition_check(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "composite_execute.xlsx",
        {
            "INT_ID": [100001, 100002, 100003, 100004],
            "INT_Faction": [0, 1, 1, 0],
            "INT_Group": [100001, 200, 200, 999999],
        },
    )
    composite_variable = _build_composite_variable()
    composite_rule = _build_composite_rule(composite_variable["tag"], rule_name="派系与分组映射校验")
    payload = _build_v4_payload(
        workbook_path,
        variables=[composite_variable],
        rules=[composite_rule],
    )

    async with _auth_client_ctx(auth_headers) as client:
        save_response = await client.put("/api/v1/fixed-rules/config", json=payload)
        execute_response = await client.post("/api/v1/fixed-rules/execute")

    assert save_response.status_code == 200
    assert execute_response.status_code == 200
    response_payload = execute_response.json()
    abnormal_results = response_payload["data"]["abnormal_results"]
    assert response_payload["msg"] == "Execution Completed"
    assert response_payload["meta"]["total_rows_scanned"] == 4
    assert len(abnormal_results) == 1
    assert abnormal_results[0]["rule_name"] == "派系与分组映射校验"
    assert abnormal_results[0]["row_index"] == 5
    assert abnormal_results[0]["location"] == "items -> INT_Group"


@pytest.mark.anyio
async def test_execute_fixed_rules_supports_composite_contains_filters(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证组合条件校验支持字符串包含筛选。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "composite_contains_execute.xlsx",
        {
            "INT_ID": [100001, 100002, 100003],
            "STR_MapType": ["ABCD", "BCD", "BEE"],
            "INT_Faction": [0, 0, 1],
            "INT_Group": [100001, "", 300],
        },
    )
    composite_variable = {
        "tag": _build_composite_tag("items-source", "items", "contains-execute-map"),
        "source_id": "items-source",
        "sheet": "items",
        "variable_kind": "composite",
        "columns": ["INT_ID", "STR_MapType", "INT_Faction", "INT_Group"],
        "key_column": "INT_ID",
        "expected_type": "json",
    }
    composite_rule = {
        "rule_id": "rule-composite-contains",
        "group_id": "basic-checks",
        "rule_name": "组合条件包含筛选",
        "target_variable_tag": composite_variable["tag"],
        "rule_type": "composite_condition_check",
        "composite_config": {
            "global_filters": [
                {
                    "condition_id": "global-maptype-contains-b",
                    "field": "STR_MapType",
                    "operator": "contains",
                    "value_source": "literal",
                    "expected_value": "B",
                }
            ],
            "branches": [
                {
                    "branch_id": "branch-maptype-contains-c",
                    "filters": [
                        {
                            "condition_id": "branch-maptype-contains-c",
                            "field": "STR_MapType",
                            "operator": "contains",
                            "value_source": "literal",
                            "expected_value": "C",
                        }
                    ],
                    "assertions": [
                        {
                            "condition_id": "branch-group-not-null",
                            "field": "INT_Group",
                            "operator": "not_null",
                        }
                    ],
                }
            ],
        },
    }
    payload = _build_v4_payload(
        workbook_path,
        variables=[composite_variable],
        rules=[composite_rule],
    )

    async with _auth_client_ctx(auth_headers) as client:
        await client.put("/api/v1/fixed-rules/config", json=payload)
        execute_response = await client.post("/api/v1/fixed-rules/execute")

    assert execute_response.status_code == 200
    abnormal_results = execute_response.json()["data"]["abnormal_results"]
    assert len(abnormal_results) == 1
    assert abnormal_results[0]["rule_name"] == "组合条件包含筛选"
    assert abnormal_results[0]["row_index"] == 3
    assert abnormal_results[0]["location"] == "items -> INT_Group"


@pytest.mark.anyio
async def test_execute_fixed_rules_supports_composite_not_contains_filters(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证组合条件校验支持字符串不包含筛选。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "composite_not_contains_execute.xlsx",
        {
            "INT_ID": [100001, 100002, 100003],
            "STR_MapType": ["ACD", "XYZ", "BCD"],
            "INT_Faction": [0, 0, 1],
            "INT_Group": [100001, "", 300],
        },
    )
    composite_variable = {
        "tag": _build_composite_tag("items-source", "items", "not-contains-execute-map"),
        "source_id": "items-source",
        "sheet": "items",
        "variable_kind": "composite",
        "columns": ["INT_ID", "STR_MapType", "INT_Faction", "INT_Group"],
        "key_column": "INT_ID",
        "expected_type": "json",
    }
    composite_rule = {
        "rule_id": "rule-composite-not-contains",
        "group_id": "basic-checks",
        "rule_name": "组合条件不包含筛选",
        "target_variable_tag": composite_variable["tag"],
        "rule_type": "composite_condition_check",
        "composite_config": {
            "global_filters": [
                {
                    "condition_id": "global-maptype-not-contains-b",
                    "field": "STR_MapType",
                    "operator": "not_contains",
                    "value_source": "literal",
                    "expected_value": "B",
                }
            ],
            "branches": [
                {
                    "branch_id": "branch-maptype-not-contains-q",
                    "filters": [
                        {
                            "condition_id": "branch-maptype-not-contains-q",
                            "field": "STR_MapType",
                            "operator": "not_contains",
                            "value_source": "literal",
                            "expected_value": "Q",
                        }
                    ],
                    "assertions": [
                        {
                            "condition_id": "branch-group-not-null",
                            "field": "INT_Group",
                            "operator": "not_null",
                        }
                    ],
                }
            ],
        },
    }
    payload = _build_v4_payload(
        workbook_path,
        variables=[composite_variable],
        rules=[composite_rule],
    )

    async with _auth_client_ctx(auth_headers) as client:
        await client.put("/api/v1/fixed-rules/config", json=payload)
        execute_response = await client.post("/api/v1/fixed-rules/execute")

    assert execute_response.status_code == 200
    abnormal_results = execute_response.json()["data"]["abnormal_results"]
    assert len(abnormal_results) == 1
    assert abnormal_results[0]["rule_name"] == "组合条件不包含筛选"
    assert abnormal_results[0]["row_index"] == 3
    assert abnormal_results[0]["location"] == "items -> INT_Group"


@pytest.mark.anyio
async def test_execute_fixed_rules_supports_mixed_composite_contains_and_not_contains_filters(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证组合条件校验支持 contains + not_contains + not_null 混合执行。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "composite_contains_not_contains_mix.xlsx",
        {
            "INT_ID": [100001, 100002, 100003],
            "STR_ParamType": ["int", "int-已废弃", "int-live"],
            "STR_ServersParam": ["server-ok", "server-skip", ""],
            "DES": ["A", "B", "C"],
        },
    )
    composite_variable = {
        "tag": _build_composite_tag("items-source", "items", "contains-not-contains-mix"),
        "source_id": "items-source",
        "sheet": "items",
        "variable_kind": "composite",
        "columns": ["INT_ID", "STR_ParamType", "STR_ServersParam", "DES"],
        "key_column": "STR_ParamType",
        "append_index_to_key": True,
        "expected_type": "json",
    }
    composite_rule = {
        "rule_id": "rule-composite-contains-not-contains-mix",
        "group_id": "basic-checks",
        "rule_name": "组合条件混合筛选",
        "target_variable_tag": composite_variable["tag"],
        "rule_type": "composite_condition_check",
        "composite_config": {
            "global_filters": [
                {
                    "condition_id": "global-paramtype-contains-int",
                    "field": "__key__",
                    "operator": "contains",
                    "value_source": "literal",
                    "expected_value": "int",
                }
            ],
            "branches": [
                {
                    "branch_id": "branch-paramtype-not-contains-deprecated",
                    "filters": [
                        {
                            "condition_id": "branch-paramtype-not-contains-deprecated",
                            "field": "__key__",
                            "operator": "not_contains",
                            "value_source": "literal",
                            "expected_value": "已废弃",
                        }
                    ],
                    "assertions": [
                        {
                            "condition_id": "branch-servers-param-not-null",
                            "field": "STR_ServersParam",
                            "operator": "not_null",
                        }
                    ],
                }
            ],
        },
    }
    payload = _build_v4_payload(
        workbook_path,
        variables=[composite_variable],
        rules=[composite_rule],
    )

    async with _auth_client_ctx(auth_headers) as client:
        await client.put("/api/v1/fixed-rules/config", json=payload)
        execute_response = await client.post("/api/v1/fixed-rules/execute")

    assert execute_response.status_code == 200
    abnormal_results = execute_response.json()["data"]["abnormal_results"]
    assert len(abnormal_results) == 1
    assert abnormal_results[0]["rule_name"] == "组合条件混合筛选"
    assert abnormal_results[0]["row_index"] == 4
    assert abnormal_results[0]["location"] == "items -> STR_ServersParam"


@pytest.mark.anyio
async def test_execute_fixed_rules_supports_composite_regex_assertion(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证组合条件校验支持在分支校验中执行正则断言。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "composite_regex_execute.xlsx",
        {
            "INT_ID": [100001, 100002, 100003],
            "STR_MapType": ["ACTIVE", "ACTIVE", "SKIP"],
            "STR_Config": [
                "11005:1;457-458:1;460:1;489-1500:1;488:0",
                "invalid-config",
                "11005:1",
            ],
            "INT_Group": [1, 2, 3],
        },
    )
    composite_variable = {
        "tag": _build_composite_tag("items-source", "items", "regex-execute-map"),
        "source_id": "items-source",
        "sheet": "items",
        "variable_kind": "composite",
        "columns": ["INT_ID", "STR_MapType", "STR_Config", "INT_Group"],
        "key_column": "INT_ID",
        "expected_type": "json",
    }
    composite_rule = {
        "rule_id": "rule-composite-regex",
        "group_id": "basic-checks",
        "rule_name": "组合条件正则断言",
        "target_variable_tag": composite_variable["tag"],
        "rule_type": "composite_condition_check",
        "composite_config": {
            "global_filters": [],
            "branches": [
                {
                    "branch_id": "branch-active-regex",
                    "filters": [
                        {
                            "condition_id": "branch-maptype-active",
                            "field": "STR_MapType",
                            "operator": "eq",
                            "value_source": "literal",
                            "expected_value": "ACTIVE",
                        }
                    ],
                    "assertions": [
                        {
                            "condition_id": "branch-config-regex",
                            "field": "STR_Config",
                            "operator": "regex",
                            "expected_value": r"(?:\d+(?:-\d+)?:(?:0|1))(?:;\d+(?:-\d+)?:(?:0|1))*",
                        }
                    ],
                }
            ],
        },
    }
    payload = _build_v4_payload(
        workbook_path,
        variables=[composite_variable],
        rules=[composite_rule],
    )

    async with _auth_client_ctx(auth_headers) as client:
        await client.put("/api/v1/fixed-rules/config", json=payload)
        execute_response = await client.post("/api/v1/fixed-rules/execute")

    assert execute_response.status_code == 200
    abnormal_results = execute_response.json()["data"]["abnormal_results"]
    assert len(abnormal_results) == 1
    assert abnormal_results[0]["rule_name"] == "组合条件正则断言"
    assert abnormal_results[0]["row_index"] == 3
    assert abnormal_results[0]["location"] == "items -> STR_Config"
    assert "正则格式" in abnormal_results[0]["message"]


@pytest.mark.anyio
async def test_put_fixed_rules_config_round_trips_composite_key_suffix_flag(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证项目校验配置可保存并读取组合变量的 Key 追加序号开关。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "composite_suffix_round_trip.xlsx",
        {"INT_ID": ["A", "A"], "INT_Faction": [0, 1], "INT_Group": [1, 2]},
    )
    composite_variable = _build_composite_variable(append_index_to_key=True)
    payload = _build_v4_payload(
        workbook_path,
        variables=[composite_variable],
        rules=[],
    )

    async with _auth_client_ctx(auth_headers) as client:
        save_response = await client.put("/api/v1/fixed-rules/config", json=payload)
        get_response = await client.get("/api/v1/fixed-rules/config")

    assert save_response.status_code == 200
    returned_variable = get_response.json()["data"]["variables"][0]
    assert returned_variable["append_index_to_key"] is True


@pytest.mark.anyio
async def test_execute_fixed_rules_supports_composite_key_suffix_generation(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证项目校验执行链路会使用原值_序号生成组合变量 key。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "composite_suffix_execute.xlsx",
        {"INT_ID": ["A", "A"], "INT_Faction": [0, 1], "INT_Group": [1, 2]},
    )
    composite_variable = _build_composite_variable(tag="suffix-map", append_index_to_key=True)
    composite_rule = {
        "rule_id": "rule-composite-suffix",
        "group_id": "basic-checks",
        "rule_name": "组合条件 Key 后缀校验",
        "target_variable_tag": composite_variable["tag"],
        "rule_type": "composite_condition_check",
        "composite_config": {
            "global_filters": [],
            "branches": [
                {
                    "branch_id": "branch-key-eq-suffixed",
                    "filters": [],
                    "assertions": [
                        {
                            "condition_id": "assert-key-eq",
                            "field": "__key__",
                            "operator": "eq",
                            "value_source": "literal",
                            "expected_value": "A_0",
                        }
                    ],
                }
            ],
        },
    }
    payload = _build_v4_payload(
        workbook_path,
        variables=[composite_variable],
        rules=[composite_rule],
    )

    async with _auth_client_ctx(auth_headers) as client:
        await client.put("/api/v1/fixed-rules/config", json=payload)
        execute_response = await client.post("/api/v1/fixed-rules/execute")

    assert execute_response.status_code == 200
    abnormal_results = execute_response.json()["data"]["abnormal_results"]
    assert len(abnormal_results) == 1
    assert abnormal_results[0]["row_index"] == 3
    assert "A_0" in abnormal_results[0]["message"]


@pytest.mark.anyio
async def test_execute_fixed_rules_supports_dual_composite_compare(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证双组合变量比对会按 Key 关联后比较内部字段值。"""
    workbook_path = _create_dual_composite_workbook(
        tmp_path / "dual_composite_execute.xlsx",
        left_rows={
            "INT_ID": [10001, 10002],
            "INT_ConditionType": [4, 3],
            "INT_RequireRule": [1, 1],
        },
        right_rows={
            "INT_ID": [10001, 10002],
            "INT_ConditionType": [5, 3],
            "INT_RequireRule": [1, 1],
        },
    )
    left_variable = {
        "tag": _build_composite_tag("items-source", "left_items", "left-map"),
        "source_id": "items-source",
        "sheet": "left_items",
        "variable_kind": "composite",
        "columns": ["INT_ID", "INT_ConditionType", "INT_RequireRule"],
        "key_column": "INT_ID",
        "expected_type": "json",
    }
    right_variable = {
        "tag": _build_composite_tag("items-source", "right_items", "right-map"),
        "source_id": "items-source",
        "sheet": "right_items",
        "variable_kind": "composite",
        "columns": ["INT_ID", "INT_ConditionType", "INT_RequireRule"],
        "key_column": "INT_ID",
        "expected_type": "json",
    }
    payload = _build_v4_payload(
        workbook_path,
        variables=[left_variable, right_variable],
        rules=[_build_dual_composite_rule(left_variable["tag"], right_variable["tag"])],
    )

    async with _auth_client_ctx(auth_headers) as client:
        await client.put("/api/v1/fixed-rules/config", json=payload)
        execute_response = await client.post("/api/v1/fixed-rules/execute")

    assert execute_response.status_code == 200
    abnormal_results = execute_response.json()["data"]["abnormal_results"]
    assert len(abnormal_results) == 1
    assert abnormal_results[0]["rule_name"] == "双组合变量比对"
    assert "Key 10001" in abnormal_results[0]["message"]
    assert "INT_ConditionType" in abnormal_results[0]["message"]
    assert "4" in abnormal_results[0]["message"]
    assert "5" in abnormal_results[0]["message"]


@pytest.mark.anyio
async def test_execute_fixed_rules_dual_composite_compare_reports_bidirectional_missing_key(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证双向 Key 校验会报告目标侧多出的 Key。"""
    workbook_path = _create_dual_composite_workbook(
        tmp_path / "dual_composite_bidirectional.xlsx",
        left_rows={
            "INT_ID": [10001],
            "INT_ConditionType": [4],
            "INT_RequireRule": [1],
        },
        right_rows={
            "INT_ID": [10001, 10002],
            "INT_ConditionType": [4, 5],
            "INT_RequireRule": [1, 1],
        },
    )
    left_variable = {
        "tag": _build_composite_tag("items-source", "left_items", "left-map"),
        "source_id": "items-source",
        "sheet": "left_items",
        "variable_kind": "composite",
        "columns": ["INT_ID", "INT_ConditionType", "INT_RequireRule"],
        "key_column": "INT_ID",
        "expected_type": "json",
    }
    right_variable = {
        "tag": _build_composite_tag("items-source", "right_items", "right-map"),
        "source_id": "items-source",
        "sheet": "right_items",
        "variable_kind": "composite",
        "columns": ["INT_ID", "INT_ConditionType", "INT_RequireRule"],
        "key_column": "INT_ID",
        "expected_type": "json",
    }
    payload = _build_v4_payload(
        workbook_path,
        variables=[left_variable, right_variable],
        rules=[
            _build_dual_composite_rule(
                left_variable["tag"],
                right_variable["tag"],
                key_check_mode="bidirectional",
                comparisons=[
                    {
                        "comparison_id": "compare-condition-type",
                        "left_field": "INT_ConditionType",
                        "operator": "eq",
                        "right_field": "INT_ConditionType",
                    }
                ],
            )
        ],
    )

    async with _auth_client_ctx(auth_headers) as client:
        await client.put("/api/v1/fixed-rules/config", json=payload)
        execute_response = await client.post("/api/v1/fixed-rules/execute")

    assert execute_response.status_code == 200
    abnormal_results = execute_response.json()["data"]["abnormal_results"]
    assert len(abnormal_results) == 1
    assert "缺失该 Key (10002)" in abnormal_results[0]["message"]


@pytest.mark.anyio
async def test_put_fixed_rules_config_rejects_compare_rule_without_expected_value(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证比较类规则缺少 expected_value 时会返回 400。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "missing_expected.xlsx",
        {"INT_ID": [1, 2, 3], "DESC": ["a", "b", "c"]},
    )
    payload = _build_v4_payload(workbook_path)
    payload["rules"][0]["expected_value"] = ""

    async with _auth_client_ctx(auth_headers) as client:
        response = await client.put("/api/v1/fixed-rules/config", json=payload)

    assert response.status_code == 400
    assert "expected_value" in response.json()["detail"]


@pytest.mark.anyio
async def test_put_fixed_rules_config_rejects_regex_check_with_invalid_pattern(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证正则校验规则会拦截非法表达式。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "invalid_regex_pattern.xlsx",
        {"DESC": ["ok", "bad"]},
    )
    target_tag = _build_single_tag("items-source", "items", "DESC")
    payload = _build_v4_payload(
        workbook_path,
        variables=[
            {
                "tag": target_tag,
                "source_id": "items-source",
                "sheet": "items",
                "variable_kind": "single",
                "column": "DESC",
                "expected_type": "str",
            }
        ],
        rules=[
            _build_regex_rule(
                target_tag,
                pattern="(",
            )
        ],
    )

    async with _auth_client_ctx(auth_headers) as client:
        response = await client.put("/api/v1/fixed-rules/config", json=payload)

    assert response.status_code == 400
    assert "正则表达式无效" in response.json()["detail"]


@pytest.mark.anyio
async def test_execute_fixed_rules_passes_gt_zero_rule(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证 INT_ID > 0 在合法数据上返回 0 条异常。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "gt_zero.xlsx",
        {"INT_ID": [1, 2, 3], "DESC": ["a", "b", "c"]},
    )
    payload = _build_v4_payload(workbook_path)

    async with _auth_client_ctx(auth_headers) as client:
        save_response = await client.put("/api/v1/fixed-rules/config", json=payload)
        execute_response = await client.post("/api/v1/fixed-rules/execute")

    assert save_response.status_code == 200
    assert execute_response.status_code == 200
    execute_payload = execute_response.json()
    assert execute_payload["msg"] == "Execution Completed"
    assert execute_payload["meta"]["total_rows_scanned"] == 3
    assert execute_payload["data"]["abnormal_results"] == []


@pytest.mark.anyio
async def test_execute_fixed_rules_supports_regex_check(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证单变量正则校验可执行，并按完整匹配报告异常。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "regex_execute.xlsx",
        {
            "DESC": [
                "11005:1;457-458:1;460:1;489-1500:1;488:0",
                "11005:1;457-458:1",
                "broken",
            ]
        },
    )
    target_tag = _build_single_tag("items-source", "items", "DESC")
    payload = _build_v4_payload(
        workbook_path,
        variables=[
            {
                "tag": target_tag,
                "source_id": "items-source",
                "sheet": "items",
                "variable_kind": "single",
                "column": "DESC",
                "expected_type": "str",
            }
        ],
        rules=[_build_regex_rule(target_tag, rule_name="DESC 格式校验")],
    )

    async with _auth_client_ctx(auth_headers) as client:
        await client.put("/api/v1/fixed-rules/config", json=payload)
        execute_response = await client.post("/api/v1/fixed-rules/execute")

    assert execute_response.status_code == 200
    abnormal_results = execute_response.json()["data"]["abnormal_results"]
    assert len(abnormal_results) == 1
    assert abnormal_results[0]["rule_name"] == "DESC 格式校验"
    assert abnormal_results[0]["row_index"] == 4
    assert "正则格式" in abnormal_results[0]["message"]


@pytest.mark.anyio
async def test_execute_fixed_rules_supports_sequence_order_check_auto_start(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证顺序校验支持自动取首行作为起始值。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "sequence_auto.xlsx",
        {"INT_ID": [10, 11, 12, 13], "DESC": ["a", "b", "c", "d"]},
    )
    target_tag = _build_single_tag("items-source", "items", "INT_ID")
    payload = _build_v4_payload(
        workbook_path,
        rules=[_build_sequence_rule(target_tag, rule_name="INT_ID 顺序递增")],
    )

    async with _auth_client_ctx(auth_headers) as client:
        await client.put("/api/v1/fixed-rules/config", json=payload)
        execute_response = await client.post("/api/v1/fixed-rules/execute")

    assert execute_response.status_code == 200
    execute_payload = execute_response.json()
    assert execute_payload["msg"] == "Execution Completed"
    assert execute_payload["data"]["abnormal_results"] == []


@pytest.mark.anyio
async def test_execute_fixed_rules_reports_sequence_gap(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证顺序校验会报告断档。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "sequence_gap.xlsx",
        {"INT_ID": [1, 2, 4], "DESC": ["a", "b", "c"]},
    )
    target_tag = _build_single_tag("items-source", "items", "INT_ID")
    payload = _build_v4_payload(
        workbook_path,
        rules=[_build_sequence_rule(target_tag, rule_name="INT_ID 顺序递增")],
    )

    async with _auth_client_ctx(auth_headers) as client:
        await client.put("/api/v1/fixed-rules/config", json=payload)
        execute_response = await client.post("/api/v1/fixed-rules/execute")

    assert execute_response.status_code == 200
    abnormal_results = execute_response.json()["data"]["abnormal_results"]
    assert len(abnormal_results) == 1
    assert abnormal_results[0]["row_index"] == 4
    assert abnormal_results[0]["rule_name"] == "INT_ID 顺序递增"
    assert "期望值 3" in abnormal_results[0]["message"]
    assert "步长 1" in abnormal_results[0]["message"]


@pytest.mark.anyio
async def test_execute_fixed_rules_supports_sequence_order_check_manual_descending(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证顺序校验支持手动起始值和降序步长。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "sequence_desc.xlsx",
        {"INT_ID": [20, 18, 16], "DESC": ["a", "b", "c"]},
    )
    target_tag = _build_single_tag("items-source", "items", "INT_ID")
    payload = _build_v4_payload(
        workbook_path,
        rules=[
            _build_sequence_rule(
                target_tag,
                direction="desc",
                step="2",
                start_mode="manual",
                start_value="20",
                rule_name="INT_ID 倒序连续",
            )
        ],
    )

    async with _auth_client_ctx(auth_headers) as client:
        await client.put("/api/v1/fixed-rules/config", json=payload)
        execute_response = await client.post("/api/v1/fixed-rules/execute")

    assert execute_response.status_code == 200
    assert execute_response.json()["data"]["abnormal_results"] == []


@pytest.mark.anyio
async def test_execute_fixed_rules_reports_sequence_empty_and_non_numeric(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证顺序校验会严格报告空值和非数字。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "sequence_invalid_values.xlsx",
        {"INT_ID": [1, None, "abc"], "DESC": ["a", "b", "c"]},
    )
    target_tag = _build_single_tag("items-source", "items", "INT_ID")
    payload = _build_v4_payload(
        workbook_path,
        rules=[_build_sequence_rule(target_tag, rule_name="INT_ID 顺序递增")],
    )

    async with _auth_client_ctx(auth_headers) as client:
        await client.put("/api/v1/fixed-rules/config", json=payload)
        execute_response = await client.post("/api/v1/fixed-rules/execute")

    assert execute_response.status_code == 200
    abnormal_results = execute_response.json()["data"]["abnormal_results"]
    assert len(abnormal_results) == 2
    assert abnormal_results[0]["row_index"] == 3
    assert abnormal_results[1]["row_index"] == 4
    assert "当前值为空" in abnormal_results[0]["message"]
    assert "不是合法数字" in abnormal_results[1]["message"]


@pytest.mark.anyio
async def test_execute_fixed_rules_reports_not_null_with_fixed_rule_location(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证固定规则页的非空校验沿用 error，并保留自定义规则名和定位。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "not_null.xlsx",
        {"INT_ID": [1, None, 3], "DESC": ["a", "b", "c"]},
    )
    target_tag = _build_single_tag("items-source", "items", "INT_ID")
    payload = _build_v4_payload(
        workbook_path,
        rules=[
            {
                "rule_id": "rule-not-null",
                "group_id": "basic-checks",
                "rule_name": "INT_ID 不能为空",
                "target_variable_tag": target_tag,
                "rule_type": "not_null",
            }
        ],
    )

    async with _auth_client_ctx(auth_headers) as client:
        await client.put("/api/v1/fixed-rules/config", json=payload)
        execute_response = await client.post("/api/v1/fixed-rules/execute")

    assert execute_response.status_code == 200
    abnormal_results = execute_response.json()["data"]["abnormal_results"]
    assert len(abnormal_results) == 1
    assert abnormal_results[0]["level"] == "error"
    assert abnormal_results[0]["rule_name"] == "INT_ID 不能为空"
    assert abnormal_results[0]["location"] == "items -> INT_ID"
    assert "不能为空" in abnormal_results[0]["message"]


@pytest.mark.anyio
async def test_execute_fixed_rules_reports_unique_with_warning_level(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证唯一校验沿用 warning 语义。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "unique.xlsx",
        {"INT_ID": [1, 1, 2], "DESC": ["a", "b", "c"]},
    )
    target_tag = _build_single_tag("items-source", "items", "INT_ID")
    payload = _build_v4_payload(
        workbook_path,
        rules=[
            {
                "rule_id": "rule-unique",
                "group_id": "basic-checks",
                "rule_name": "INT_ID 必须唯一",
                "target_variable_tag": target_tag,
                "rule_type": "unique",
            }
        ],
    )

    async with _auth_client_ctx(auth_headers) as client:
        await client.put("/api/v1/fixed-rules/config", json=payload)
        execute_response = await client.post("/api/v1/fixed-rules/execute")

    assert execute_response.status_code == 200
    abnormal_results = execute_response.json()["data"]["abnormal_results"]
    assert len(abnormal_results) == 2
    assert all(item["level"] == "warning" for item in abnormal_results)
    assert all(item["rule_name"] == "INT_ID 必须唯一" for item in abnormal_results)
    assert all(item["location"] == "items -> INT_ID" for item in abnormal_results)


@pytest.mark.anyio
async def test_execute_fixed_rules_supports_cross_table_mapping(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证固定规则页保存的“包含 (in)”规则会复用 cross_table_mapping 执行。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "cross_table_mapping.xlsx",
        {"INT_ID": [1, 2, 4], "DICT_ID": [1, 2, 3]},
    )
    target_tag = _build_single_tag("items-source", "items", "INT_ID")
    dict_tag = _build_single_tag("items-source", "items", "DICT_ID")
    payload = _build_v4_payload(
        workbook_path,
        variables=[
            {
                "tag": target_tag,
                "source_id": "items-source",
                "sheet": "items",
                "variable_kind": "single",
                "column": "INT_ID",
                "expected_type": "str",
            },
            {
                "tag": dict_tag,
                "source_id": "items-source",
                "sheet": "items",
                "variable_kind": "single",
                "column": "DICT_ID",
                "expected_type": "str",
            },
        ],
        rules=[
            {
                "rule_id": "rule-int-id-in-dict",
                "group_id": "basic-checks",
                "rule_name": "INT_ID 必须包含于 DICT_ID",
                "target_variable_tag": target_tag,
                "rule_type": "cross_table_mapping",
                "reference_variable_tag": dict_tag,
            }
        ],
    )

    async with _auth_client_ctx(auth_headers) as client:
        await client.put("/api/v1/fixed-rules/config", json=payload)
        execute_response = await client.post("/api/v1/fixed-rules/execute")

    assert execute_response.status_code == 200
    abnormal_results = execute_response.json()["data"]["abnormal_results"]
    assert len(abnormal_results) == 1
    assert abnormal_results[0]["level"] == "error"
    assert abnormal_results[0]["rule_name"] == "INT_ID 必须包含于 DICT_ID"
    assert abnormal_results[0]["raw_value"] == 4
    assert "未命中该映射值" in abnormal_results[0]["message"]


@pytest.mark.anyio
async def test_execute_fixed_rules_supports_mixed_rule_types_in_one_run(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证比较类、非空和唯一规则可以在一次执行中混合运行。"""
    workbook_a = _create_fixed_rules_workbook(
        tmp_path / "items_a.xlsx",
        {"INT_ID": [1, 2, 3], "DESC": ["a-1", "a-2", "a-3"]},
    )
    workbook_b = _create_fixed_rules_workbook(
        tmp_path / "items_b.xlsx",
        {"INT_ID": [10, 10, 30], "DESC": ["", "b-2", "b-3"]},
    )

    payload = {
        "version": 4,
        "configured": True,
        "sources": [
            {
                "id": "source-a",
                "type": "local_excel",
                "path": str(workbook_a),
                "pathOrUrl": str(workbook_a),
            },
            {
                "id": "source-b",
                "type": "local_excel",
                "path": str(workbook_b),
                "pathOrUrl": str(workbook_b),
            },
        ],
        "variables": [
            {
                "tag": "[source-a-items-INT_ID]",
                "source_id": "source-a",
                "sheet": "items",
                "variable_kind": "single",
                "column": "INT_ID",
                "expected_type": "str",
            },
            {
                "tag": "[source-b-items-INT_ID]",
                "source_id": "source-b",
                "sheet": "items",
                "variable_kind": "single",
                "column": "INT_ID",
                "expected_type": "str",
            },
            {
                "tag": "[source-b-items-DESC]",
                "source_id": "source-b",
                "sheet": "items",
                "variable_kind": "single",
                "column": "DESC",
                "expected_type": "str",
            },
        ],
        "groups": [
            {"group_id": "ungrouped", "group_name": "未分组", "builtin": True},
            {"group_id": "basic-checks", "group_name": "基础校验", "builtin": False},
        ],
        "rules": [
            {
                "rule_id": "rule-a",
                "group_id": "basic-checks",
                "rule_name": "A 文件 INT_ID > 0",
                "target_variable_tag": "[source-a-items-INT_ID]",
                "rule_type": "fixed_value_compare",
                "operator": "gt",
                "expected_value": "0",
            },
            {
                "rule_id": "rule-b1",
                "group_id": "basic-checks",
                "rule_name": "B 文件 DESC 不能为空",
                "target_variable_tag": "[source-b-items-DESC]",
                "rule_type": "not_null",
            },
            {
                "rule_id": "rule-b2",
                "group_id": "basic-checks",
                "rule_name": "B 文件 INT_ID 必须唯一",
                "target_variable_tag": "[source-b-items-INT_ID]",
                "rule_type": "unique",
            },
        ],
    }

    async with _auth_client_ctx(auth_headers) as client:
        await client.put("/api/v1/fixed-rules/config", json=payload)
        execute_response = await client.post("/api/v1/fixed-rules/execute")

    assert execute_response.status_code == 200
    execute_payload = execute_response.json()
    abnormal_results = execute_payload["data"]["abnormal_results"]
    assert execute_payload["meta"]["total_rows_scanned"] == 9
    assert any(item["rule_name"] == "B 文件 DESC 不能为空" for item in abnormal_results)
    assert any(item["rule_name"] == "B 文件 INT_ID 必须唯一" for item in abnormal_results)
    assert all(item["rule_name"] != "A 文件 INT_ID > 0" for item in abnormal_results)


@pytest.mark.anyio
async def test_execute_fixed_rules_filters_by_selected_rule_ids(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证项目校验执行接口只运行被勾选的规则。"""
    workbook_a = _create_fixed_rules_workbook(
        tmp_path / "selected_items_a.xlsx",
        {"INT_ID": [1, 2, 3], "DESC": ["a-1", "a-2", "a-3"]},
    )
    workbook_b = _create_fixed_rules_workbook(
        tmp_path / "selected_items_b.xlsx",
        {"INT_ID": [10, 10, 30], "DESC": ["", "b-2", "b-3"]},
    )

    payload = {
        "version": 4,
        "configured": True,
        "sources": [
            {
                "id": "source-a",
                "type": "local_excel",
                "path": str(workbook_a),
                "pathOrUrl": str(workbook_a),
            },
            {
                "id": "source-b",
                "type": "local_excel",
                "path": str(workbook_b),
                "pathOrUrl": str(workbook_b),
            },
        ],
        "variables": [
            {
                "tag": "[source-a-items-INT_ID]",
                "source_id": "source-a",
                "sheet": "items",
                "variable_kind": "single",
                "column": "INT_ID",
                "expected_type": "str",
            },
            {
                "tag": "[source-b-items-INT_ID]",
                "source_id": "source-b",
                "sheet": "items",
                "variable_kind": "single",
                "column": "INT_ID",
                "expected_type": "str",
            },
            {
                "tag": "[source-b-items-DESC]",
                "source_id": "source-b",
                "sheet": "items",
                "variable_kind": "single",
                "column": "DESC",
                "expected_type": "str",
            },
        ],
        "groups": [
            {"group_id": "ungrouped", "group_name": "未分组", "builtin": True},
            {"group_id": "basic-checks", "group_name": "基础校验", "builtin": False},
        ],
        "rules": [
            {
                "rule_id": "rule-a",
                "group_id": "basic-checks",
                "rule_name": "A 文件 INT_ID > 0",
                "target_variable_tag": "[source-a-items-INT_ID]",
                "rule_type": "fixed_value_compare",
                "operator": "gt",
                "expected_value": "0",
            },
            {
                "rule_id": "rule-b1",
                "group_id": "basic-checks",
                "rule_name": "B 文件 DESC 不能为空",
                "target_variable_tag": "[source-b-items-DESC]",
                "rule_type": "not_null",
            },
            {
                "rule_id": "rule-b2",
                "group_id": "basic-checks",
                "rule_name": "B 文件 INT_ID 必须唯一",
                "target_variable_tag": "[source-b-items-INT_ID]",
                "rule_type": "unique",
            },
        ],
    }

    async with _auth_client_ctx(auth_headers) as client:
        await client.put("/api/v1/fixed-rules/config", json=payload)
        execute_response = await client.post(
            "/api/v1/fixed-rules/execute",
            json={"selected_rule_ids": ["rule-b1"]},
        )

    assert execute_response.status_code == 200
    abnormal_results = execute_response.json()["data"]["abnormal_results"]
    assert len(abnormal_results) == 1
    assert abnormal_results[0]["rule_name"] == "B 文件 DESC 不能为空"


@pytest.mark.anyio
async def test_execute_fixed_rules_supports_trimmed_sheet_and_column_identifiers(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证项目校验配置中被 trim 的 Sheet/列名仍能解析到真实表头并正常执行。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "fixed_rules_trimmed_headers.xlsx",
        {
            "STR_ABSwitch  ": ["on", "off"],
            "DESC3": ["开", "关"],
        },
        sheet_name="Quest  ",
    )

    payload = {
        "version": 5,
        "configured": True,
        "sources": [
            {
                "id": "source-space",
                "type": "local_excel",
                "path": str(workbook_path),
                "pathOrUrl": str(workbook_path),
            }
        ],
        "variables": [
            {
                "tag": "[source-space-quest-switch]",
                "source_id": "source-space",
                "sheet": "Quest",
                "variable_kind": "single",
                "column": "STR_ABSwitch",
                "expected_type": "str",
            }
        ],
        "groups": [
            {"group_id": "ungrouped", "group_name": "未分组", "builtin": True},
        ],
        "rules": [
            {
                "rule_id": "rule-not-null",
                "group_id": "ungrouped",
                "rule_name": "开关不能为空",
                "target_variable_tag": "[source-space-quest-switch]",
                "rule_type": "not_null",
            }
        ],
    }

    async with _auth_client_ctx(auth_headers) as client:
        save_response = await client.put("/api/v1/fixed-rules/config", json=payload)
        execute_response = await client.post("/api/v1/fixed-rules/execute")

    assert save_response.status_code == 200
    assert execute_response.status_code == 200
    execute_payload = execute_response.json()
    assert execute_payload["meta"]["failed_sources"] == []
    assert execute_payload["meta"]["total_rows_scanned"] == 2
    assert execute_payload["data"]["abnormal_results"] == []


@pytest.mark.anyio
async def test_execute_fixed_rules_returns_first_page_and_supports_result_pagination(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证项目校验执行后只返回第一页，并可按 result_id 翻页。"""
    workbook_path = _create_fixed_rules_paged_workbook(
        tmp_path / "fixed_rules_paged.xlsx",
    )
    target_tag = _build_single_tag("items-source", "items", "INT_ID")
    dict_tag = _build_single_tag("items-source", "items", "DICT_ID")
    payload = _build_v4_payload(
        workbook_path,
        variables=[
            {
                "tag": target_tag,
                "source_id": "items-source",
                "sheet": "items",
                "variable_kind": "single",
                "column": "INT_ID",
                "expected_type": "str",
            },
            {
                "tag": dict_tag,
                "source_id": "items-source",
                "sheet": "items",
                "variable_kind": "single",
                "column": "DICT_ID",
                "expected_type": "str",
            },
        ],
        rules=[
            {
                "rule_id": "rule-int-id-in-dict",
                "group_id": "basic-checks",
                "rule_name": "INT_ID 必须包含于 DICT_ID",
                "target_variable_tag": target_tag,
                "rule_type": "cross_table_mapping",
                "reference_variable_tag": dict_tag,
            }
        ],
    )

    async with _auth_client_ctx(auth_headers) as client:
        save_response = await client.put("/api/v1/fixed-rules/config", json=payload)
        assert save_response.status_code == 200

        execute_response = await client.post(
            "/api/v1/fixed-rules/execute",
            json={"page": 1, "size": 20},
        )

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
            f"/api/v1/fixed-rules/results/{result_id}",
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


@pytest.mark.anyio
async def test_fixed_rules_composite_condition_keeps_real_spaced_field_names(
    tmp_path: Path,
    auth_headers: dict[str, str],
) -> None:
    """验证组合条件校验会把裁剪过的字段名解析回 Excel 中的真实列名。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "fixed_rules_composite_spaced_headers.xlsx",
        {
            "INT_ID": [1, 2],
            "STR_ABSwitch  ": ["A", "B"],
            "DESC3": ["A", "B"],
        },
        sheet_name="Quest  ",
    )
    composite_variable = {
        "tag": "[source-space-quest-composite]",
        "source_id": "source-space",
        "sheet": "Quest",
        "variable_kind": "composite",
        "columns": ["INT_ID", "STR_ABSwitch", "DESC3"],
        "key_column": "INT_ID",
        "append_index_to_key": False,
        "expected_type": "json",
    }
    payload = {
        "version": 5,
        "configured": True,
        "sources": [
            {
                "id": "source-space",
                "type": "local_excel",
                "path": str(workbook_path),
                "pathOrUrl": str(workbook_path),
            }
        ],
        "variables": [composite_variable],
        "groups": [
            {"group_id": "ungrouped", "group_name": "未分组", "builtin": True},
            {"group_id": "basic-checks", "group_name": "基础校验", "builtin": False},
        ],
        "rules": [
            {
                "rule_id": "rule-composite-spaced",
                "group_id": "basic-checks",
                "rule_name": "组合字段尾部空格兼容",
                "target_variable_tag": composite_variable["tag"],
                "rule_type": "composite_condition_check",
                "composite_config": {
                    "global_filters": [],
                    "branches": [
                        {
                            "branch_id": "branch-spaced",
                            "filters": [],
                            "assertions": [
                                {
                                    "condition_id": "assert-spaced-field",
                                    "field": "DESC3",
                                    "operator": "eq",
                                    "value_source": "field",
                                    "expected_field": "STR_ABSwitch",
                                }
                            ],
                        }
                    ],
                },
            }
        ],
    }

    async with _auth_client_ctx(auth_headers) as client:
        save_response = await client.put("/api/v1/fixed-rules/config", json=payload)
        execute_response = await client.post("/api/v1/fixed-rules/execute")

    assert save_response.status_code == 200
    save_payload = save_response.json()["data"]
    assert save_payload["variables"][0]["sheet"] == "Quest  "
    assert save_payload["variables"][0]["columns"] == ["INT_ID", "STR_ABSwitch  ", "DESC3"]
    saved_assertion = save_payload["rules"][0]["composite_config"]["branches"][0]["assertions"][0]
    assert saved_assertion["field"] == "DESC3"
    assert saved_assertion["expected_field"] == "STR_ABSwitch  "

    assert execute_response.status_code == 200
    execute_payload = execute_response.json()
    assert execute_payload["meta"]["failed_sources"] == []
    assert execute_payload["meta"]["total_rows_scanned"] == 2
    assert execute_payload["data"]["abnormal_results"] == []


@pytest.mark.anyio
async def test_fixed_rules_svn_update_deduplicates_working_copies_from_saved_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    auth_headers: dict[str, str],
) -> None:
    """验证 SVN 更新会按已保存数据源目录去重后统一执行。"""
    dir_a = tmp_path / "svn-a"
    dir_b = tmp_path / "svn-b"
    dir_a.mkdir()
    dir_b.mkdir()
    workbook_a1 = _create_fixed_rules_workbook(
        dir_a / "items_a1.xlsx",
        {"INT_ID": [1, 2, 3], "DESC": ["a1", "a2", "a3"]},
    )
    workbook_a2 = _create_fixed_rules_workbook(
        dir_a / "items_a2.xlsx",
        {"INT_ID": [4, 5, 6], "DESC": ["b1", "b2", "b3"]},
    )
    workbook_b = _create_fixed_rules_workbook(
        dir_b / "items_b.xlsx",
        {"INT_ID": [7, 8, 9], "DESC": ["c1", "c2", "c3"]},
    )
    payload = {
        "version": 4,
        "configured": True,
        "sources": [
            {
                "id": "source-a1",
                "type": "local_excel",
                "path": str(workbook_a1),
                "pathOrUrl": str(workbook_a1),
            },
            {
                "id": "source-a2",
                "type": "local_excel",
                "path": str(workbook_a2),
                "pathOrUrl": str(workbook_a2),
            },
            {
                "id": "source-b",
                "type": "local_excel",
                "path": str(workbook_b),
                "pathOrUrl": str(workbook_b),
            },
        ],
        "variables": [
            {
                "tag": "[source-a1-items-INT_ID]",
                "source_id": "source-a1",
                "sheet": "items",
                "variable_kind": "single",
                "column": "INT_ID",
                "expected_type": "str",
            }
        ],
        "groups": [{"group_id": "ungrouped", "group_name": "未分组", "builtin": True}],
        "rules": [
            {
                "rule_id": "rule-a",
                "group_id": "ungrouped",
                "rule_name": "A",
                "target_variable_tag": "[source-a1-items-INT_ID]",
                "rule_type": "fixed_value_compare",
                "operator": "gt",
                "expected_value": "0",
            }
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

    async with _auth_client_ctx(auth_headers) as client:
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
    monkeypatch: pytest.MonkeyPatch,
    auth_headers: dict[str, str],
) -> None:
    """验证当前环境缺少 svn CLI 时会返回明确提示。"""
    workbook_path = _create_fixed_rules_workbook(
        tmp_path / "svn_sample.xlsx",
        {"INT_ID": [1, 2, 3], "DESC": ["a", "b", "c"]},
    )
    payload = _build_v4_payload(workbook_path)

    def raise_missing_cli(_: Path) -> dict[str, str]:
        raise NotImplementedError(
            "当前环境未检测到 svn 命令，请先安装 SVN CLI，或在后端配置中指定 svn 可执行文件路径。"
        )

    monkeypatch.setattr(fixed_rules_service, "update_svn_working_copy", raise_missing_cli)

    async with _auth_client_ctx(auth_headers) as client:
        await client.put("/api/v1/fixed-rules/config", json=payload)
        response = await client.post("/api/v1/fixed-rules/svn-update")

    assert response.status_code == 400
    assert "svn 命令" in response.json()["detail"]

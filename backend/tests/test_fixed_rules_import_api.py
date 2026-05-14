"""个人校验规则导入项目校验接口测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from backend.app.database import async_session_factory
from backend.app.models import WorkbenchConfigRecord
from backend.tests.conftest import seed_fixed_rules_config


def _create_workbook(path: Path, columns: dict[str, list[object]]) -> Path:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(columns).to_excel(writer, sheet_name="items", index=False)
    return path


async def _seed_workbench_config(
    project_id: int,
    user_id: int,
    config: dict[str, object],
) -> None:
    async with async_session_factory() as session:
        session.add(
            WorkbenchConfigRecord(
                project_id=project_id,
                user_id=user_id,
                config_json=json.dumps(config, ensure_ascii=False),
            )
        )
        await session.commit()


async def _get_test_user_id() -> int:
    async with async_session_factory() as session:
        from sqlalchemy import select

        from backend.app.models import User

        result = await session.execute(select(User.id).where(User.username == "testuser"))
        return int(result.scalar_one())


def _workbench_config(
    workbook_path: Path,
    *,
    source_id: str = "src_items",
    variable_tag: str = "[personal-items-composite]",
    rule_id: str = "personal-rule-composite",
    rule_type: str = "composite_condition_check",
) -> dict[str, object]:
    if rule_type == "not_null":
        variable = {
            "tag": "[personal-items-id]",
            "source_id": source_id,
            "sheet": "items",
            "variable_kind": "single",
            "column": "INT_ID",
            "expected_type": "str",
        }
        rule = {
            "rule_id": rule_id,
            "group_id": "personal-group",
            "rule_name": "INT_ID 非空",
            "target_variable_tag": "[personal-items-id]",
            "rule_type": "not_null",
        }
    else:
        variable = {
            "tag": variable_tag,
            "source_id": source_id,
            "sheet": "items",
            "variable_kind": "composite",
            "columns": ["INT_ID", "INT_Faction", "INT_Group"],
            "key_column": "INT_ID",
            "append_index_to_key": False,
            "expected_type": "json",
        }
        rule = {
            "rule_id": rule_id,
            "group_id": "personal-group",
            "rule_name": "阵营分组检查",
            "target_variable_tag": variable_tag,
            "rule_type": "composite_condition_check",
            "composite_config": {
                "global_filters": [],
                "branches": [
                    {
                        "branch_id": "branch-1",
                        "filters": [
                            {
                                "condition_id": "filter-1",
                                "field": "INT_Faction",
                                "operator": "eq",
                                "value_source": "literal",
                                "expected_value": "0",
                            }
                        ],
                        "assertions": [
                            {
                                "condition_id": "assert-1",
                                "field": "INT_Group",
                                "operator": "not_null",
                            }
                        ],
                    }
                ],
            },
        }

    return {
        "sources": [
            {
                "id": source_id,
                "type": "local_excel",
                "pathOrUrl": str(workbook_path),
            }
        ],
        "variables": [variable],
        "ruleGroups": [
            {"group_id": "personal-group", "group_name": "个人导入组", "builtin": False}
        ],
        "orchestrationRules": [rule],
    }


def _project_config(
    workbook_path: Path,
    *,
    source_id: str = "src_items",
    variables: list[dict[str, object]] | None = None,
    rules: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "version": 6,
        "configured": True,
        "sources": [
            {
                "id": source_id,
                "type": "local_excel",
                "pathOrUrl": str(workbook_path),
            }
        ],
        "variables": variables or [],
        "groups": [{"group_id": "ungrouped", "group_name": "未分组", "builtin": True}],
        "rules": rules or [],
        "local_path_replacement_presets": [],
        "svn_path_replacement_presets": [],
    }


@pytest.mark.anyio
async def test_import_preview_reuses_project_source_and_composite_superset(
    auth_client,
    test_project_id,
    tmp_path: Path,
):
    personal_path = _create_workbook(
        tmp_path / "personal.xlsx",
        {"INT_ID": [1], "INT_Faction": [0], "INT_Group": [10]},
    )
    project_path = _create_workbook(
        tmp_path / "project.xlsx",
        {"INT_ID": [1], "INT_Faction": [0], "INT_Group": [10], "STR_Name": ["a"]},
    )
    user_id = await _get_test_user_id()
    await _seed_workbench_config(test_project_id, user_id, _workbench_config(personal_path))
    await seed_fixed_rules_config(
        _project_config(
            project_path,
            variables=[
                {
                    "tag": "[project-items-wide]",
                    "source_id": "src_items",
                    "sheet": "items",
                    "variable_kind": "composite",
                    "columns": ["INT_ID", "INT_Faction", "INT_Group", "STR_Name"],
                    "key_column": "INT_ID",
                    "append_index_to_key": False,
                    "expected_type": "json",
                }
            ],
        ),
        test_project_id,
    )

    response = await auth_client.post(
        "/api/v1/fixed-rules/import-preview",
        json={"selected_rule_ids": ["personal-rule-composite"]},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"] == {"total": 1, "ready": 1, "duplicate": 0, "skipped": 0}
    assert data["sources"][0]["final_source"]["pathOrUrl"] == str(project_path)
    assert data["variables"][0]["mode"] == "project"
    assert data["variables"][0]["final_tag"] == "[project-items-wide]"
    assert data["rules"][0]["candidate_rule"]["target_variable_tag"] == "[project-items-wide]"

    import_response = await auth_client.post(
        "/api/v1/fixed-rules/import-from-workbench",
        json={"selected_rule_ids": ["personal-rule-composite"]},
    )

    assert import_response.status_code == 200
    imported = import_response.json()["data"]
    assert len(imported["sources"]) == 1
    assert imported["sources"][0]["pathOrUrl"] == str(project_path)
    assert len(imported["variables"]) == 1
    assert imported["rules"][0]["target_variable_tag"] == "[project-items-wide]"


@pytest.mark.anyio
async def test_import_source_override_adds_custom_source_without_changing_project_source(
    auth_client,
    test_project_id,
    tmp_path: Path,
):
    personal_path = _create_workbook(tmp_path / "personal.xlsx", {"INT_ID": [1]})
    project_path = _create_workbook(tmp_path / "project.xlsx", {"INT_ID": [1]})
    user_id = await _get_test_user_id()
    await _seed_workbench_config(
        test_project_id,
        user_id,
        _workbench_config(personal_path, rule_type="not_null", rule_id="personal-rule-not-null"),
    )
    await seed_fixed_rules_config(_project_config(project_path), test_project_id)

    payload = {
        "selected_rule_ids": ["personal-rule-not-null"],
        "source_overrides": {
            "src_items": {
                "id": "src_items_import",
                "type": "local_excel",
                "pathOrUrl": str(personal_path),
            }
        },
    }
    response = await auth_client.post("/api/v1/fixed-rules/import-from-workbench", json=payload)

    assert response.status_code == 200
    imported = response.json()["data"]
    source_map = {source["id"]: source for source in imported["sources"]}
    assert source_map["src_items"]["pathOrUrl"] == str(project_path)
    assert source_map["src_items_import"]["pathOrUrl"] == str(personal_path)
    imported_variable = next(
        variable for variable in imported["variables"] if variable["tag"] == "[personal-items-id]"
    )
    assert imported_variable["source_id"] == "src_items_import"


@pytest.mark.anyio
async def test_import_preview_skips_when_project_source_lacks_required_field(
    auth_client,
    test_project_id,
    tmp_path: Path,
):
    personal_path = _create_workbook(
        tmp_path / "personal.xlsx",
        {"INT_ID": [1], "INT_Faction": [0], "INT_Group": [10]},
    )
    project_path = _create_workbook(
        tmp_path / "project.xlsx",
        {"INT_ID": [1], "INT_Faction": [0]},
    )
    user_id = await _get_test_user_id()
    await _seed_workbench_config(test_project_id, user_id, _workbench_config(personal_path))
    await seed_fixed_rules_config(_project_config(project_path), test_project_id)

    response = await auth_client.post(
        "/api/v1/fixed-rules/import-preview",
        json={"selected_rule_ids": ["personal-rule-composite"]},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"]["ready"] == 0
    assert data["summary"]["skipped"] == 1
    assert "INT_Group" in data["rules"][0]["reason"]


@pytest.mark.anyio
async def test_import_preview_skips_duplicate_rule(
    auth_client,
    test_project_id,
    tmp_path: Path,
):
    workbook_path = _create_workbook(tmp_path / "shared.xlsx", {"INT_ID": [1]})
    user_id = await _get_test_user_id()
    await _seed_workbench_config(
        test_project_id,
        user_id,
        _workbench_config(workbook_path, rule_type="not_null", rule_id="personal-rule-not-null"),
    )
    variable = {
        "tag": "[personal-items-id]",
        "source_id": "src_items",
        "sheet": "items",
        "variable_kind": "single",
        "column": "INT_ID",
        "expected_type": "str",
    }
    await seed_fixed_rules_config(
        _project_config(
            workbook_path,
            variables=[variable],
            rules=[
                {
                    "rule_id": "project-rule-not-null",
                    "group_id": "ungrouped",
                    "rule_name": "已有非空",
                    "target_variable_tag": "[personal-items-id]",
                    "rule_type": "not_null",
                }
            ],
        ),
        test_project_id,
    )

    response = await auth_client.post(
        "/api/v1/fixed-rules/import-preview",
        json={"selected_rule_ids": ["personal-rule-not-null"]},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"] == {"total": 1, "ready": 0, "duplicate": 1, "skipped": 0}


@pytest.mark.anyio
async def test_import_preview_can_rename_conflicting_variable_after_source_override(
    auth_client,
    test_project_id,
    tmp_path: Path,
):
    personal_path = _create_workbook(tmp_path / "personal.xlsx", {"INT_ID": [1]})
    project_path = _create_workbook(tmp_path / "project.xlsx", {"INT_ID": [1]})
    user_id = await _get_test_user_id()
    await _seed_workbench_config(
        test_project_id,
        user_id,
        _workbench_config(personal_path, rule_type="not_null", rule_id="personal-rule-not-null"),
    )
    await seed_fixed_rules_config(
        _project_config(
            project_path,
            variables=[
                {
                    "tag": "[personal-items-id]",
                    "source_id": "src_items",
                    "sheet": "items",
                    "variable_kind": "single",
                    "column": "INT_ID",
                    "expected_type": "str",
                }
            ],
        ),
        test_project_id,
    )

    response = await auth_client.post(
        "/api/v1/fixed-rules/import-preview",
        json={
            "selected_rule_ids": ["personal-rule-not-null"],
            "source_overrides": {
                "src_items": {
                    "id": "src_items_import",
                    "type": "local_excel",
                    "pathOrUrl": str(personal_path),
                }
            },
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"] == {"total": 1, "ready": 0, "duplicate": 0, "skipped": 1}
    variable = data["variables"][0]
    assert variable["issue_code"] == "tag_conflict"
    assert variable["can_rename"] is True
    assert variable["suggested_tag"] == "[personal-items-id_import]"
    assert "修改变量池标签" in variable["issue"]


@pytest.mark.anyio
async def test_import_variable_tag_override_adds_custom_source_variable_and_rewrites_rule(
    auth_client,
    test_project_id,
    tmp_path: Path,
):
    personal_path = _create_workbook(tmp_path / "personal.xlsx", {"INT_ID": [1]})
    project_path = _create_workbook(tmp_path / "project.xlsx", {"INT_ID": [1]})
    user_id = await _get_test_user_id()
    await _seed_workbench_config(
        test_project_id,
        user_id,
        _workbench_config(personal_path, rule_type="not_null", rule_id="personal-rule-not-null"),
    )
    await seed_fixed_rules_config(
        _project_config(
            project_path,
            variables=[
                {
                    "tag": "[personal-items-id]",
                    "source_id": "src_items",
                    "sheet": "items",
                    "variable_kind": "single",
                    "column": "INT_ID",
                    "expected_type": "str",
                }
            ],
        ),
        test_project_id,
    )

    payload = {
        "selected_rule_ids": ["personal-rule-not-null"],
        "source_overrides": {
            "src_items": {
                "id": "src_items_import",
                "type": "local_excel",
                "pathOrUrl": str(personal_path),
            }
        },
        "variable_tag_overrides": {
            "[personal-items-id]": "[personal-items-id_import]",
        },
    }
    preview_response = await auth_client.post(
        "/api/v1/fixed-rules/import-preview",
        json=payload,
    )

    assert preview_response.status_code == 200
    preview = preview_response.json()["data"]
    assert preview["summary"] == {"total": 1, "ready": 1, "duplicate": 0, "skipped": 0}
    assert preview["variables"][0]["mode"] == "new"
    assert preview["variables"][0]["final_tag"] == "[personal-items-id_import]"
    assert (
        preview["rules"][0]["candidate_rule"]["target_variable_tag"]
        == "[personal-items-id_import]"
    )

    import_response = await auth_client.post(
        "/api/v1/fixed-rules/import-from-workbench",
        json=payload,
    )

    assert import_response.status_code == 200
    imported = import_response.json()["data"]
    source_map = {source["id"]: source for source in imported["sources"]}
    assert source_map["src_items"]["pathOrUrl"] == str(project_path)
    assert source_map["src_items_import"]["pathOrUrl"] == str(personal_path)
    variable_map = {variable["tag"]: variable for variable in imported["variables"]}
    assert variable_map["[personal-items-id]"]["source_id"] == "src_items"
    assert variable_map["[personal-items-id_import]"]["source_id"] == "src_items_import"
    assert imported["rules"][0]["target_variable_tag"] == "[personal-items-id_import]"


@pytest.mark.anyio
async def test_import_variable_tag_override_reuses_existing_compatible_project_variable(
    auth_client,
    test_project_id,
    tmp_path: Path,
):
    workbook_path = _create_workbook(tmp_path / "shared.xlsx", {"INT_ID": [1]})
    user_id = await _get_test_user_id()
    await _seed_workbench_config(
        test_project_id,
        user_id,
        _workbench_config(workbook_path, rule_type="not_null", rule_id="personal-rule-not-null"),
    )
    await seed_fixed_rules_config(
        _project_config(
            workbook_path,
            variables=[
                {
                    "tag": "[project-items-id]",
                    "source_id": "src_items",
                    "sheet": "items",
                    "variable_kind": "single",
                    "column": "INT_ID",
                    "expected_type": "str",
                }
            ],
        ),
        test_project_id,
    )

    response = await auth_client.post(
        "/api/v1/fixed-rules/import-preview",
        json={
            "selected_rule_ids": ["personal-rule-not-null"],
            "variable_tag_overrides": {
                "[personal-items-id]": "[project-items-id]",
            },
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"] == {"total": 1, "ready": 1, "duplicate": 0, "skipped": 0}
    assert data["variables"][0]["mode"] == "project"
    assert data["variables"][0]["final_tag"] == "[project-items-id]"
    assert data["rules"][0]["candidate_rule"]["target_variable_tag"] == "[project-items-id]"


@pytest.mark.anyio
async def test_import_preview_skips_duplicate_new_variable_tag_overrides(
    auth_client,
    test_project_id,
    tmp_path: Path,
):
    workbook_path = _create_workbook(tmp_path / "shared.xlsx", {"INT_A": [1], "INT_B": [2]})
    user_id = await _get_test_user_id()
    await _seed_workbench_config(
        test_project_id,
        user_id,
        {
            "sources": [
                {
                    "id": "src_items",
                    "type": "local_excel",
                    "pathOrUrl": str(workbook_path),
                }
            ],
            "variables": [
                {
                    "tag": "var_a",
                    "source_id": "src_items",
                    "sheet": "items",
                    "variable_kind": "single",
                    "column": "INT_A",
                    "expected_type": "str",
                },
                {
                    "tag": "var_b",
                    "source_id": "src_items",
                    "sheet": "items",
                    "variable_kind": "single",
                    "column": "INT_B",
                    "expected_type": "str",
                },
            ],
            "ruleGroups": [
                {"group_id": "personal-group", "group_name": "个人导入组", "builtin": False}
            ],
            "orchestrationRules": [
                {
                    "rule_id": "rule-a",
                    "group_id": "personal-group",
                    "rule_name": "A 非空",
                    "target_variable_tag": "var_a",
                    "rule_type": "not_null",
                },
                {
                    "rule_id": "rule-b",
                    "group_id": "personal-group",
                    "rule_name": "B 非空",
                    "target_variable_tag": "var_b",
                    "rule_type": "not_null",
                },
            ],
        },
    )
    await seed_fixed_rules_config(_project_config(workbook_path), test_project_id)

    response = await auth_client.post(
        "/api/v1/fixed-rules/import-preview",
        json={
            "selected_rule_ids": ["rule-a", "rule-b"],
            "variable_tag_overrides": {
                "var_a": "shared_import",
                "var_b": "shared_import",
            },
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"] == {"total": 2, "ready": 0, "duplicate": 0, "skipped": 2}
    assert {variable["issue_code"] for variable in data["variables"]} == {
        "duplicate_target_tag"
    }

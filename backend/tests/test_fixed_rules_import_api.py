"""个人校验规则导入项目校验接口回归测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from backend.app.database import async_session_factory
from backend.app.fixed_rules.db_service import load_fixed_rules_config_from_db
from backend.app.models import User, WorkbenchConfigRecord
from backend.tests.conftest import seed_fixed_rules_config

import pytest


pytestmark = pytest.mark.anyio


def _create_workbook(target_path: Path) -> Path:
    with pd.ExcelWriter(target_path, engine="openpyxl") as writer:
        pd.DataFrame({"INT_ID": [1, 2, 3], "Name": ["a", "b", "c"]}).to_excel(
            writer,
            sheet_name="items",
            index=False,
        )
    return target_path


def _source(source_id: str, path: Path | str) -> dict[str, object]:
    locator = str(path)
    return {
        "id": source_id,
        "type": "local_excel",
        "path": locator,
        "pathOrUrl": locator,
    }


def _variable(source_id: str, tag: str = "[items-Name]") -> dict[str, object]:
    return {
        "tag": tag,
        "source_id": source_id,
        "sheet": "items",
        "variable_kind": "single",
        "column": "Name",
        "expected_type": "str",
    }


def _composite_variable(source_id: str, tag: str = "[items-composite]") -> dict[str, object]:
    return {
        "tag": tag,
        "source_id": source_id,
        "sheet": "items",
        "variable_kind": "composite",
        "columns": ["INT_ID", "Name"],
        "key_column": "INT_ID",
        "append_index_to_key": False,
        "expected_type": "json",
    }


def _rule(tag: str = "[items-Name]", rule_id: str = "rule-not-null") -> dict[str, object]:
    return {
        "rule_id": rule_id,
        "group_id": "ungrouped",
        "rule_name": "Name 非空",
        "target_variable_tag": tag,
        "rule_type": "not_null",
    }


def _workbench_payload(workbook_path: Path) -> dict[str, object]:
    return {
        "sources": [_source("personal-source", workbook_path)],
        "variables": [_variable("personal-source")],
        "ruleGroups": [{"group_id": "ungrouped", "group_name": "未分组", "builtin": True}],
        "orchestrationRules": [_rule()],
    }


async def _seed_workbench_config(project_id: int, user_id: int, payload: dict[str, object]) -> None:
    async with async_session_factory() as session:
        session.add(
            WorkbenchConfigRecord(
                project_id=project_id,
                user_id=user_id,
                config_json=json.dumps(payload, ensure_ascii=False),
            )
        )
        await session.commit()


async def _current_user_id() -> int:
    async with async_session_factory() as session:
        from sqlalchemy import select

        result = await session.execute(select(User.id).where(User.username == "testuser"))
        return int(result.scalar_one())


async def test_workbench_import_draft_returns_personal_rules(
    auth_client,
    test_project_id: int,
    tmp_path: Path,
) -> None:
    user_id = await _current_user_id()
    workbook_path = _create_workbook(tmp_path / "personal.xlsx")
    await _seed_workbench_config(test_project_id, user_id, _workbench_payload(workbook_path))

    response = await auth_client.get("/api/v1/fixed-rules/import/workbench/draft")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["importable_rules"][0]["rule_id"] == "rule-not-null"
    assert data["source_mappings"][0]["recommended_action"] == "new"


async def test_workbench_import_preview_does_not_persist_project_config(
    auth_client,
    test_project_id: int,
    tmp_path: Path,
) -> None:
    user_id = await _current_user_id()
    workbook_path = _create_workbook(tmp_path / "personal.xlsx")
    await _seed_workbench_config(test_project_id, user_id, _workbench_payload(workbook_path))

    response = await auth_client.post(
        "/api/v1/fixed-rules/import/workbench/preview",
        json={"scope": {"mode": "all"}, "source_mappings": []},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"]["rules_new"] == 1
    assert data["blocking_errors"] == []
    async with async_session_factory() as session:
        assert await load_fixed_rules_config_from_db(session, test_project_id) is None


async def test_workbench_import_commit_saves_project_config(
    auth_client,
    test_project_id: int,
    tmp_path: Path,
) -> None:
    user_id = await _current_user_id()
    workbook_path = _create_workbook(tmp_path / "personal.xlsx")
    await _seed_workbench_config(test_project_id, user_id, _workbench_payload(workbook_path))

    response = await auth_client.post(
        "/api/v1/fixed-rules/import/workbench/commit",
        json={"scope": {"mode": "all"}, "source_mappings": []},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["rules"][0]["rule_id"] == "rule-not-null"
    assert response.json()["meta"]["import_summary"]["rules_new"] == 1


async def test_workbench_import_commit_failure_does_not_overwrite_project_config(
    auth_client,
    test_project_id: int,
    tmp_path: Path,
) -> None:
    user_id = await _current_user_id()
    workbook_path = _create_workbook(tmp_path / "personal.xlsx")
    await _seed_workbench_config(test_project_id, user_id, _workbench_payload(workbook_path))
    original_config = {
        "version": 6,
        "configured": True,
        "sources": [_source("project-source", workbook_path)],
        "variables": [_variable("project-source", "[project-Name]")],
        "groups": [{"group_id": "ungrouped", "group_name": "未分组", "builtin": True}],
        "rules": [_rule("[project-Name]", "project-rule")],
        "local_path_replacement_presets": [],
        "selected_local_path_replacement_preset": None,
        "svn_path_replacement_presets": [],
        "selected_svn_path_replacement_preset": None,
    }
    await seed_fixed_rules_config(original_config, test_project_id)

    response = await auth_client.post(
        "/api/v1/fixed-rules/import/workbench/commit",
        json={
            "scope": {"mode": "all"},
            "source_mappings": [
                {
                    "personal_source_id": "personal-source",
                    "action": "replace",
                    "next_source": _source("personal-source", tmp_path / "missing.xlsx"),
                }
            ],
        },
    )

    assert response.status_code == 400
    async with async_session_factory() as session:
        persisted = await load_fixed_rules_config_from_db(session, test_project_id)
    assert persisted is not None
    assert persisted["rules"][0]["rule_id"] == "project-rule"


async def test_workbench_import_modified_source_path_is_validated_and_committed(
    auth_client,
    test_project_id: int,
    tmp_path: Path,
) -> None:
    user_id = await _current_user_id()
    release_path = _create_workbook(tmp_path / "release.xlsx")
    missing_dev_path = tmp_path / "dev-missing.xlsx"
    await _seed_workbench_config(test_project_id, user_id, _workbench_payload(missing_dev_path))
    payload = {
        "scope": {"mode": "all"},
        "source_mappings": [
            {
                "personal_source_id": "personal-source",
                "action": "replace",
                "next_source": _source("personal-source", release_path),
                "confirmed": True,
            }
        ],
    }

    preview_response = await auth_client.post(
        "/api/v1/fixed-rules/import/workbench/preview",
        json=payload,
    )
    commit_response = await auth_client.post(
        "/api/v1/fixed-rules/import/workbench/commit",
        json=payload,
    )

    assert preview_response.status_code == 200
    preview_data = preview_response.json()["data"]
    assert preview_data["blocking_errors"] == []
    assert preview_data["variable_previews"][0]["status"] == "ok"
    assert commit_response.status_code == 200
    committed_source = commit_response.json()["data"]["sources"][0]
    assert committed_source["pathOrUrl"] == str(release_path)


async def test_workbench_import_preview_blocks_missing_complex_rule_variable(
    auth_client,
    test_project_id: int,
    tmp_path: Path,
) -> None:
    user_id = await _current_user_id()
    workbook_path = _create_workbook(tmp_path / "personal.xlsx")
    payload = _workbench_payload(workbook_path)
    payload["variables"] = []
    payload["orchestrationRules"] = [
        {
            "rule_id": "pipeline-missing",
            "group_id": "ungrouped",
            "rule_name": "串行缺变量",
            "target_variable_tag": "[missing]",
            "rule_type": "multi_composite_pipeline_check",
            "pipeline_config": {
                "nodes": [
                    {
                        "node_id": "node-1",
                        "variable_tag": "[missing]",
                        "filters": [],
                        "assertions": [
                            {
                                "condition_id": "assert-1",
                                "field": "__key__",
                                "operator": "not_null",
                            }
                        ],
                    }
                ]
            },
        }
    ]
    await _seed_workbench_config(test_project_id, user_id, payload)

    response = await auth_client.post(
        "/api/v1/fixed-rules/import/workbench/preview",
        json={"scope": {"mode": "all"}, "source_mappings": []},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["blocking_errors"]
    assert "missing" in data["blocking_errors"][0]


async def test_workbench_import_preview_auto_replaces_same_id_different_path(
    auth_client,
    test_project_id: int,
    tmp_path: Path,
) -> None:
    user_id = await _current_user_id()
    personal_path = _create_workbook(tmp_path / "personal.xlsx")
    project_path = _create_workbook(tmp_path / "project.xlsx")
    payload = _workbench_payload(personal_path)
    payload["sources"] = [_source("shared-source", personal_path)]
    payload["variables"] = [_variable("shared-source")]
    await _seed_workbench_config(test_project_id, user_id, payload)
    await seed_fixed_rules_config(
        {
            "version": 6,
            "configured": True,
            "sources": [_source("shared-source", project_path)],
            "variables": [],
            "groups": [{"group_id": "ungrouped", "group_name": "未分组", "builtin": True}],
            "rules": [],
            "local_path_replacement_presets": [],
            "selected_local_path_replacement_preset": None,
            "svn_path_replacement_presets": [],
            "selected_svn_path_replacement_preset": None,
        },
        test_project_id,
    )

    response = await auth_client.post(
        "/api/v1/fixed-rules/import/workbench/preview",
        json={"scope": {"mode": "all"}, "source_mappings": []},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["blocking_errors"] == []
    assert data["source_results"][0]["status"] == "new"
    assert data["source_results"][0]["next_id"] == "shared-source-import-2"


async def test_workbench_import_variable_tag_conflict_can_be_renamed(
    auth_client,
    test_project_id: int,
    tmp_path: Path,
) -> None:
    user_id = await _current_user_id()
    personal_path = _create_workbook(tmp_path / "personal.xlsx")
    project_path = _create_workbook(tmp_path / "project.xlsx")
    await _seed_workbench_config(test_project_id, user_id, _workbench_payload(personal_path))
    await seed_fixed_rules_config(
        {
            "version": 6,
            "configured": True,
            "sources": [_source("project-source", project_path)],
            "variables": [_variable("project-source")],
            "groups": [{"group_id": "ungrouped", "group_name": "未分组", "builtin": True}],
            "rules": [],
            "local_path_replacement_presets": [],
            "selected_local_path_replacement_preset": None,
            "svn_path_replacement_presets": [],
            "selected_svn_path_replacement_preset": None,
        },
        test_project_id,
    )

    response = await auth_client.post(
        "/api/v1/fixed-rules/import/workbench/preview",
        json={
            "scope": {"mode": "all"},
            "source_mappings": [],
            "conflict_resolutions": {
                "variable_tags": {"[items-Name]": "[items-Name-import]"},
                "rule_names": {},
                "group_names": {},
            },
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["blocking_errors"] == []
    imported_rule = next(
        rule
        for rule in data["next_config_preview"]["rules"]
        if rule["rule_id"] == "rule-not-null"
    )
    assert imported_rule["target_variable_tag"] == "[items-Name-import]"


async def test_workbench_import_variable_tag_conflict_auto_gets_import_suffix(
    auth_client,
    test_project_id: int,
    tmp_path: Path,
) -> None:
    user_id = await _current_user_id()
    personal_path = _create_workbook(tmp_path / "personal.xlsx")
    project_path = _create_workbook(tmp_path / "project.xlsx")
    await _seed_workbench_config(test_project_id, user_id, _workbench_payload(personal_path))
    await seed_fixed_rules_config(
        {
            "version": 6,
            "configured": True,
            "sources": [_source("project-source", project_path)],
            "variables": [_variable("project-source")],
            "groups": [{"group_id": "ungrouped", "group_name": "未分组", "builtin": True}],
            "rules": [],
            "local_path_replacement_presets": [],
            "selected_local_path_replacement_preset": None,
            "svn_path_replacement_presets": [],
            "selected_svn_path_replacement_preset": None,
        },
        test_project_id,
    )

    response = await auth_client.post(
        "/api/v1/fixed-rules/import/workbench/preview",
        json={"scope": {"mode": "all"}, "source_mappings": []},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["blocking_errors"] == []
    imported_rule = next(
        rule
        for rule in data["next_config_preview"]["rules"]
        if rule["rule_id"] == "rule-not-null"
    )
    assert imported_rule["target_variable_tag"] == "[items-Name-导入]"
    assert data["variable_results"][0]["next_id"] == "[items-Name-导入]"


async def test_workbench_import_rule_name_conflict_gets_import_suffix(
    auth_client,
    test_project_id: int,
    tmp_path: Path,
) -> None:
    user_id = await _current_user_id()
    personal_path = _create_workbook(tmp_path / "personal.xlsx")
    project_path = _create_workbook(tmp_path / "project.xlsx")
    await _seed_workbench_config(test_project_id, user_id, _workbench_payload(personal_path))
    await seed_fixed_rules_config(
        {
            "version": 6,
            "configured": True,
            "sources": [_source("project-source", project_path)],
            "variables": [_variable("project-source", "[project-Name]")],
            "groups": [{"group_id": "ungrouped", "group_name": "未分组", "builtin": True}],
            "rules": [_rule("[project-Name]", "project-rule")],
            "local_path_replacement_presets": [],
            "selected_local_path_replacement_preset": None,
            "svn_path_replacement_presets": [],
            "selected_svn_path_replacement_preset": None,
        },
        test_project_id,
    )

    response = await auth_client.post(
        "/api/v1/fixed-rules/import/workbench/preview",
        json={"scope": {"mode": "all"}, "source_mappings": []},
    )

    assert response.status_code == 200
    rule_results = response.json()["data"]["rule_results"]
    imported_result = next(item for item in rule_results if item["item_id"] == "rule-not-null")
    assert imported_result["status"] == "renamed"
    assert imported_result["details"]["rule_name"] == "Name 非空-导入"
    assert imported_result["details"]["duplicate_rule"] is True
    assert imported_result["details"]["duplicate_action"] == "rename"


async def test_workbench_import_duplicate_rule_can_be_skipped(
    auth_client,
    test_project_id: int,
    tmp_path: Path,
) -> None:
    user_id = await _current_user_id()
    personal_path = _create_workbook(tmp_path / "personal.xlsx")
    project_path = _create_workbook(tmp_path / "project.xlsx")
    await _seed_workbench_config(test_project_id, user_id, _workbench_payload(personal_path))
    await seed_fixed_rules_config(
        {
            "version": 6,
            "configured": True,
            "sources": [_source("project-source", project_path)],
            "variables": [_variable("project-source", "[project-Name]")],
            "groups": [{"group_id": "ungrouped", "group_name": "未分组", "builtin": True}],
            "rules": [_rule("[project-Name]", "project-rule")],
            "local_path_replacement_presets": [],
            "selected_local_path_replacement_preset": None,
            "svn_path_replacement_presets": [],
            "selected_svn_path_replacement_preset": None,
        },
        test_project_id,
    )
    payload = {
        "scope": {"mode": "all"},
        "source_mappings": [],
        "duplicate_rule_actions": {"rule-not-null": "skip"},
    }

    preview_response = await auth_client.post(
        "/api/v1/fixed-rules/import/workbench/preview",
        json=payload,
    )
    commit_response = await auth_client.post(
        "/api/v1/fixed-rules/import/workbench/commit",
        json=payload,
    )

    assert preview_response.status_code == 200
    preview_data = preview_response.json()["data"]
    skipped_result = next(item for item in preview_data["rule_results"] if item["item_id"] == "rule-not-null")
    assert skipped_result["status"] == "skipped"
    assert skipped_result["details"]["duplicate_rule"] is True
    assert preview_data["summary"]["rules_skipped"] == 1
    assert [rule["rule_id"] for rule in preview_data["next_config_preview"]["rules"]] == ["project-rule"]
    assert [source["id"] for source in preview_data["next_config_preview"]["sources"]] == ["project-source"]
    assert commit_response.status_code == 200
    assert [rule["rule_id"] for rule in commit_response.json()["data"]["rules"]] == ["project-rule"]


async def test_workbench_import_group_name_conflict_gets_import_suffix(
    auth_client,
    test_project_id: int,
    tmp_path: Path,
) -> None:
    user_id = await _current_user_id()
    personal_path = _create_workbook(tmp_path / "personal.xlsx")
    project_path = _create_workbook(tmp_path / "project.xlsx")
    payload = _workbench_payload(personal_path)
    payload["ruleGroups"] = [{"group_id": "personal-group", "group_name": "共享规则组", "builtin": False}]
    payload["orchestrationRules"] = [
        {**_rule(), "group_id": "personal-group"},
    ]
    await _seed_workbench_config(test_project_id, user_id, payload)
    await seed_fixed_rules_config(
        {
            "version": 6,
            "configured": True,
            "sources": [_source("project-source", project_path)],
            "variables": [_variable("project-source", "[project-Name]")],
            "groups": [
                {"group_id": "project-group", "group_name": "共享规则组", "builtin": False},
            ],
            "rules": [],
            "local_path_replacement_presets": [],
            "selected_local_path_replacement_preset": None,
            "svn_path_replacement_presets": [],
            "selected_svn_path_replacement_preset": None,
        },
        test_project_id,
    )

    response = await auth_client.post(
        "/api/v1/fixed-rules/import/workbench/preview",
        json={"scope": {"mode": "all"}, "source_mappings": []},
    )

    assert response.status_code == 200
    groups = response.json()["data"]["next_config_preview"]["groups"]
    assert any(group["group_name"] == "共享规则组-导入" for group in groups)
    group_result = response.json()["data"]["group_results"][0]
    assert group_result["status"] == "new"
    assert group_result["details"]["group_name"] == "共享规则组-导入"


async def test_workbench_import_rule_scope_only_imports_selected_dependencies(
    auth_client,
    test_project_id: int,
    tmp_path: Path,
) -> None:
    user_id = await _current_user_id()
    path_a = _create_workbook(tmp_path / "personal-a.xlsx")
    path_b = _create_workbook(tmp_path / "personal-b.xlsx")
    payload = {
        "sources": [_source("source-a", path_a), _source("source-b", path_b)],
        "variables": [_variable("source-a", "[items-A]"), _variable("source-b", "[items-B]")],
        "ruleGroups": [{"group_id": "ungrouped", "group_name": "未分组", "builtin": True}],
        "orchestrationRules": [
            _rule("[items-A]", "rule-a"),
            _rule("[items-B]", "rule-b"),
        ],
    }
    await _seed_workbench_config(test_project_id, user_id, payload)

    response = await auth_client.post(
        "/api/v1/fixed-rules/import/workbench/preview",
        json={"scope": {"mode": "rules", "rule_ids": ["rule-b"]}, "source_mappings": []},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert [rule["rule_id"] for rule in data["next_config_preview"]["rules"]] == ["rule-b"]
    assert [source["id"] for source in data["next_config_preview"]["sources"]] == ["source-b"]
    assert [variable["tag"] for variable in data["next_config_preview"]["variables"]] == ["[items-B]"]


async def test_workbench_import_draft_filters_selected_rule_dependencies(
    auth_client,
    test_project_id: int,
    tmp_path: Path,
) -> None:
    user_id = await _current_user_id()
    path_a = _create_workbook(tmp_path / "personal-a.xlsx")
    path_b = _create_workbook(tmp_path / "personal-b.xlsx")
    payload = {
        "sources": [_source("source-a", path_a), _source("source-b", path_b)],
        "variables": [_variable("source-a", "[items-A]"), _variable("source-b", "[items-B]")],
        "ruleGroups": [{"group_id": "ungrouped", "group_name": "未分组", "builtin": True}],
        "orchestrationRules": [
            _rule("[items-A]", "rule-a"),
            _rule("[items-B]", "rule-b"),
        ],
    }
    await _seed_workbench_config(test_project_id, user_id, payload)

    response = await auth_client.get(
        "/api/v1/fixed-rules/import/workbench/draft",
        params=[("selected_rule_ids", "rule-b")],
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert [rule["rule_id"] for rule in data["importable_rules"]] == ["rule-b"]
    assert [source["id"] for source in data["importable_sources"]] == ["source-b"]
    assert [variable["tag"] for variable in data["importable_variables"]] == ["[items-B]"]


async def test_workbench_import_draft_filters_selected_group_dependencies(
    auth_client,
    test_project_id: int,
    tmp_path: Path,
) -> None:
    user_id = await _current_user_id()
    path_a = _create_workbook(tmp_path / "personal-a.xlsx")
    path_b = _create_workbook(tmp_path / "personal-b.xlsx")
    payload = {
        "sources": [_source("source-a", path_a), _source("source-b", path_b)],
        "variables": [_variable("source-a", "[items-A]"), _variable("source-b", "[items-B]")],
        "ruleGroups": [
            {"group_id": "group-a", "group_name": "A 组", "builtin": False},
            {"group_id": "group-b", "group_name": "B 组", "builtin": False},
        ],
        "orchestrationRules": [
            {**_rule("[items-A]", "rule-a"), "group_id": "group-a"},
            {**_rule("[items-B]", "rule-b"), "group_id": "group-b"},
        ],
    }
    await _seed_workbench_config(test_project_id, user_id, payload)

    response = await auth_client.get(
        "/api/v1/fixed-rules/import/workbench/draft",
        params=[("selected_group_ids", "group-b")],
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert [group["group_id"] for group in data["importable_groups"]] == ["group-b"]
    assert [rule["rule_id"] for rule in data["importable_rules"]] == ["rule-b"]
    assert [source["id"] for source in data["importable_sources"]] == ["source-b"]


async def test_workbench_import_preview_accepts_top_level_selected_rule_ids(
    auth_client,
    test_project_id: int,
    tmp_path: Path,
) -> None:
    user_id = await _current_user_id()
    path_a = _create_workbook(tmp_path / "personal-a.xlsx")
    path_b = _create_workbook(tmp_path / "personal-b.xlsx")
    payload = {
        "sources": [_source("source-a", path_a), _source("source-b", path_b)],
        "variables": [_variable("source-a", "[items-A]"), _variable("source-b", "[items-B]")],
        "ruleGroups": [{"group_id": "ungrouped", "group_name": "未分组", "builtin": True}],
        "orchestrationRules": [
            _rule("[items-A]", "rule-a"),
            _rule("[items-B]", "rule-b"),
        ],
    }
    await _seed_workbench_config(test_project_id, user_id, payload)

    response = await auth_client.post(
        "/api/v1/fixed-rules/import/workbench/preview",
        json={
            "scope": {"mode": "all"},
            "selected_rule_ids": ["rule-b"],
            "source_mappings": [],
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert [rule["rule_id"] for rule in data["next_config_preview"]["rules"]] == ["rule-b"]
    assert [source["id"] for source in data["next_config_preview"]["sources"]] == ["source-b"]


async def test_workbench_import_rejects_foreign_user_or_project(
    auth_client,
    test_project_id: int,
    tmp_path: Path,
) -> None:
    user_id = await _current_user_id()
    workbook_path = _create_workbook(tmp_path / "personal.xlsx")
    await _seed_workbench_config(test_project_id, user_id, _workbench_payload(workbook_path))

    user_response = await auth_client.post(
        "/api/v1/fixed-rules/import/workbench/preview",
        json={
            "scope": {"mode": "all"},
            "source_mappings": [],
            "user_id": user_id + 1,
        },
    )
    project_response = await auth_client.get(
        "/api/v1/fixed-rules/import/workbench/draft",
        params={"project_id": test_project_id + 1},
    )

    assert user_response.status_code == 403
    assert project_response.status_code == 403


async def test_workbench_import_pipeline_and_mapping_rewrite_renamed_variable_tag(
    auth_client,
    test_project_id: int,
    tmp_path: Path,
) -> None:
    user_id = await _current_user_id()
    personal_path = _create_workbook(tmp_path / "personal.xlsx")
    project_path = _create_workbook(tmp_path / "project.xlsx")
    payload = {
        "sources": [_source("personal-source", personal_path)],
        "variables": [_composite_variable("personal-source")],
        "ruleGroups": [{"group_id": "ungrouped", "group_name": "未分组", "builtin": True}],
        "orchestrationRules": [
            {
                "rule_id": "pipeline-rule",
                "group_id": "ungrouped",
                "rule_name": "串行规则",
                "target_variable_tag": "[items-composite]",
                "rule_type": "multi_composite_pipeline_check",
                "pipeline_config": {
                    "nodes": [
                        {
                            "node_id": "node-1",
                            "variable_tag": "[items-composite]",
                            "filters": [],
                            "assertions": [
                                {
                                    "condition_id": "assert-1",
                                    "field": "Name",
                                    "operator": "not_null",
                                }
                            ],
                        }
                    ]
                },
            },
            {
                "rule_id": "mapping-rule",
                "group_id": "ungrouped",
                "rule_name": "映射规则",
                "target_variable_tag": "[items-composite]",
                "rule_type": "multi_composite_mapping_check",
                "mapping_config": {
                    "nodes": [
                        {
                            "node_id": "node-1",
                            "variable_tag": "[items-composite]",
                            "filters": [
                                {
                                    "condition_id": "filter-1",
                                    "field": "Name",
                                    "operator": "not_null",
                                    "exclusion_ranges": [],
                                }
                            ],
                        }
                    ]
                },
            },
        ],
    }
    await _seed_workbench_config(test_project_id, user_id, payload)
    await seed_fixed_rules_config(
        {
            "version": 6,
            "configured": True,
            "sources": [_source("project-source", project_path)],
            "variables": [_composite_variable("project-source")],
            "groups": [{"group_id": "ungrouped", "group_name": "未分组", "builtin": True}],
            "rules": [],
            "local_path_replacement_presets": [],
            "selected_local_path_replacement_preset": None,
            "svn_path_replacement_presets": [],
            "selected_svn_path_replacement_preset": None,
        },
        test_project_id,
    )

    response = await auth_client.post(
        "/api/v1/fixed-rules/import/workbench/preview",
        json={"scope": {"mode": "all"}, "source_mappings": []},
    )

    assert response.status_code == 200
    rules = response.json()["data"]["next_config_preview"]["rules"]
    pipeline_rule = next(rule for rule in rules if rule["rule_id"] == "pipeline-rule")
    mapping_rule = next(rule for rule in rules if rule["rule_id"] == "mapping-rule")
    assert pipeline_rule["target_variable_tag"] == "[items-composite-导入]"
    assert pipeline_rule["pipeline_config"]["nodes"][0]["variable_tag"] == "[items-composite-导入]"
    assert mapping_rule["target_variable_tag"] == "[items-composite-导入]"
    assert mapping_rule["mapping_config"]["nodes"][0]["variable_tag"] == "[items-composite-导入]"

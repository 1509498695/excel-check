"""AI 规则草稿稳定行为快照。

这些用例只锁定对外行为关键字段，避免后续模块拆分时被动态 ID 或解释文案干扰。
如确需更新快照，显式设置 ``UPDATE_AI_SNAPSHOTS=1`` 后单独运行本文件。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from backend.app.ai.providers import ProviderConnectionError
from backend.tests.test_ai_api import (
    BPCHERKS_COMMA_DUAL_DESCRIPTION,
    _get_test_user_id,
    _save_provider,
    _seed_bpcherks_composite_variable_config,
    _seed_test_composite_variable_config,
    _seed_workbench_config,
)


SNAPSHOT_DIR = Path(__file__).resolve().parent
STABLE_RESPONSE_KEYS = ("verdict", "rule_type", "draft", "missing", "rejection_reason")
DYNAMIC_ID_KEYS = {"rule_id", "condition_id", "branch_id", "comparison_id", "node_id"}


def _stable_snapshot(data: dict[str, Any]) -> dict[str, Any]:
    return {key: _scrub_dynamic_ids(data.get(key)) for key in STABLE_RESPONSE_KEYS}


def _scrub_dynamic_ids(value: Any) -> Any:
    if isinstance(value, list):
        return [_scrub_dynamic_ids(item) for item in value]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            result[key] = "<dynamic>" if key in DYNAMIC_ID_KEYS and item else _scrub_dynamic_ids(item)
        return result
    return value


def _assert_snapshot(name: str, data: dict[str, Any]) -> None:
    snapshot = _stable_snapshot(data)
    path = SNAPSHOT_DIR / f"{name}.json"
    serialized = json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if os.getenv("UPDATE_AI_SNAPSHOTS") == "1":
        path.write_text(serialized, encoding="utf-8")
        return
    assert path.exists(), f"missing snapshot: {path}"
    assert json.loads(path.read_text(encoding="utf-8")) == snapshot


@pytest.mark.anyio
async def test_snapshot_ready_composite_condition_check(
    auth_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    test_project_id: int,
    test_db,
) -> None:
    user_id = await _get_test_user_id()
    await _seed_test_composite_variable_config(test_project_id, user_id)
    await _save_provider(auth_client)

    async def fake_call_provider_json(**_: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        return {"verdict": "needs_input", "confidence": 0.1, "reasoning_summary": "fallback"}, {}

    monkeypatch.setattr("backend.app.ai.agent_service.call_provider_json", fake_call_provider_json)
    response = await auth_client.post(
        "/api/v1/ai/agents/rule-draft",
        json={
            "description": (
                "筛选DESC3=升级p1建筑到p2级p4次,完成p2等级的p1科研，两种类型。"
                "STR_ABSwitch字段=GreenServer:0 or SLG2:0。"
            ),
            "input_mode": "free_text",
            "allow_auto_complete": False,
            "selected_variable_tags": ["test"],
            "workflow_hints": {"target_variable_tag": "test"},
        },
    )
    assert response.status_code == 200, response.text
    _assert_snapshot("ready_composite_condition_check", response.json()["data"])


@pytest.mark.anyio
async def test_snapshot_ready_dual_composite_compare(
    auth_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    test_project_id: int,
    test_db,
) -> None:
    user_id = await _get_test_user_id()
    await _seed_bpcherks_composite_variable_config(test_project_id, user_id)
    await _save_provider(auth_client)

    async def fake_call_provider_json(**_: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        raise ProviderConnectionError(status_code=504, category="timeout", message="调用大模型超时，请稍后重试。")

    monkeypatch.setattr("backend.app.ai.agent_service.call_provider_json", fake_call_provider_json)
    response = await auth_client.post(
        "/api/v1/ai/agents/rule-draft",
        json={
            "description": BPCHERKS_COMMA_DUAL_DESCRIPTION,
            "input_mode": "free_text",
            "allow_auto_complete": False,
            "selected_variable_tags": ["bpcherks"],
        },
    )
    assert response.status_code == 200, response.text
    _assert_snapshot("ready_dual_composite_compare", response.json()["data"])


@pytest.mark.anyio
async def test_snapshot_ready_not_null_short_template(
    auth_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    test_project_id: int,
    test_db,
) -> None:
    user_id = await _get_test_user_id()
    await _seed_workbench_config(test_project_id, user_id)
    await _save_provider(auth_client)

    async def fake_call_provider_json(**_: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        raise AssertionError("完整固定模板不应先调用模型")

    monkeypatch.setattr("backend.app.ai.agent_service.call_provider_json", fake_call_provider_json)
    response = await auth_client.post(
        "/api/v1/ai/agents/rule-draft",
        json={
            "description": "\n".join(
                [
                    "数据源：src_demo",
                    "sheet分页：items",
                    "变量选择：ID",
                    "",
                    "筛选：",
                    "",
                    "Key值选择：无",
                    "",
                    "判定：ID 不能为空",
                ]
            ),
            "input_mode": "template",
            "allow_auto_complete": True,
            "workflow_hints": {
                "source_id": "src_demo",
                "sheet": "items",
                "target_field": "ID",
                "rule_type_hint": "not_null",
            },
        },
    )
    assert response.status_code == 200, response.text
    _assert_snapshot("ready_not_null_short_template", response.json()["data"])


@pytest.mark.anyio
async def test_snapshot_ready_fixed_value_set(
    auth_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    test_project_id: int,
    test_db,
) -> None:
    user_id = await _get_test_user_id()
    await _seed_workbench_config(test_project_id, user_id)
    await _save_provider(auth_client)

    async def fake_call_provider_json(**_: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        return {
            "verdict": "ready",
            "rule_type": "fixed_value_compare",
            "confidence": 0.9,
            "reasoning_summary": "ID 字段只能是规则集 0,1。",
            "target": {"tag": "[src_demo-items-ID]"},
            "operator": "eq",
            "expected_value": "0,1",
            "expected_value_mode": "set",
        }, {}

    monkeypatch.setattr("backend.app.ai.agent_service.call_provider_json", fake_call_provider_json)
    response = await auth_client.post(
        "/api/v1/ai/agents/rule-draft",
        json={
            "description": "ID 只能是 0,1",
            "input_mode": "free_text",
            "allow_auto_complete": False,
            "selected_variable_tags": ["[src_demo-items-ID]"],
        },
    )
    assert response.status_code == 200, response.text
    _assert_snapshot("ready_fixed_value_set", response.json()["data"])


@pytest.mark.anyio
async def test_snapshot_needs_input_missing_assertion(
    auth_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    test_project_id: int,
    test_db,
) -> None:
    await _save_provider(auth_client)

    async def fake_call_provider_json(**_: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        return {
            "verdict": "needs_input",
            "confidence": 0.4,
            "reasoning_summary": "缺少规则口径。",
            "missing": [{"kind": "rule", "message": "缺少可用规则类型。"}],
        }, {}

    monkeypatch.setattr("backend.app.ai.agent_service.call_provider_json", fake_call_provider_json)
    response = await auth_client.post(
        "/api/v1/ai/agents/rule-draft",
        json={
            "description": "检查 switch 表 STR_ServersParam。",
            "workflow_hints": {
                "source_id": "server_config",
                "source_url": "https://samosvn/data/project/samo/GameDatas/datas_qa88/server_config.xls",
                "sheet": "switch",
                "target_field": "STR_ServersParam",
            },
        },
    )
    assert response.status_code == 200, response.text
    _assert_snapshot("needs_input_missing_assertion", response.json()["data"])


@pytest.mark.anyio
async def test_snapshot_rejected_aggregation(
    auth_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    test_project_id: int,
    test_db,
) -> None:
    await _save_provider(auth_client)

    async def fake_call_provider_json(**_: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        raise AssertionError("聚合类需求应在候选批判阶段直接拒绝")

    monkeypatch.setattr("backend.app.ai.agent_service.call_provider_json", fake_call_provider_json)
    response = await auth_client.post(
        "/api/v1/ai/agents/rule-draft",
        json={"description": "按服务器聚合分组后计算平均战力。"},
    )
    assert response.status_code == 200, response.text
    _assert_snapshot("rejected_aggregation", response.json()["data"])

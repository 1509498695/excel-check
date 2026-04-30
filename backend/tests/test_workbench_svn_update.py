"""个人校验 SVN 更新接口测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient

from backend.app.fixed_rules import service as fixed_rules_service


@pytest.mark.anyio
async def test_workbench_svn_update_uses_current_user_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    auth_client: AsyncClient,
) -> None:
    """个人校验 SVN 更新只读取当前用户保存的工作台数据源。"""
    workbook_path = tmp_path / "working-copy" / "items.xlsx"
    workbook_path.parent.mkdir()
    workbook_path.write_text("placeholder", encoding="utf-8")
    called_working_copies: list[str] = []

    def fake_update(working_copy: Path) -> dict[str, str]:
        called_working_copies.append(str(working_copy))
        return {
            "output": f"updated:{working_copy.name}",
            "used_executable": "svn.exe",
        }

    monkeypatch.setattr(fixed_rules_service, "update_svn_working_copy", fake_update)

    await auth_client.put(
        "/api/v1/workbench/config",
        json={
            "sources": [
                {
                    "id": "source-a",
                    "type": "local_excel",
                    "path": str(workbook_path),
                    "pathOrUrl": str(workbook_path),
                }
            ],
            "variables": [],
            "ruleGroups": [],
            "orchestrationRules": [],
        },
    )

    response = await auth_client.post("/api/v1/workbench/svn-update")

    assert response.status_code == 200
    response_payload = response.json()["data"]
    assert response_payload["total_paths"] == 1
    assert response_payload["updated_paths"] == 1
    assert called_working_copies == [str(workbook_path.parent)]


@pytest.mark.anyio
async def test_workbench_svn_update_requires_saved_config(
    auth_client: AsyncClient,
) -> None:
    """没有个人校验持久化配置时，接口返回明确错误。"""
    response = await auth_client.post("/api/v1/workbench/svn-update")

    assert response.status_code == 400
    assert "个人校验" in response.json()["detail"]

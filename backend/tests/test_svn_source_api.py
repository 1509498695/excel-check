"""SVN 数据源相关 HTTP 接口测试。

涵盖：
- /sources/svn-list 正向 / host 拒 / 401 鉴权失败 / 404 未找到 / 自动补斜杠
- /sources/svn-credentials 的 POST/GET/DELETE
- /sources/svn-refresh 强制刷新
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from backend.app.api import source_api
from backend.app.loaders import svn_cache, svn_credentials, svn_manager


@pytest.fixture
def temp_svn_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """凭据存储与缓存目录都重定向到 tmp_path。"""
    new_settings = dataclasses.replace(
        svn_cache.settings,
        svn_cache_dir=tmp_path / "svn-cache",
        svn_credentials_path=tmp_path / "svn-credentials.json",
        svn_credentials_key_path=tmp_path / ".svn-key",
        svn_cache_ttl_seconds=60,
        svn_url_allowlist=("samosvn",),
    )
    monkeypatch.setattr(svn_cache, "settings", new_settings)
    monkeypatch.setattr(svn_credentials, "settings", new_settings)
    monkeypatch.setattr(svn_manager, "settings", new_settings)
    return tmp_path


@pytest.mark.anyio
async def test_svn_list_returns_normalized_dir_url_and_entries(
    auth_client: AsyncClient,
    temp_svn_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """正向：返回 dir_url（自动补斜杠）+ entries + host。"""
    captured: dict[str, Any] = {}

    def _fake_list(dir_url: str, *, credentials, timeout=None):
        captured["dir_url"] = dir_url
        captured["has_credentials"] = credentials is not None
        return {
            "dir_url": dir_url,
            "entries": [
                {
                    "kind": "file",
                    "name": "quests.xls",
                    "size": 4521984,
                    "revision": 11823,
                    "last_author": "liming",
                    "last_modified_at": "2026-04-18T03:11:09Z",
                }
            ],
        }

    monkeypatch.setattr(source_api, "list_svn_directory", _fake_list)

    response = await auth_client.post(
        "/api/v1/sources/svn-list",
        json={"dir_url": "https://samosvn/data/project/samo/GameDatas/datas_qa88"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["dir_url"].endswith("/datas_qa88/")
    assert payload["data"]["host"] == "samosvn"
    assert payload["data"]["entries"][0]["name"] == "quests.xls"
    # 没保存过凭据 → list 调用时 credentials=None
    assert captured["has_credentials"] is False
    assert captured["dir_url"].endswith("/datas_qa88/")


@pytest.mark.anyio
async def test_svn_list_rejects_host_outside_allowlist(
    auth_client: AsyncClient,
    temp_svn_runtime: Path,
) -> None:
    """非白名单 host → 400 + 中文提示，不触达 svn 命令。"""
    response = await auth_client.post(
        "/api/v1/sources/svn-list",
        json={"dir_url": "https://evil.example.com/data/"},
    )
    assert response.status_code == 400
    assert "不在允许列表" in response.json()["detail"]


@pytest.mark.anyio
async def test_svn_list_translates_auth_failed_to_403(
    auth_client: AsyncClient,
    temp_svn_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """svn list 抛 auth_failed → 接口返回 403（业务级拒绝，避免前端跳登录）。"""

    def _failing(*_args, **_kwargs):
        raise svn_manager.SvnRemoteError("auth_failed", "鉴权失败")

    monkeypatch.setattr(source_api, "list_svn_directory", _failing)

    response = await auth_client.post(
        "/api/v1/sources/svn-list",
        json={"dir_url": "https://samosvn/data/project/samo/GameDatas/datas_qa88/"},
    )
    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["category"] == "auth_failed"


@pytest.mark.anyio
async def test_svn_list_requires_authentication(temp_svn_runtime: Path) -> None:
    """未携带 Bearer Token → 401。"""
    from httpx import ASGITransport, AsyncClient as PlainClient

    from backend.run import app

    async with PlainClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/sources/svn-list",
            json={"dir_url": "https://samosvn/data/"},
        )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_svn_credentials_crud_round_trip(
    auth_client: AsyncClient,
    temp_svn_runtime: Path,
) -> None:
    """POST → GET → DELETE 三连。"""
    # 初始为空
    initial = await auth_client.get("/api/v1/sources/svn-credentials")
    assert initial.status_code == 200
    assert initial.json()["data"]["items"] == []

    # 保存
    saved = await auth_client.post(
        "/api/v1/sources/svn-credentials",
        json={
            "host": "samosvn",
            "username": "alice",
            "password": "secret",
            "test_dir_url": "https://samosvn/data/project/samo/GameDatas",
        },
    )
    assert saved.status_code == 200
    assert saved.json()["data"]["host"] == "samosvn"
    assert saved.json()["data"]["test_dir_url"] == "https://samosvn/data/project/samo/GameDatas/"

    # 列出
    listed = await auth_client.get("/api/v1/sources/svn-credentials")
    items = listed.json()["data"]["items"]
    assert len(items) == 1 and items[0]["host"] == "samosvn"
    assert items[0]["username"] == "alice"
    assert items[0]["test_dir_url"] == "https://samosvn/data/project/samo/GameDatas/"
    assert "password" not in items[0]

    # 删除
    deleted = await auth_client.delete("/api/v1/sources/svn-credentials/samosvn")
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted"] is True

    after = await auth_client.get("/api/v1/sources/svn-credentials")
    assert after.json()["data"]["items"] == []


@pytest.mark.anyio
async def test_svn_credentials_reject_test_dir_url_with_mismatched_host(
    auth_client: AsyncClient,
    temp_svn_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试目录 URL 若与 host 不匹配，应直接 400。"""
    expanded_settings = dataclasses.replace(
        source_api.settings,
        svn_url_allowlist=("samosvn", "otherhost"),
    )
    monkeypatch.setattr(source_api, "settings", expanded_settings)
    monkeypatch.setattr(svn_manager, "settings", expanded_settings)

    response = await auth_client.post(
        "/api/v1/sources/svn-credentials",
        json={
            "host": "samosvn",
            "username": "alice",
            "password": "secret",
            "test_dir_url": "https://otherhost/data/project/samo/GameDatas/",
        },
    )
    assert response.status_code == 400
    assert "host 不匹配" in response.json()["detail"]


@pytest.mark.anyio
async def test_svn_refresh_force_updates_cache(
    auth_client: AsyncClient,
    temp_svn_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """svn-refresh 强制刷新缓存并返回 cached_path。"""
    captured = {"force": []}

    def _fake_prepare(source, *, user_scope=None, force_refresh=False):
        captured["force"].append(force_refresh)
        cached_dir = temp_svn_runtime / "svn-cache" / "samosvn" / "abc"
        cached_dir.mkdir(parents=True, exist_ok=True)
        (cached_dir / ".meta.json").write_text(
            '{"dir_url":"https://samosvn/data/project/samo/GameDatas/datas_qa88/","last_updated_at":"2026-04-21T00:00:00+00:00","revision":11900}',
            encoding="utf-8",
        )
        cached_file = cached_dir / "quests.xls"
        cached_file.write_bytes(b"data")
        return cached_file

    def _fake_state(_url):
        return {
            "host": "samosvn",
            "cache_dir": "ignored",
            "file_name": "quests.xls",
            "cached_path": str(temp_svn_runtime / "svn-cache" / "samosvn" / "abc" / "quests.xls"),
            "revision": 11900,
            "last_updated_at": "2026-04-21T00:00:00+00:00",
        }

    monkeypatch.setattr(source_api, "prepare_remote_svn_source", _fake_prepare)
    monkeypatch.setattr(source_api, "get_remote_cache_state", _fake_state)

    response = await auth_client.post(
        "/api/v1/sources/svn-refresh",
        json={
            "source": {
                "id": "src_remote",
                "type": "svn",
                "pathOrUrl": "https://samosvn/data/project/samo/GameDatas/datas_qa88/quests.xls",
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["host"] == "samosvn"
    assert payload["data"]["revision"] == 11900
    assert payload["data"]["cached_path"].endswith("quests.xls")
    assert captured["force"] == [True]

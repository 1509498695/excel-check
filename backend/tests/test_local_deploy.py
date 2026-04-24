"""本机共享部署相关接口与静态托管回归。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.api import source_api
from backend.run import app as main_app
from backend.run import configure_static_frontend


TEST_DATA_PATH = Path(__file__).resolve().parent / "data" / "minimal_rules.xlsx"


def _patch_upload_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, max_bytes: int) -> None:
    monkeypatch.setattr(
        source_api,
        "settings",
        SimpleNamespace(
            runtime_upload_dir=tmp_path,
            max_upload_bytes=max_bytes,
            max_upload_mb=max(1, max_bytes // 1024 // 1024),
            supported_source_types=("local_excel", "local_csv", "feishu", "svn"),
        ),
    )


@pytest.mark.anyio
async def test_upload_source_file_returns_reusable_server_path(
    auth_client: AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """上传 Excel 后应返回可继续用于 metadata 的服务器路径。"""
    _patch_upload_settings(monkeypatch, tmp_path, max_bytes=10 * 1024 * 1024)

    with TEST_DATA_PATH.open("rb") as file_handle:
        response = await auth_client.post(
            "/api/v1/sources/upload",
            files={
                "file": (
                    "minimal_rules.xlsx",
                    file_handle,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )

    assert response.status_code == 200
    payload = response.json()
    selected_path = Path(payload["data"]["selected_path"])
    assert payload["data"]["source_type"] == "local_excel"
    assert payload["data"]["original_filename"] == "minimal_rules.xlsx"
    assert selected_path.is_file()
    assert tmp_path in selected_path.parents

    metadata_response = await auth_client.post(
        "/api/v1/sources/metadata",
        json={
            "id": "uploaded_rules",
            "type": "local_excel",
            "pathOrUrl": str(selected_path),
        },
    )
    assert metadata_response.status_code == 200
    assert metadata_response.json()["data"]["sheets"][0]["name"] == "items"


@pytest.mark.anyio
async def test_upload_source_file_requires_login(tmp_path: Path) -> None:
    """上传接口必须带登录态。"""
    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/sources/upload",
            files={"file": ("sample.csv", b"id\n1\n", "text/csv")},
        )

    assert response.status_code == 401


@pytest.mark.anyio
async def test_upload_source_file_rejects_unsupported_suffix(
    auth_client: AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """仅允许上传 Excel/CSV。"""
    _patch_upload_settings(monkeypatch, tmp_path, max_bytes=1024)

    response = await auth_client.post(
        "/api/v1/sources/upload",
        files={"file": ("sample.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 400
    assert "仅支持上传" in response.json()["detail"]


@pytest.mark.anyio
async def test_upload_source_file_rejects_oversized_file(
    auth_client: AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """超过 MAX_UPLOAD_MB 对应字节数时拒绝并清理临时文件。"""
    _patch_upload_settings(monkeypatch, tmp_path, max_bytes=4)

    response = await auth_client.post(
        "/api/v1/sources/upload",
        files={"file": ("sample.csv", b"id\n123\n", "text/csv")},
    )

    assert response.status_code == 413
    assert not list(tmp_path.rglob("*.csv"))


@pytest.mark.anyio
async def test_static_frontend_serves_spa_routes_and_keeps_api_404(
    tmp_path: Path,
) -> None:
    """生产包托管应支持前端路由回退，同时不吞掉 API 404。"""
    dist_dir = tmp_path / "dist"
    assets_dir = dist_dir / "assets"
    assets_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text("<html><body>Excel Check</body></html>", encoding="utf-8")
    (assets_dir / "app.js").write_text("console.log('ok')", encoding="utf-8")

    app = FastAPI()
    assert configure_static_frontend(app, frontend_dist_dir=dist_dir) is True

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        root_response = await client.get("/")
        nested_route_response = await client.get("/fixed-rules")
        asset_response = await client.get("/assets/app.js")
        api_response = await client.get("/api/v1/not-found")

    assert root_response.status_code == 200
    assert "Excel Check" in root_response.text
    assert nested_route_response.status_code == 200
    assert "Excel Check" in nested_route_response.text
    assert asset_response.status_code == 200
    assert "console.log" in asset_response.text
    assert api_response.status_code == 404

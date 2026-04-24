"""SVN 远端 URL → 本地缓存模块测试。"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from backend.app.api.schemas import DataSource
from backend.app.loaders import svn_cache, svn_credentials, svn_manager


@pytest.fixture
def temp_svn_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """把 svn_cache_dir / 凭据文件重定向到 tmp_path。"""
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


def _make_svn_source(file_url: str) -> DataSource:
    return DataSource(
        id="src_remote",
        type="svn",
        pathOrUrl=file_url,
    )


def _stub_checkout_creates_file(file_name: str = "quests.xls"):
    """模拟 svn checkout：在 cache_dir 里创建 .svn 与目标文件。"""

    def _checkout(*, dir_url, target_dir: Path, credentials, depth="files", timeout=None):
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / ".svn").mkdir(exist_ok=True)
        (target_dir / file_name).write_bytes(b"fake-excel-bytes")
        return {"output": "Checked out revision 11823."}

    return _checkout


def test_prepare_remote_svn_source_first_run_triggers_checkout(
    temp_svn_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """首跑：cache_dir 不存在 → checkout，并落 .meta.json。"""
    calls = {"checkout": 0, "update": 0}

    def _checkout(*args, **kwargs):
        calls["checkout"] += 1
        return _stub_checkout_creates_file()(*args, **kwargs)

    def _update(*args, **kwargs):
        calls["update"] += 1
        return {"output": "Updated."}

    monkeypatch.setattr(svn_cache, "checkout_remote_directory", _checkout)
    monkeypatch.setattr(svn_cache, "update_remote_cache_directory", _update)
    monkeypatch.setattr(svn_cache, "get_remote_revision", lambda *_a, **_k: 11823)

    source = _make_svn_source(
        "https://samosvn/data/project/samo/GameDatas/datas_qa88/quests.xls"
    )
    cached = svn_cache.prepare_remote_svn_source(source, user_scope="alice")

    assert cached.exists()
    assert cached.name == "quests.xls"
    assert calls["checkout"] == 1
    assert calls["update"] == 0
    meta_file = cached.parent / ".meta.json"
    assert meta_file.exists()


def test_prepare_remote_svn_source_skips_when_within_ttl(
    temp_svn_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """命中 TTL 内：第二次调用既不 checkout 也不 update。"""
    monkeypatch.setattr(svn_cache, "checkout_remote_directory", _stub_checkout_creates_file())
    monkeypatch.setattr(svn_cache, "update_remote_cache_directory", lambda **_k: {"output": ""})
    monkeypatch.setattr(svn_cache, "get_remote_revision", lambda *_a, **_k: 11823)

    source = _make_svn_source(
        "https://samosvn/data/project/samo/GameDatas/datas_qa88/quests.xls"
    )
    svn_cache.prepare_remote_svn_source(source, user_scope="alice")

    calls = {"checkout": 0, "update": 0}

    def _track_checkout(**kwargs):
        calls["checkout"] += 1
        return {"output": ""}

    def _track_update(**kwargs):
        calls["update"] += 1
        return {"output": ""}

    monkeypatch.setattr(svn_cache, "checkout_remote_directory", _track_checkout)
    monkeypatch.setattr(svn_cache, "update_remote_cache_directory", _track_update)

    cached = svn_cache.prepare_remote_svn_source(source, user_scope="alice")
    assert cached.exists()
    assert calls == {"checkout": 0, "update": 0}


def test_prepare_remote_svn_source_force_refresh_triggers_update(
    temp_svn_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """force_refresh=True 时即使在 TTL 内也走 update。"""
    monkeypatch.setattr(svn_cache, "checkout_remote_directory", _stub_checkout_creates_file())
    monkeypatch.setattr(svn_cache, "get_remote_revision", lambda *_a, **_k: 11900)

    source = _make_svn_source(
        "https://samosvn/data/project/samo/GameDatas/datas_qa88/quests.xls"
    )
    svn_cache.prepare_remote_svn_source(source, user_scope="alice")

    calls = {"update": 0}

    def _track_update(**kwargs):
        calls["update"] += 1
        return {"output": ""}

    monkeypatch.setattr(svn_cache, "update_remote_cache_directory", _track_update)
    svn_cache.prepare_remote_svn_source(source, user_scope="alice", force_refresh=True)
    assert calls["update"] == 1


def test_prepare_remote_svn_source_passes_through_local_path(
    temp_svn_runtime: Path,
    tmp_path: Path,
) -> None:
    """svn 源 pathOrUrl 是本地路径时直接透传，不触达远端调用。"""
    local_file = tmp_path / "fake-local-svn-checkout" / "quests.xls"
    local_file.parent.mkdir(parents=True, exist_ok=True)
    local_file.write_bytes(b"data")

    source = DataSource(id="src_local_svn", type="svn", pathOrUrl=str(local_file))
    resolved = svn_cache.prepare_remote_svn_source(source, user_scope="alice")
    assert resolved == local_file


def test_prepare_remote_svn_source_rejects_url_pointing_to_directory(
    temp_svn_runtime: Path,
) -> None:
    """URL 必须指向文件，不允许目录。"""
    source = _make_svn_source(
        "https://samosvn/data/project/samo/GameDatas/datas_qa88/"
    )
    with pytest.raises(ValueError, match="必须指向具体文件"):
        svn_cache.prepare_remote_svn_source(source, user_scope="alice")


def test_prepare_remote_svn_source_translates_remote_error(
    temp_svn_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """checkout 抛 SvnRemoteError 时，最外层翻译为 ValueError 携带 category。"""

    def _failing_checkout(**_kwargs):
        raise svn_manager.SvnRemoteError("auth_failed", "鉴权失败")

    monkeypatch.setattr(svn_cache, "checkout_remote_directory", _failing_checkout)

    source = _make_svn_source(
        "https://samosvn/data/project/samo/GameDatas/datas_qa88/quests.xls"
    )
    with pytest.raises(ValueError, match="auth_failed"):
        svn_cache.prepare_remote_svn_source(source, user_scope="alice")


def test_get_remote_cache_state_returns_meta_after_prepare(
    temp_svn_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """prepare 之后，get_remote_cache_state 能读出 cached_path 与 revision。"""
    monkeypatch.setattr(svn_cache, "checkout_remote_directory", _stub_checkout_creates_file())
    monkeypatch.setattr(svn_cache, "update_remote_cache_directory", lambda **_k: {"output": ""})
    monkeypatch.setattr(svn_cache, "get_remote_revision", lambda *_a, **_k: 11823)

    source = _make_svn_source(
        "https://samosvn/data/project/samo/GameDatas/datas_qa88/quests.xls"
    )
    svn_cache.prepare_remote_svn_source(source, user_scope="alice")

    state = svn_cache.get_remote_cache_state(source.pathOrUrl)
    assert state["host"] == "samosvn"
    assert state["file_name"] == "quests.xls"
    assert state["cached_path"].endswith("quests.xls")
    assert state["revision"] == 11823
    assert state["last_updated_at"]

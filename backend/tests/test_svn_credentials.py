"""SVN 凭据存储模块单元测试。"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from backend.app.loaders import svn_credentials


@pytest.fixture
def temp_credential_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """把凭据文件 / 密钥重定向到 tmp_path，避免污染真实 runtime 目录。"""
    new_settings = dataclasses.replace(
        svn_credentials.settings,
        svn_credentials_path=tmp_path / "svn-credentials.json",
        svn_credentials_key_path=tmp_path / ".svn-key",
    )
    monkeypatch.setattr(svn_credentials, "settings", new_settings)
    return tmp_path


def test_save_load_list_delete_round_trip(temp_credential_paths: Path) -> None:
    """save → load → list → delete 基本流程。"""
    saved = svn_credentials.save_credentials(
        host="samosvn",
        username="alice",
        password="P@ssw0rd!",
        user_scope="alice",
        test_dir_url="https://samosvn/data/project/samo/GameDatas/",
    )
    assert saved.username == "alice"
    assert saved.host == "samosvn"
    assert saved.test_dir_url == "https://samosvn/data/project/samo/GameDatas/"

    loaded = svn_credentials.load_credentials(host="samosvn", user_scope="alice")
    assert loaded is not None
    assert loaded.username == "alice"
    assert loaded.password == "P@ssw0rd!"
    assert loaded.test_dir_url == "https://samosvn/data/project/samo/GameDatas/"

    listed = svn_credentials.list_hosts(user_scope="alice")
    assert len(listed) == 1
    assert listed[0]["host"] == "samosvn"
    assert listed[0]["username"] == "alice"
    assert listed[0]["test_dir_url"] == "https://samosvn/data/project/samo/GameDatas/"
    assert "password" not in listed[0]

    assert svn_credentials.delete_credentials(host="samosvn", user_scope="alice") is True
    assert svn_credentials.load_credentials(host="samosvn", user_scope="alice") is None
    assert svn_credentials.list_hosts(user_scope="alice") == []


def test_credentials_isolated_between_user_scopes(temp_credential_paths: Path) -> None:
    """不同登录用户保存的凭据互不干扰。"""
    svn_credentials.save_credentials(
        host="samosvn", username="alice", password="alicepwd", user_scope="alice"
    )
    svn_credentials.save_credentials(
        host="samosvn", username="bob", password="bobpwd", user_scope="bob"
    )

    alice_loaded = svn_credentials.load_credentials(host="samosvn", user_scope="alice")
    bob_loaded = svn_credentials.load_credentials(host="samosvn", user_scope="bob")

    assert alice_loaded is not None and alice_loaded.password == "alicepwd"
    assert bob_loaded is not None and bob_loaded.password == "bobpwd"

    # 删除 alice 的不应影响 bob
    assert svn_credentials.delete_credentials(host="samosvn", user_scope="alice") is True
    assert svn_credentials.load_credentials(host="samosvn", user_scope="alice") is None
    bob_after = svn_credentials.load_credentials(host="samosvn", user_scope="bob")
    assert bob_after is not None and bob_after.password == "bobpwd"


def test_host_case_normalized(temp_credential_paths: Path) -> None:
    """SAMOSVN / samosvn 视为同一份凭据。"""
    svn_credentials.save_credentials(
        host="SAMOSVN", username="u", password="p", user_scope="alice"
    )
    loaded = svn_credentials.load_credentials(host="samosvn", user_scope="alice")
    assert loaded is not None and loaded.username == "u"
    assert svn_credentials.delete_credentials(host="SAmOSvn", user_scope="alice") is True


def test_load_credentials_tolerates_legacy_store_without_test_dir_url(
    temp_credential_paths: Path,
) -> None:
    """旧格式凭据文件没有 test_dir_url 字段时，仍应正常读取。"""
    saved = svn_credentials.save_credentials(
        host="samosvn",
        username="legacy",
        password="legacypwd",
        user_scope="alice",
        test_dir_url="https://samosvn/data/project/samo/GameDatas/",
    )
    assert saved.test_dir_url is not None

    store_path = svn_credentials.settings.svn_credentials_path
    payload = json.loads(store_path.read_text(encoding="utf-8"))
    payload["alice"]["samosvn"].pop("test_dir_url", None)
    store_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    loaded = svn_credentials.load_credentials(host="samosvn", user_scope="alice")
    assert loaded is not None
    assert loaded.username == "legacy"
    assert loaded.password == "legacypwd"
    assert loaded.test_dir_url is None

"""Focused extractor regression tests for AI smart-rule hints."""

from __future__ import annotations

from backend.app.ai.extractors.source import derive_source_id, extract_source_url, guess_source_type
from backend.app.ai.extractors.value import extract_fixed_value_compare, extract_sequence
from backend.app.ai.hint_extractor import extract_workflow_hints_from_text


def test_source_extractors_keep_existing_url_id_and_type_semantics() -> None:
    url = extract_source_url("配置表：https://example.com/path/server_config.xlsx，sheet=switch")

    assert url == "https://example.com/path/server_config.xlsx"
    assert derive_source_id(url) == "server_config"
    assert guess_source_type(url) == "svn"


def test_value_extractors_keep_fixed_value_and_sequence_semantics() -> None:
    assert extract_fixed_value_compare("Status 只能是 0,1") == ("eq", "0,1", "set")
    assert extract_sequence("ID 按升序连续，步长 2，从 10 开始") == ("asc", "2", "manual", "10")


def test_main_hint_extractor_still_uses_split_extractors() -> None:
    hints = extract_workflow_hints_from_text(
        "数据源：https://example.com/path/items.xlsx sheet分页：items 变量选择：ID 判定：ID 只能是 0,1"
    )

    assert hints.source_url == "https://example.com/path/items.xlsx"
    assert hints.source_id == "items"
    assert hints.rule_type_hint == "fixed_value_compare"
    assert hints.expected_value == "0,1"

"""AI field resolver regression tests."""

from __future__ import annotations

from backend.app.ai.field_resolver import (
    canonicalize_with_metadata,
    canonicalize_with_variable,
    is_placeholder_key_column,
    resolve_identifier_exact_or_trim,
    unique_fuzzy_field_match,
)
from backend.app.ai.schemas import AiRuleFilterHint, AiRuleWorkflowHints
from backend.app.api.schemas import VariableTag


def test_resolve_identifier_exact_trim_and_ambiguous() -> None:
    assert resolve_identifier_exact_or_trim("INT_ID", ["INT_ID"]) == ("INT_ID", None)
    assert resolve_identifier_exact_or_trim("INT_ID", ["INT_ID ", " INT_ID"]) == (None, "ambiguous")
    assert resolve_identifier_exact_or_trim("INT_ID", ["INT_ID "]) == ("INT_ID ", None)


def test_unique_fuzzy_field_match_is_conservative() -> None:
    assert unique_fuzzy_field_match("INT_FreeRewardSubType1", ["INT_PayRewardSubType1"]) == "INT_PayRewardSubType1"
    assert unique_fuzzy_field_match("INT_Level", ["STR_Name", "DESC"]) is None


def test_placeholder_key_detection() -> None:
    assert is_placeholder_key_column("Key")
    assert is_placeholder_key_column("需要用户确认 Key 字段")
    assert not is_placeholder_key_column("INT_ID")


def test_canonicalize_with_variable_updates_scalar_list_and_filters() -> None:
    variable = VariableTag(
        tag="bpcherks",
        source_id="battlepass",
        sheet="level_reward",
        variable_kind="composite",
        key_column="INT_Level",
        columns=["INT_Index", "INT_PayRewardValue1"],
    )
    hints = AiRuleWorkflowHints(
        target_field="INT_PayRewardValu1",
        key_column="Key",
        compare_fields=["INT_PayRewardValu1"],
        filters=[AiRuleFilterHint(field="INT_Index", value="1012")],
    )

    next_hints, warnings, unresolved = canonicalize_with_variable(hints, variable)

    assert next_hints.target_field == "INT_PayRewardValue1"
    assert next_hints.key_column is None
    assert next_hints.compare_fields == ["INT_PayRewardValue1"]
    assert next_hints.filters[0].field == "INT_Index"
    assert warnings
    assert unresolved == []


def test_canonicalize_with_metadata_updates_against_sheet_columns() -> None:
    context = {
        "source_metadata": {
            "battlepass": {
                "sheets": [
                    {
                        "name": "level_reward",
                        "columns": ["INT_Level", "INT_Index", "INT_PayRewardSubType1"],
                    }
                ]
            }
        }
    }
    hints = AiRuleWorkflowHints(
        source_id="battlepass",
        sheet="level_reward",
        target_field="INT_FreeRewardSubType1",
    )

    next_hints, warnings, unresolved = canonicalize_with_metadata(
        hints,
        context,
        source_id="battlepass",
        sheet="level_reward",
    )

    assert next_hints.target_field == "INT_PayRewardSubType1"
    assert warnings
    assert unresolved == []

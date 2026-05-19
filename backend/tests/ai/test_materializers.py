"""RuleIntent materializer regression tests."""

from __future__ import annotations

from backend.app.ai.materializers import materialize_rule_definition
from backend.app.ai.schemas import RuleIntent
from backend.app.api.schemas import VariableTag


def _single_variable() -> VariableTag:
    return VariableTag(
        tag="[items-id]",
        source_id="src_demo",
        sheet="items",
        variable_kind="single",
        column="ID",
        expected_type="str",
    )


def test_materializes_fixed_value_compare_rule() -> None:
    rule, missing = materialize_rule_definition(
        RuleIntent(
            verdict="ready",
            rule_type="fixed_value_compare",
            operator="eq",
            expected_value="0,1",
            expected_value_mode="set",
        ),
        target_variable=_single_variable(),
        reference_variable=None,
        description="ID 只能是 0,1",
    )

    assert missing == []
    assert rule is not None
    assert rule.rule_type == "fixed_value_compare"
    assert rule.target_variable_tag == "[items-id]"
    assert rule.expected_value == "0,1"
    assert rule.expected_value_mode == "set"


def test_materializer_requires_regex_pattern() -> None:
    rule, missing = materialize_rule_definition(
        RuleIntent(verdict="ready", rule_type="regex_check"),
        target_variable=_single_variable(),
        reference_variable=None,
        description="ID 格式校验",
    )

    assert rule is None
    assert missing and missing[0].kind == "parameter"

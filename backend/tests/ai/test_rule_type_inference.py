"""Rule type inference tests for AI workflow hints."""

from __future__ import annotations

from backend.app.ai.rule_type_inference import infer_hint_rule_type
from backend.app.ai.schemas import RuleIntent
from backend.app.ai.workflow_hints import AiRuleFilterHint, AiRuleWorkflowHints


def _intent(rule_type: str | None = None) -> RuleIntent:
    return RuleIntent(verdict="needs_input", rule_type=rule_type)


def test_infers_composite_condition_from_filter_assertion_pair() -> None:
    hints = AiRuleWorkflowHints(
        filters=[AiRuleFilterHint(field="Type", operator="eq", value="A")],
        assertion_field="Status",
        assertion_operator="duplicate_required",
    )

    assert infer_hint_rule_type(_intent(), hints, "") == "composite_condition_check"


def test_infers_dual_compare_from_complete_dual_hints() -> None:
    hints = AiRuleWorkflowHints(
        left_filter_field="Type",
        left_filter_value="A",
        right_filter_field="Type",
        right_filter_value="B",
        compare_fields=["Value"],
    )

    assert infer_hint_rule_type(_intent(), hints, "") == "dual_composite_compare"


def test_composite_signals_upgrade_regex_to_composite_condition() -> None:
    hints = AiRuleWorkflowHints(
        rule_type_hint="regex_check",
        filter_field="Type",
        filter_value="A",
        regex_pattern=r"^\d+$",
    )

    assert infer_hint_rule_type(_intent(), hints, "") == "composite_condition_check"

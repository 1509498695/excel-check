"""Golden contract tests for fixed-rule to engine-rule parameter mapping."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app.api.fixed_rules_schemas import FixedRulesConfig
from backend.app.fixed_rules.service import (
    build_fixed_rules_task_tree,
    validate_and_normalize_fixed_rules_config,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_PATH = REPO_ROOT / "contracts" / "rule_params_golden.json"


def _load_golden() -> dict[str, Any]:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def _stable_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize JSON-compatible dictionaries and sort by rule id."""
    return sorted(
        json.loads(json.dumps(rules, ensure_ascii=False)),
        key=lambda item: item["rule_id"],
    )


def test_fixed_rules_task_tree_params_match_golden_contract() -> None:
    golden = _load_golden()
    config = FixedRulesConfig.model_validate(golden["fixed_rules_config"])

    normalized_config = validate_and_normalize_fixed_rules_config(config)
    task_tree = build_fixed_rules_task_tree(normalized_config)

    actual_rules = [
        rule.model_dump(mode="json", exclude_none=False)
        for rule in task_tree.rules
    ]

    assert _stable_rules(actual_rules) == _stable_rules(golden["expected_validation_rules"])


def test_fixed_rules_task_tree_keeps_node_driven_variables() -> None:
    golden = _load_golden()
    config = FixedRulesConfig.model_validate(golden["fixed_rules_config"])

    normalized_config = validate_and_normalize_fixed_rules_config(config)
    task_tree = build_fixed_rules_task_tree(normalized_config)

    actual_tags = {variable.tag for variable in task_tree.variables}

    assert set(golden["expected_task_tree_variable_tags"]) <= actual_tags

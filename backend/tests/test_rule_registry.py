"""规则注册表与拆分入口回归测试。"""

from __future__ import annotations

from backend.app.rules.engine_core import RULE_REGISTRY
from backend.app.rules.registry import RULE_METADATA


EXPECTED_RULE_TYPES = {
    "not_null",
    "unique",
    "fixed_value_compare",
    "regex_check",
    "sequence_order_check",
    "cross_table_mapping",
    "composite_condition_check",
    "dual_composite_compare",
    "multi_composite_pipeline_check",
    "multi_composite_mapping_check",
}


def test_rule_registry_contains_all_supported_rule_types() -> None:
    """拆分 handler 后，执行注册表仍覆盖所有规则类型。"""

    assert EXPECTED_RULE_TYPES.issubset(RULE_REGISTRY)
    assert EXPECTED_RULE_TYPES.issubset(RULE_METADATA)


def test_fixed_handler_split_entries_use_real_package_modules() -> None:
    """fixed handler 拆分后不再通过 _fixed_legacy 动态加载旧文件。"""

    import sys
    from backend.app.rules.handlers import fixed
    from backend.app.rules.handlers.fixed import (
        basic,
        composite,
        dual_composite,
        mapping,
        pipeline,
        sequence,
    )

    assert "backend.app.rules.handlers._fixed_legacy" not in sys.modules
    assert fixed.__file__.endswith("__init__.py")
    assert basic.check_fixed_value_compare is fixed.check_fixed_value_compare
    assert basic.check_regex_check is fixed.check_regex_check
    assert composite.check_composite_condition_check is fixed.check_composite_condition_check
    assert dual_composite.check_dual_composite_compare is fixed.check_dual_composite_compare
    assert sequence.check_sequence_order is fixed.check_sequence_order
    assert pipeline.check_multi_composite_pipeline_check is fixed.check_multi_composite_pipeline_check
    assert mapping.check_multi_composite_mapping_check is fixed.check_multi_composite_mapping_check

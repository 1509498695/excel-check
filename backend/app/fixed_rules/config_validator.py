"""固定规则配置校验入口。"""

from __future__ import annotations

from backend.app.api.fixed_rules_schemas import FixedRulesConfig
from backend.app.fixed_rules.config_normalizer import validate_and_normalize_fixed_rules_config


def validate_config(config: FixedRulesConfig) -> FixedRulesConfig:
    return validate_and_normalize_fixed_rules_config(config)

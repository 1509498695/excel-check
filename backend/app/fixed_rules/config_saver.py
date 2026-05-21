"""固定规则配置保存。"""

from __future__ import annotations

import json

from backend.app.api.fixed_rules_schemas import FixedRulesConfig
from backend.app.fixed_rules.config_migrator import _ensure_v4_config
from backend.app.fixed_rules.config_normalizer import validate_and_normalize_fixed_rules_config
from backend.config import settings


def save_fixed_rules_config(config: FixedRulesConfig) -> FixedRulesConfig:
    """?????????????"""
    normalized_config = validate_and_normalize_fixed_rules_config(_ensure_v4_config(config))
    config_path = settings.fixed_rules_config_path
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            normalized_config.model_dump(mode="json", exclude_none=True),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return normalized_config

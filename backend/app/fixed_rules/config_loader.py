"""固定规则配置加载与原始 payload 解析。"""

from __future__ import annotations

import json

from backend.app.api.fixed_rules_schemas import FixedRulesConfig, FixedRulesConfigIssue
from backend.app.fixed_rules.config_common import FIXED_RULES_CONFIG_VERSION, _build_default_group
from backend.app.fixed_rules.config_migrator import _ensure_v4_config, _parse_fixed_rules_payload
from backend.app.fixed_rules.config_normalizer import _validate_and_normalize_fixed_rules_config
from backend.config import settings


def build_default_fixed_rules_config() -> FixedRulesConfig:
    """??????????????????"""
    return FixedRulesConfig(
        version=FIXED_RULES_CONFIG_VERSION,
        configured=False,
        sources=[],
        variables=[],
        groups=[_build_default_group()],
        rules=[],
        local_path_replacement_presets=[],
        selected_local_path_replacement_preset=None,
        svn_path_replacement_presets=[],
        selected_svn_path_replacement_preset=None,
    )


def load_fixed_rules_config() -> FixedRulesConfig:
    """??????????????????????????????"""
    config, _ = _load_fixed_rules_config_payload(allow_runtime_issues=False)
    return config


def parse_raw_fixed_rules_config(raw: dict) -> FixedRulesConfig:
    """将数据库读出的原始 dict 解析为 FixedRulesConfig，兼容遗留格式。"""
    return _parse_fixed_rules_payload(raw)


def load_fixed_rules_config_with_issues(
    config: FixedRulesConfig | None = None,
    *,
    allow_legacy_mapping_config: bool = False,
    allow_unsupported_csv: bool = True,
) -> tuple[FixedRulesConfig, list[FixedRulesConfigIssue]]:
    """从文件或传入的配置加载并校验固定规则，返回配置与问题列表。"""
    if config is not None:
        return _validate_and_normalize_fixed_rules_config(
            _ensure_v4_config(config),
            allow_runtime_issues=True,
            allow_legacy_mapping_config=allow_legacy_mapping_config,
            allow_unsupported_csv=allow_unsupported_csv,
        )
    return _load_fixed_rules_config_payload(
        allow_runtime_issues=True,
        allow_legacy_mapping_config=allow_legacy_mapping_config,
    )


def _load_fixed_rules_config_payload(
    *,
    allow_runtime_issues: bool,
    allow_legacy_mapping_config: bool = False,
) -> tuple[FixedRulesConfig, list[FixedRulesConfigIssue]]:
    """?????????????"""
    config_path = settings.fixed_rules_config_path
    if not config_path.exists():
        return build_default_fixed_rules_config(), []

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"???????????????? JSON?{exc}") from exc

    raw_config = _parse_fixed_rules_payload(payload)
    return _validate_and_normalize_fixed_rules_config(
        raw_config,
        allow_runtime_issues=allow_runtime_issues,
        allow_legacy_mapping_config=allow_legacy_mapping_config,
    )

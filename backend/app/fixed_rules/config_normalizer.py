"""固定规则配置归一化流程编排。"""

from __future__ import annotations

from backend.app.api.fixed_rules_schemas import FixedRulesConfig, FixedRulesConfigIssue
from backend.app.fixed_rules.config_common import (
    FIXED_RULES_CONFIG_VERSION,
    _normalize_local_path_replacement_presets,
    _normalize_selected_local_path_replacement_preset,
    _normalize_selected_svn_path_replacement_preset,
    _normalize_svn_path_replacement_presets,
)
from backend.app.fixed_rules.config_migrator import _ensure_v4_config
from backend.app.fixed_rules.group_normalizer import _normalize_groups
from backend.app.fixed_rules.rule_normalizer import _normalize_rules
from backend.app.fixed_rules.source_normalizer import _normalize_sources
from backend.app.fixed_rules.source_runtime_validator import _validate_source_runtime_bindings
from backend.app.fixed_rules.variable_normalizer import _normalize_variables


def validate_and_normalize_fixed_rules_config(
    config: FixedRulesConfig,
) -> FixedRulesConfig:
    """校验并归一化固定规则配置。"""
    normalized_config, _ = _validate_and_normalize_fixed_rules_config(
        config,
        allow_runtime_issues=False,
    )
    return normalized_config


def _validate_and_normalize_fixed_rules_config(
    config: FixedRulesConfig,
    *,
    allow_runtime_issues: bool,
    allow_legacy_mapping_config: bool = False,
    allow_unsupported_csv: bool | None = None,
) -> tuple[FixedRulesConfig, list[FixedRulesConfigIssue]]:
    """执行固定规则配置迁移、归一化与可选运行时问题收集。"""
    migrated_config = _ensure_v4_config(config)
    groups = _normalize_groups(migrated_config.groups)
    allow_csv_compat = allow_runtime_issues if allow_unsupported_csv is None else allow_unsupported_csv
    sources = _normalize_sources(
        migrated_config.sources,
        allow_unsupported_csv=allow_csv_compat,
    )
    source_map = {source.id: source for source in sources}
    metadata_cache: dict[str, dict[str, object]] = {}
    config_issues: list[FixedRulesConfigIssue] = []
    issue_keys: set[tuple[str, str | None, str | None, str | None, str]] = set()
    _validate_source_runtime_bindings(
        sources,
        metadata_cache=metadata_cache,
        config_issues=config_issues if allow_runtime_issues else None,
        issue_keys=issue_keys if allow_runtime_issues else None,
    )
    variables = _normalize_variables(
        migrated_config.variables,
        source_map=source_map,
        metadata_cache=metadata_cache,
        config_issues=config_issues if allow_runtime_issues else None,
        issue_keys=issue_keys if allow_runtime_issues else None,
    )
    variable_map = {variable.tag: variable for variable in variables}
    rules = _normalize_rules(
        migrated_config.rules,
        group_ids={group.group_id for group in groups},
        variable_map=variable_map,
        allow_legacy_mapping_config=allow_legacy_mapping_config,
        config_issues=config_issues if allow_runtime_issues else None,
        issue_keys=issue_keys if allow_runtime_issues else None,
    )

    configured = bool(
        sources or variables or rules or len(groups) > 1 or migrated_config.configured
    )
    return (
        FixedRulesConfig(
            version=FIXED_RULES_CONFIG_VERSION,
            configured=configured,
            sources=sources,
            variables=variables,
            groups=groups,
            rules=rules,
            local_path_replacement_presets=_normalize_local_path_replacement_presets(
                migrated_config.local_path_replacement_presets
                or migrated_config.path_replacement_presets
            ),
            selected_local_path_replacement_preset=_normalize_selected_local_path_replacement_preset(
                migrated_config.selected_local_path_replacement_preset
                or migrated_config.selected_path_replacement_preset,
                migrated_config.local_path_replacement_presets
                or migrated_config.path_replacement_presets,
            ),
            svn_path_replacement_presets=_normalize_svn_path_replacement_presets(
                migrated_config.svn_path_replacement_presets
            ),
            selected_svn_path_replacement_preset=_normalize_selected_svn_path_replacement_preset(
                migrated_config.selected_svn_path_replacement_preset,
                migrated_config.svn_path_replacement_presets,
            ),
        ),
        config_issues,
    )

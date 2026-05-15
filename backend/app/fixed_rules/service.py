"""Compatibility facade for fixed-rules configuration and execution."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.fixed_rules_schemas import (
    FixedRulesConfig,
    FixedRulesConfigIssue,
    UNGROUPED_GROUP_ID,
    UNGROUPED_GROUP_NAME,
)
from backend.app.fixed_rules.config_common import (
    COMPARE_STYLE_OPERATORS,
    COMPOSITE_KEY_FIELD,
    FIXED_RULES_CONFIG_VERSION,
    SET_STYLE_OPERATORS,
    SUPPORTED_COMPOSITE_ASSERTION_OPERATORS,
    SUPPORTED_COMPOSITE_FILTER_OPERATORS,
    SUPPORTED_DUAL_COMPOSITE_KEY_CHECK_MODES,
    SUPPORTED_DUAL_COMPOSITE_OPERATORS,
    SUPPORTED_FIXED_RULE_OPERATORS,
    SUPPORTED_FIXED_RULE_TYPES,
    SUPPORTED_LOCAL_SOURCE_SUFFIXES,
    SUPPORTED_MULTI_PIPELINE_ASSERTION_OPERATORS,
    _build_default_group,
)
from backend.app.fixed_rules.config_migration import (
    LEGACY_FIXED_RULE_KEYS,
    _ensure_v4_config,
    _parse_fixed_rules_payload,
)
from backend.app.fixed_rules.config_validation import (
    _validate_and_normalize_fixed_rules_config,
    validate_and_normalize_fixed_rules_config,
)
from backend.app.fixed_rules.execution import (
    execute_fixed_rules_for_project as _execute_fixed_rules_for_project,
    execute_saved_fixed_rules as _execute_saved_fixed_rules,
    run_saved_fixed_rules_svn_update as _run_saved_fixed_rules_svn_update,
)
from backend.app.fixed_rules.task_tree import build_fixed_rules_task_tree
from backend.app.loaders.svn_manager import update_svn_working_copy
from backend.config import settings


__all__ = [
    "COMPARE_STYLE_OPERATORS",
    "COMPOSITE_KEY_FIELD",
    "FIXED_RULES_CONFIG_VERSION",
    "LEGACY_FIXED_RULE_KEYS",
    "SET_STYLE_OPERATORS",
    "SUPPORTED_COMPOSITE_ASSERTION_OPERATORS",
    "SUPPORTED_COMPOSITE_FILTER_OPERATORS",
    "SUPPORTED_DUAL_COMPOSITE_KEY_CHECK_MODES",
    "SUPPORTED_DUAL_COMPOSITE_OPERATORS",
    "SUPPORTED_FIXED_RULE_OPERATORS",
    "SUPPORTED_FIXED_RULE_TYPES",
    "SUPPORTED_LOCAL_SOURCE_SUFFIXES",
    "SUPPORTED_MULTI_PIPELINE_ASSERTION_OPERATORS",
    "UNGROUPED_GROUP_ID",
    "UNGROUPED_GROUP_NAME",
    "build_default_fixed_rules_config",
    "build_fixed_rules_task_tree",
    "execute_fixed_rules_for_project",
    "execute_saved_fixed_rules",
    "load_fixed_rules_config",
    "load_fixed_rules_config_with_issues",
    "parse_raw_fixed_rules_config",
    "run_saved_fixed_rules_svn_update",
    "save_fixed_rules_config",
    "update_svn_working_copy",
    "validate_and_normalize_fixed_rules_config",
]


def build_default_fixed_rules_config() -> FixedRulesConfig:
    """返回项目校验的默认配置。"""
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
    """从默认路径加载并校验固定规则配置。"""
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
    """从配置文件读取并归一化固定规则配置。"""
    config_path = settings.fixed_rules_config_path
    if not config_path.exists():
        return build_default_fixed_rules_config(), []

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"固定规则配置文件不是合法 JSON：{exc}") from exc

    raw_config = _parse_fixed_rules_payload(payload)
    return _validate_and_normalize_fixed_rules_config(
        raw_config,
        allow_runtime_issues=allow_runtime_issues,
        allow_legacy_mapping_config=allow_legacy_mapping_config,
    )


def save_fixed_rules_config(config: FixedRulesConfig) -> FixedRulesConfig:
    """校验并保存固定规则配置。"""
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


def execute_saved_fixed_rules(
    config: FixedRulesConfig | None = None,
    selected_rule_ids: list[str] | None = None,
) -> dict[str, object]:
    """执行固定规则。如果传入 config 则直接使用，否则从文件加载。"""
    if config is None:
        config = load_fixed_rules_config()
    return _execute_saved_fixed_rules(config, selected_rule_ids=selected_rule_ids)


async def execute_fixed_rules_for_project(
    db: AsyncSession,
    project_id: int,
    *,
    user_scope: str | None = None,
    selected_rule_ids: list[str] | None = None,
) -> dict[str, Any]:
    """以项目级配置执行项目校验，落库后返回执行摘要。"""
    return await _execute_fixed_rules_for_project(
        db,
        project_id,
        user_scope=user_scope,
        selected_rule_ids=selected_rule_ids,
    )


def run_saved_fixed_rules_svn_update(
    config: FixedRulesConfig | None = None,
    *,
    user_scope: str | None = None,
) -> dict[str, object]:
    """对固定规则配置中的数据源执行 SVN 更新。"""
    if config is None:
        config = load_fixed_rules_config()
    return _run_saved_fixed_rules_svn_update(
        config,
        user_scope=user_scope,
        update_working_copy=update_svn_working_copy,
    )

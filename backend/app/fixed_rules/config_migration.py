"""Fixed-rules config parsing and legacy migration helpers."""

from __future__ import annotations

from pathlib import Path

from backend.app.api.fixed_rules_schemas import (
    FixedRuleDefinition,
    FixedRulesConfig,
    UNGROUPED_GROUP_ID,
)
from backend.app.api.schemas import DataSource, VariableTag
from backend.app.fixed_rules.config_common import (
    FIXED_RULES_CONFIG_VERSION,
    _build_single_variable_tag,
    _build_source_id_from_path,
    _normalize_local_path_replacement_presets,
    _normalize_local_source_path,
    _normalize_selected_local_path_replacement_preset,
    _normalize_selected_svn_path_replacement_preset,
    _normalize_svn_path_replacement_presets,
)

LEGACY_FIXED_RULE_KEYS = {"file_path", "sheet", "columns", "svn_enabled"}


def _parse_fixed_rules_payload(payload: object) -> FixedRulesConfig:
    """???????????????? JSON ???"""
    if not isinstance(payload, dict):
        raise ValueError("?????????????????????????")

    if LEGACY_FIXED_RULE_KEYS.intersection(payload):
        return _migrate_legacy_payload(payload)

    try:
        config = FixedRulesConfig.model_validate(payload)
    except Exception as exc:  # pragma: no cover - ???????????
        raise ValueError(f"??????????????{exc}") from exc

    return _ensure_v4_config(config)


def _migrate_legacy_payload(payload: dict[str, object]) -> FixedRulesConfig:
    """???????????????????????"""
    file_path = str(payload.get("file_path") or "").strip()
    sheet = str(payload.get("sheet") or "").strip()
    raw_rules = payload.get("rules") or []

    if not isinstance(raw_rules, list):
        raise ValueError("?????????? rules ????????")

    migrated_rules: list[dict[str, object]] = []
    for raw_rule in raw_rules:
        if not isinstance(raw_rule, dict):
            raise ValueError("????????????????????")

        column = str(raw_rule.get("column") or "").strip()
        if not column:
            raise ValueError("??????????????????????????")

        migrated_rules.append(
            {
                "rule_id": raw_rule.get("rule_id", ""),
                "group_id": raw_rule.get("group_id") or UNGROUPED_GROUP_ID,
                "rule_name": raw_rule.get("rule_name", ""),
                "binding": {
                    "file_path": file_path,
                    "sheet": sheet,
                    "column": column,
                },
                "rule_type": raw_rule.get("rule_type") or "fixed_value_compare",
                "operator": raw_rule.get("operator"),
                "expected_value": raw_rule.get("expected_value", ""),
            }
        )

    config = FixedRulesConfig.model_validate(
        {
            "version": 3,
            "configured": bool(payload.get("configured", False)),
            "groups": payload.get("groups") or [],
            "rules": migrated_rules,
        }
    )
    return _ensure_v4_config(config)


def _ensure_v4_config(config: FixedRulesConfig) -> FixedRulesConfig:
    """??? binding ????? sources / variables / target_variable_tag?"""
    needs_migration = config.version < FIXED_RULES_CONFIG_VERSION or any(
        not rule.target_variable_tag and rule.binding is not None
        for rule in config.rules
    )
    if not needs_migration:
        return config

    migrated_sources = [source.model_copy(deep=True) for source in config.sources]
    migrated_variables = [variable.model_copy(deep=True) for variable in config.variables]
    seen_source_ids = {source.id for source in migrated_sources}
    seen_variable_tags = {variable.tag for variable in migrated_variables}

    source_id_by_key: dict[str, str] = {}
    for source in migrated_sources:
        locator = source.pathOrUrl or source.path or source.url or ""
        if source.type in {"local_excel", "local_csv", "svn"} and locator:
            source_id_by_key[str(Path(locator).expanduser().resolve(strict=False)).lower()] = source.id

    variable_tag_by_key: dict[tuple[str, str, str], str] = {}
    for variable in migrated_variables:
        if (variable.variable_kind or "single") != "single" or not variable.column:
            continue
        variable_tag_by_key[
            (
                variable.source_id,
                variable.sheet,
                variable.column,
            )
        ] = variable.tag

    migrated_rules: list[FixedRuleDefinition] = []
    for rule in config.rules:
        if rule.target_variable_tag:
            migrated_rules.append(
                FixedRuleDefinition(
                    rule_id=rule.rule_id,
                    group_id=rule.group_id,
                    rule_name=rule.rule_name,
                    target_variable_tag=rule.target_variable_tag,
                    display_field=rule.display_field,
                    rule_type=rule.rule_type,
                    operator=rule.operator,
                    expected_value=rule.expected_value,
                    expected_value_mode=rule.expected_value_mode,
                    reference_variable_tag=rule.reference_variable_tag,
                    sequence_direction=rule.sequence_direction,
                    sequence_step=rule.sequence_step,
                    sequence_start_mode=rule.sequence_start_mode,
                    sequence_start_value=rule.sequence_start_value,
                    composite_config=rule.composite_config,
                    key_check_mode=rule.key_check_mode,
                    left_key_field=rule.left_key_field,
                    right_key_field=rule.right_key_field,
                    comparisons=rule.comparisons,
                    left_filters=rule.left_filters,
                    right_filters=rule.right_filters,
                    pipeline_config=rule.pipeline_config,
                    mapping_config=rule.mapping_config,
                )
            )
            continue

        if rule.binding is None:
            migrated_rules.append(
                FixedRuleDefinition(
                    rule_id=rule.rule_id,
                    group_id=rule.group_id,
                    rule_name=rule.rule_name,
                    target_variable_tag=rule.target_variable_tag,
                    display_field=rule.display_field,
                    rule_type=rule.rule_type,
                    operator=rule.operator,
                    expected_value=rule.expected_value,
                    expected_value_mode=rule.expected_value_mode,
                    reference_variable_tag=rule.reference_variable_tag,
                    sequence_direction=rule.sequence_direction,
                    sequence_step=rule.sequence_step,
                    sequence_start_mode=rule.sequence_start_mode,
                    sequence_start_value=rule.sequence_start_value,
                    composite_config=rule.composite_config,
                    key_check_mode=rule.key_check_mode,
                    left_key_field=rule.left_key_field,
                    right_key_field=rule.right_key_field,
                    comparisons=rule.comparisons,
                    left_filters=rule.left_filters,
                    right_filters=rule.right_filters,
                    pipeline_config=rule.pipeline_config,
                    mapping_config=rule.mapping_config,
                )
            )
            continue

        binding = rule.binding
        source_path = _normalize_local_source_path(
            "__migration__",
            binding.file_path,
            "local_excel",
        )
        source_key = str(source_path).lower()
        source_id = source_id_by_key.get(source_key)
        if source_id is None:
            source_id = _build_source_id_from_path(source_path, seen_source_ids)
            seen_source_ids.add(source_id)
            source_id_by_key[source_key] = source_id
            migrated_sources.append(
                DataSource(
                    id=source_id,
                    type="local_excel",
                    path=str(source_path),
                    pathOrUrl=str(source_path),
                )
            )

        variable_key = (
            source_id,
            binding.sheet,
            binding.column,
        )
        target_tag = variable_tag_by_key.get(variable_key)
        if target_tag is None:
            target_tag = _build_single_variable_tag(
                source_id=source_id,
                sheet=binding.sheet,
                column=binding.column,
                seen_tags=seen_variable_tags,
            )
            seen_variable_tags.add(target_tag)
            variable_tag_by_key[variable_key] = target_tag
            migrated_variables.append(
                VariableTag(
                    tag=target_tag,
                    source_id=source_id,
                    sheet=binding.sheet,
                    variable_kind="single",
                    column=binding.column,
                    expected_type="str",
                )
            )

        migrated_rules.append(
            FixedRuleDefinition(
                rule_id=rule.rule_id,
                group_id=rule.group_id,
                rule_name=rule.rule_name,
                target_variable_tag=target_tag,
                display_field=rule.display_field,
                rule_type=rule.rule_type,
                operator=rule.operator,
                expected_value=rule.expected_value,
                expected_value_mode=rule.expected_value_mode,
                reference_variable_tag=rule.reference_variable_tag,
                sequence_direction=rule.sequence_direction,
                sequence_step=rule.sequence_step,
                sequence_start_mode=rule.sequence_start_mode,
                sequence_start_value=rule.sequence_start_value,
                composite_config=rule.composite_config,
                key_check_mode=rule.key_check_mode,
                left_key_field=rule.left_key_field,
                right_key_field=rule.right_key_field,
                comparisons=rule.comparisons,
                left_filters=rule.left_filters,
                right_filters=rule.right_filters,
                pipeline_config=rule.pipeline_config,
                mapping_config=rule.mapping_config,
            )
        )

    return FixedRulesConfig(
        version=FIXED_RULES_CONFIG_VERSION,
        configured=config.configured,
        sources=migrated_sources,
        variables=migrated_variables,
        groups=config.groups,
        rules=migrated_rules,
        local_path_replacement_presets=_normalize_local_path_replacement_presets(
            config.local_path_replacement_presets or config.path_replacement_presets
        ),
        selected_local_path_replacement_preset=_normalize_selected_local_path_replacement_preset(
            config.selected_local_path_replacement_preset
            or config.selected_path_replacement_preset,
            config.local_path_replacement_presets or config.path_replacement_presets,
        ),
        svn_path_replacement_presets=_normalize_svn_path_replacement_presets(
            config.svn_path_replacement_presets
        ),
        selected_svn_path_replacement_preset=_normalize_selected_svn_path_replacement_preset(
            config.selected_svn_path_replacement_preset,
            config.svn_path_replacement_presets,
        ),
    )

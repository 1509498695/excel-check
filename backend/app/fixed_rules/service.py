"""????????????????????????"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from backend.app.api.fixed_rules_schemas import (
    CompositeAssertionOperator,
    CompositeBranch,
    CompositeCondition,
    CompositeFilterOperator,
    CompositeRuleConfig,
    DualCompositeComparison,
    DualCompositeKeyCheckMode,
    FixedRuleDefinition,
    FixedRuleGroup,
    FixedRulesConfig,
    FixedRulesConfigIssue,
    UNGROUPED_GROUP_ID,
    UNGROUPED_GROUP_NAME,
)
from backend.app.api.schemas import DataSource, TaskTree, ValidationRule, VariableTag
from backend.app.execution_pipeline import run_execution_pipeline
from backend.app.loaders.local_reader import read_source_metadata
from backend.app.loaders.svn_manager import update_svn_working_copy
from backend.app.utils.formatter import build_execution_response
from backend.config import settings


FIXED_RULES_CONFIG_VERSION = 4
COMPOSITE_KEY_FIELD = "__key__"
SUPPORTED_FIXED_RULE_TYPES = {
    "fixed_value_compare",
    "not_null",
    "unique",
    "sequence_order_check",
    "cross_table_mapping",
    "composite_condition_check",
    "dual_composite_compare",
}
SUPPORTED_FIXED_RULE_OPERATORS = {"eq", "ne", "gt", "lt"}
SUPPORTED_COMPOSITE_FILTER_OPERATORS = {"eq", "ne", "gt", "lt", "not_null"}
SUPPORTED_COMPOSITE_ASSERTION_OPERATORS = {
    "eq",
    "ne",
    "gt",
    "lt",
    "not_null",
    "unique",
    "duplicate_required",
}
SUPPORTED_DUAL_COMPOSITE_OPERATORS = {"eq", "ne", "gt", "lt", "not_null"}
SUPPORTED_DUAL_COMPOSITE_KEY_CHECK_MODES = {"baseline_only", "bidirectional"}
COMPARE_STYLE_OPERATORS = {"eq", "ne", "gt", "lt"}
SET_STYLE_OPERATORS = {"unique", "duplicate_required"}
SUPPORTED_LOCAL_SOURCE_SUFFIXES = {
    "local_excel": {".xls", ".xlsx"},
    "local_csv": {".csv"},
}
LEGACY_FIXED_RULE_KEYS = {"file_path", "sheet", "columns", "svn_enabled"}


def _normalize_sequence_numeric(
    value: str | None,
    *,
    field_name: str,
    rule_id: str,
    positive_only: bool = False,
) -> str:
    """校验并规范顺序校验使用的数字参数。"""
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError(f"规则 '{rule_id}' 缺少 {field_name}。")

    try:
        numeric = float(normalized)
    except ValueError as exc:
        raise ValueError(f"规则 '{rule_id}' 的 {field_name} 必须是合法数字。") from exc

    if positive_only and numeric <= 0:
        raise ValueError(f"规则 '{rule_id}' 的 {field_name} 必须大于 0。")

    if numeric.is_integer():
        return str(int(numeric))
    return format(numeric, "g")


def build_default_fixed_rules_config() -> FixedRulesConfig:
    """??????????????????"""
    return FixedRulesConfig(
        version=FIXED_RULES_CONFIG_VERSION,
        configured=False,
        sources=[],
        variables=[],
        groups=[_build_default_group()],
        rules=[],
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
) -> tuple[FixedRulesConfig, list[FixedRulesConfigIssue]]:
    """从文件或传入的配置加载并校验固定规则，返回配置与问题列表。"""
    if config is not None:
        return _validate_and_normalize_fixed_rules_config(
            _ensure_v4_config(config),
            allow_runtime_issues=True,
        )
    return _load_fixed_rules_config_payload(allow_runtime_issues=True)


def _load_fixed_rules_config_payload(
    *,
    allow_runtime_issues: bool,
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
    )


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


def execute_saved_fixed_rules(
    config: FixedRulesConfig | None = None,
    selected_rule_ids: list[str] | None = None,
) -> dict[str, object]:
    """执行固定规则。如果传入 config 则直接使用，否则从文件加载。"""
    if config is None:
        config = load_fixed_rules_config()
    ordered_rules = _get_ordered_rules(config, selected_rule_ids=selected_rule_ids)
    if not ordered_rules:
        raise ValueError("当前没有可执行的固定规则，请先配置规则再执行。")
    task_tree = build_fixed_rules_task_tree(config, selected_rule_ids=selected_rule_ids)
    start = time.perf_counter()
    execution_artifacts = run_execution_pipeline(task_tree)
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    total_rows_scanned = sum(
        len(frame) for frame in execution_artifacts["loaded_variables"].values()
    )
    return build_execution_response(
        abnormal_results=execution_artifacts["abnormal_results"],
        execution_time_ms=elapsed_ms,
        total_rows_scanned=total_rows_scanned,
        failed_sources=execution_artifacts["failed_sources"],
        msg="Execution Completed",
    )


def run_saved_fixed_rules_svn_update(
    config: FixedRulesConfig | None = None,
) -> dict[str, object]:
    """对固定规则配置中的数据源目录执行 SVN 更新。"""
    if config is None:
        config = load_fixed_rules_config()
    working_copies = _collect_working_copies(config.sources)
    if not working_copies:
        raise ValueError("??????? SVN ?????????????")

    results: list[dict[str, object]] = []
    updated_paths = 0

    for working_copy in working_copies:
        try:
            update_result = update_svn_working_copy(working_copy)
        except NotImplementedError:
            raise
        except (FileNotFoundError, ValueError) as exc:
            results.append(
                {
                    "working_copy": str(working_copy),
                    "status": "error",
                    "output": "",
                    "used_executable": "",
                    "error": str(exc),
                }
            )
            continue

        updated_paths += 1
        results.append(
            {
                "working_copy": str(working_copy),
                "status": "success",
                "output": update_result["output"],
                "used_executable": update_result["used_executable"],
            }
        )

    return {
        "total_paths": len(working_copies),
        "updated_paths": updated_paths,
        "results": results,
    }


def build_fixed_rules_task_tree(
    config: FixedRulesConfig,
    selected_rule_ids: list[str] | None = None,
) -> TaskTree:
    """????????????????????? TaskTree?"""
    ordered_rules = _get_ordered_rules(config, selected_rule_ids=selected_rule_ids)
    variable_map = {variable.tag: variable for variable in config.variables}
    needed_tags = {
        tag
        for rule in ordered_rules
        for tag in [rule.target_variable_tag, rule.reference_variable_tag]
        if tag
    }

    variables = [variable for variable in config.variables if variable.tag in needed_tags]
    source_ids = {variable.source_id for variable in variables}
    sources = [source for source in config.sources if source.id in source_ids]

    task_rules = [
        ValidationRule(
            rule_id=rule.rule_id,
            rule_type=rule.rule_type,
            params=_build_fixed_rule_params(rule, variable_map[rule.target_variable_tag]),
        )
        for rule in ordered_rules
    ]

    return TaskTree(
        sources=sources,
        variables=variables,
        rules=task_rules,
        selected_rule_ids=selected_rule_ids,
    )


def validate_and_normalize_fixed_rules_config(
    config: FixedRulesConfig,
) -> FixedRulesConfig:
    """??????????????????"""
    normalized_config, _ = _validate_and_normalize_fixed_rules_config(
        config,
        allow_runtime_issues=False,
    )
    return normalized_config


def _validate_and_normalize_fixed_rules_config(
    config: FixedRulesConfig,
    *,
    allow_runtime_issues: bool,
) -> tuple[FixedRulesConfig, list[FixedRulesConfigIssue]]:
    """???????????????????????????"""
    migrated_config = _ensure_v4_config(config)
    groups = _normalize_groups(migrated_config.groups)
    sources = _normalize_sources(migrated_config.sources)
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
        ),
        config_issues,
    )


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
                variable.sheet.strip(),
                variable.column.strip(),
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
                    rule_type=rule.rule_type,
                    operator=rule.operator,
                    expected_value=rule.expected_value,
                    reference_variable_tag=rule.reference_variable_tag,
                    sequence_direction=rule.sequence_direction,
                    sequence_step=rule.sequence_step,
                    sequence_start_mode=rule.sequence_start_mode,
                    sequence_start_value=rule.sequence_start_value,
                    composite_config=rule.composite_config,
                    key_check_mode=rule.key_check_mode,
                    comparisons=rule.comparisons,
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
                    rule_type=rule.rule_type,
                    operator=rule.operator,
                    expected_value=rule.expected_value,
                    reference_variable_tag=rule.reference_variable_tag,
                    sequence_direction=rule.sequence_direction,
                    sequence_step=rule.sequence_step,
                    sequence_start_mode=rule.sequence_start_mode,
                    sequence_start_value=rule.sequence_start_value,
                    composite_config=rule.composite_config,
                    key_check_mode=rule.key_check_mode,
                    comparisons=rule.comparisons,
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
            binding.sheet.strip(),
            binding.column.strip(),
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
                    sheet=binding.sheet.strip(),
                    variable_kind="single",
                    column=binding.column.strip(),
                    expected_type="str",
                )
            )

        migrated_rules.append(
            FixedRuleDefinition(
                rule_id=rule.rule_id,
                group_id=rule.group_id,
                rule_name=rule.rule_name,
                target_variable_tag=target_tag,
                rule_type=rule.rule_type,
                operator=rule.operator,
                expected_value=rule.expected_value,
                reference_variable_tag=rule.reference_variable_tag,
                sequence_direction=rule.sequence_direction,
                sequence_step=rule.sequence_step,
                sequence_start_mode=rule.sequence_start_mode,
                sequence_start_value=rule.sequence_start_value,
                composite_config=rule.composite_config,
                key_check_mode=rule.key_check_mode,
                comparisons=rule.comparisons,
            )
        )

    return FixedRulesConfig(
        version=FIXED_RULES_CONFIG_VERSION,
        configured=config.configured,
        sources=migrated_sources,
        variables=migrated_variables,
        groups=config.groups,
        rules=migrated_rules,
    )


def _normalize_groups(groups: list[FixedRuleGroup]) -> list[FixedRuleGroup]:
    """??????????????????????"""
    normalized_groups: list[FixedRuleGroup] = [_build_default_group()]
    seen_group_ids = {UNGROUPED_GROUP_ID}

    for group in groups:
        group_id = group.group_id.strip()
        group_name = _normalize_group_name(group_id, group.group_name.strip())

        if not group_id or not group_name:
            raise ValueError("????? group_id ? group_name?")
        if group_id == UNGROUPED_GROUP_ID:
            continue
        if group_id in seen_group_ids:
            raise ValueError(f"??? ID ???'{group_id}'?")

        normalized_groups.append(
            FixedRuleGroup(
                group_id=group_id,
                group_name=group_name,
                builtin=False,
            )
        )
        seen_group_ids.add(group_id)

    return normalized_groups


def _normalize_group_name(group_id: str, group_name: str) -> str:
    """修正已知的历史乱码分组名称，避免运行态配置继续回显脏数据。"""
    if group_id == UNGROUPED_GROUP_ID and (
        not group_name or "æ" in group_name or "?" in group_name
    ):
        return UNGROUPED_GROUP_NAME

    if group_id == "basic-checks" and (
        not group_name or group_name.strip("?") == "" or "æ" in group_name
    ):
        return "基础校验"

    return group_name


def _normalize_sources(sources: list[DataSource]) -> list[DataSource]:
    """?????????????????"""
    normalized_sources: list[DataSource] = []
    seen_source_ids: set[str] = set()

    for source in sources:
        source_id = source.id.strip()
        if not source_id:
            raise ValueError("????????? id?")
        if source_id in seen_source_ids:
            raise ValueError(f"??????? ID ???'{source_id}'?")

        source_type = source.type
        raw_locator = (source.pathOrUrl or source.path or source.url or "").strip()
        token = source.token.strip() if source.token else None

        if source_type == "feishu":
            if not raw_locator:
                raise ValueError(f"??????? '{source_id}' ???????")
            normalized_sources.append(
                DataSource(
                    id=source_id,
                    type=source_type,
                    url=raw_locator,
                    pathOrUrl=raw_locator,
                    token=token or None,
                )
            )
        elif source_type in {"local_excel", "local_csv"}:
            normalized_path = _normalize_local_source_path(source_id, raw_locator, source_type)
            normalized_sources.append(
                DataSource(
                    id=source_id,
                    type=source_type,
                    path=str(normalized_path),
                    pathOrUrl=str(normalized_path),
                    token=token or None,
                )
            )
        elif source_type == "svn":
            if not raw_locator:
                raise ValueError(f"??????? '{source_id}' ?? SVN ?????")
            normalized_path = Path(raw_locator).expanduser().resolve(strict=False)
            normalized_sources.append(
                DataSource(
                    id=source_id,
                    type=source_type,
                    path=str(normalized_path),
                    pathOrUrl=str(normalized_path),
                    token=token or None,
                )
            )
        else:  # pragma: no cover - ? pydantic Literal ??
            raise ValueError(f"??????? '{source_id}' ????????? '{source_type}'?")

        seen_source_ids.add(source_id)

    return normalized_sources


def _validate_source_runtime_bindings(
    sources: list[DataSource],
    *,
    metadata_cache: dict[str, dict[str, object]],
    config_issues: list[FixedRulesConfigIssue] | None = None,
    issue_keys: set[tuple[str, str | None, str | None, str | None, str]] | None = None,
) -> None:
    """把数据源级别的运行时校验前置，确保空变量池场景也能捕获失效路径。"""
    for source in sources:
        if source.type not in {"local_excel", "local_csv"}:
            continue

        raw_locator = (source.pathOrUrl or source.path or "").strip()
        if not raw_locator:
            continue

        source_path = Path(raw_locator).expanduser().resolve(strict=False)
        if not source_path.exists():
            message = (
                f"数据源“{source.id}”的本地路径已失效：{source_path}。"
                "请到“数据源接入管理”中修复路径后再保存或执行。"
            )
            if config_issues is None:
                raise ValueError(message)
            _append_config_issue(
                config_issues,
                issue_keys,
                source_id=source.id,
                message=message,
            )
            metadata_cache[source.id] = {"sheets": [], "__missing__": True}
            continue

        if source.type == "local_excel" and source.id not in metadata_cache:
            try:
                metadata_cache[source.id] = read_source_metadata(source)
            except FileNotFoundError:
                message = (
                    f"数据源“{source.id}”的本地路径已失效：{source_path}。"
                    "请到“数据源接入管理”中修复路径后再保存或执行。"
                )
                if config_issues is None:
                    raise ValueError(message)
                _append_config_issue(
                    config_issues,
                    issue_keys,
                    source_id=source.id,
                    message=message,
                )
                metadata_cache[source.id] = {"sheets": [], "__missing__": True}


def _normalize_variables(
    variables: list[VariableTag],
    *,
    source_map: dict[str, DataSource],
    metadata_cache: dict[str, dict[str, object]],
    config_issues: list[FixedRulesConfigIssue] | None = None,
    issue_keys: set[tuple[str, str | None, str | None, str | None, str]] | None = None,
) -> list[VariableTag]:
    """?????????????????"""
    normalized_variables: list[VariableTag] = []
    seen_tags: set[str] = set()

    for variable in variables:
        tag = variable.tag.strip()
        source_id = variable.source_id.strip()
        sheet = variable.sheet.strip()
        variable_kind = (variable.variable_kind or "single").strip()

        if not tag:
            raise ValueError("???????? tag?")
        if tag in seen_tags:
            raise ValueError(f"???????????'{tag}'?")
        if source_id not in source_map:
            raise ValueError(f"?????? '{tag}' ?????????? '{source_id}'?")
        if not sheet:
            raise ValueError(f"?????? '{tag}' ?? Sheet?")

        source = source_map[source_id]
        if source.type != "local_excel":
            raise ValueError(
                f"?????????????? Excel ???????? '{tag}' "
                f"????????? '{source.type}'?"
            )

        available_columns = _load_sheet_columns(
            source=source,
            sheet_name=sheet,
            metadata_cache=metadata_cache,
            variable_tag=tag,
            config_issues=config_issues,
            issue_keys=issue_keys,
        )

        if variable_kind == "composite":
            columns = _normalize_columns(variable.columns or [])
            key_column = (variable.key_column or "").strip()

            if len(columns) < 2:
                raise ValueError(f"???? '{tag}' ?????? 2 ??")
            if not key_column:
                raise ValueError(f"???? '{tag}' ?? key_column?")
            if key_column not in columns:
                raise ValueError(f"???? '{tag}' ? key_column ??????????")

            if available_columns is not None:
                missing_columns = [column for column in columns if column not in available_columns]
                if missing_columns:
                    if config_issues is None:
                        raise ValueError(
                            f"???? '{tag}' ?????????{missing_columns}?"
                        )
                    _append_config_issue(
                        config_issues,
                        issue_keys,
                        source_id=source_id,
                        variable_tag=tag,
                        message=(
                            f"???{tag}?????????{', '.join(missing_columns)}?"
                            "???????????????????????"
                        ),
                    )

            normalized_variables.append(
                VariableTag(
                    tag=tag,
                    source_id=source_id,
                    sheet=sheet,
                    variable_kind="composite",
                    columns=columns,
                    key_column=key_column,
                    expected_type="json",
                )
            )
        elif variable_kind == "single":
            column = (variable.column or "").strip()
            if not column:
                raise ValueError(f"??? '{tag}' ?? column?")
            if available_columns is not None and column not in available_columns:
                if config_issues is None:
                    raise ValueError(
                        f"??? '{tag}' ???? '{column}' ???? Sheet '{sheet}' ??"
                    )
                _append_config_issue(
                    config_issues,
                    issue_keys,
                    source_id=source_id,
                    variable_tag=tag,
                    message=(
                        f"???{tag}??????{column}?????? Sheet ?{sheet}? ??"
                        "???????????????????????"
                    ),
                )

            normalized_variables.append(
                VariableTag(
                    tag=tag,
                    source_id=source_id,
                    sheet=sheet,
                    variable_kind="single",
                    column=column,
                    expected_type=variable.expected_type or "str",
                )
            )
        else:
            raise ValueError(
                f"?????? '{tag}' ??????? variable_kind '{variable_kind}'?"
            )

        seen_tags.add(tag)

    return normalized_variables


def _normalize_rules(
    rules: list[FixedRuleDefinition],
    *,
    group_ids: set[str],
    variable_map: dict[str, VariableTag],
) -> list[FixedRuleDefinition]:
    """???????????????????????"""
    normalized_rules: list[FixedRuleDefinition] = []
    seen_rule_ids: set[str] = set()

    for rule in rules:
        rule_id = rule.rule_id.strip()
        group_id = rule.group_id.strip() or UNGROUPED_GROUP_ID
        rule_name = rule.rule_name.strip()
        target_variable_tag = (rule.target_variable_tag or "").strip()
        rule_type = str(rule.rule_type).strip()
        operator = rule.operator.strip() if rule.operator else ""
        expected_value = rule.expected_value.strip() if rule.expected_value else ""
        reference_variable_tag = (rule.reference_variable_tag or "").strip()
        sequence_direction = (rule.sequence_direction or "").strip()
        sequence_step = (rule.sequence_step or "").strip()
        sequence_start_mode = (rule.sequence_start_mode or "").strip()
        sequence_start_value = (rule.sequence_start_value or "").strip()

        if not rule_id:
            raise ValueError("?????? rule_id?")
        if rule_id in seen_rule_ids:
            raise ValueError(f"???? ID ???'{rule_id}'?")
        if group_id not in group_ids:
            raise ValueError(f"???? '{rule_id}' ?????????? '{group_id}'?")
        if not rule_name:
            raise ValueError(f"???? '{rule_id}' ?? rule_name?")
        if not target_variable_tag:
            raise ValueError(f"???? '{rule_id}' ?? target_variable_tag?")
        if target_variable_tag not in variable_map:
            raise ValueError(
                f"???? '{rule_id}' ????????? '{target_variable_tag}'?"
            )
        if rule_type not in SUPPORTED_FIXED_RULE_TYPES:
            raise ValueError(f"???? '{rule_id}' ??????? rule_type '{rule_type}'?")

        target_variable = variable_map[target_variable_tag]
        variable_kind = target_variable.variable_kind or "single"
        normalized_operator: str | None = None
        normalized_expected_value: str | None = None
        normalized_reference_variable_tag: str | None = None
        normalized_sequence_direction: str | None = None
        normalized_sequence_step: str | None = None
        normalized_sequence_start_mode: str | None = None
        normalized_sequence_start_value: str | None = None
        normalized_composite_config: CompositeRuleConfig | None = None
        normalized_key_check_mode: DualCompositeKeyCheckMode | None = None
        normalized_dual_comparisons: list[DualCompositeComparison] = []

        if variable_kind == "single" and rule_type == "composite_condition_check":
            raise ValueError(
                f"???? '{rule_id}' ???????? '{target_variable_tag}'????????????????"
            )
        if variable_kind == "single" and rule_type == "dual_composite_compare":
            raise ValueError(
                f"规则 '{rule_id}' 引用了单变量 '{target_variable_tag}'，不能保存双组合变量比对。"
            )
        if variable_kind == "composite" and rule_type not in {"composite_condition_check", "dual_composite_compare"}:
            raise ValueError(
                f"???? '{rule_id}' ???????? '{target_variable_tag}'???????????????"
            )

        if rule_type == "fixed_value_compare":
            if operator not in SUPPORTED_FIXED_RULE_OPERATORS:
                raise ValueError(
                    f"???? '{rule_id}' ?????????? '{operator}'?"
                )
            if not expected_value:
                raise ValueError(f"???? '{rule_id}' ?? expected_value?")
            if operator in {"gt", "lt"}:
                try:
                    float(expected_value)
                except ValueError as exc:
                    raise ValueError(
                        f"???? '{rule_id}' ? expected_value ????????"
                    ) from exc
            normalized_operator = operator
            normalized_expected_value = expected_value
        elif rule_type == "cross_table_mapping":
            if not reference_variable_tag:
                raise ValueError(
                    f"规则 '{rule_id}' 缺少 reference_variable_tag。"
                )
            if reference_variable_tag == target_variable_tag:
                raise ValueError(
                    f"规则 '{rule_id}' 的参考变量不能与目标变量相同。"
                )
            if reference_variable_tag not in variable_map:
                raise ValueError(
                    f"规则 '{rule_id}' 引用了不存在的参考变量 '{reference_variable_tag}'。"
                )
            reference_variable = variable_map[reference_variable_tag]
            if (reference_variable.variable_kind or "single") != "single":
                raise ValueError(
                    f"规则 '{rule_id}' 的参考变量 '{reference_variable_tag}' 必须是单个变量。"
                )
            normalized_reference_variable_tag = reference_variable_tag
        elif rule_type == "sequence_order_check":
            if operator or expected_value or reference_variable_tag or rule.composite_config is not None:
                raise ValueError(
                    f"规则 '{rule_id}' 的顺序校验不应包含比较值、参考变量或组合配置。"
                )
            if sequence_direction not in {"asc", "desc"}:
                raise ValueError(
                    f"规则 '{rule_id}' 的顺序方向仅支持 asc 或 desc。"
                )
            if sequence_start_mode not in {"auto", "manual"}:
                raise ValueError(
                    f"规则 '{rule_id}' 的起始值模式仅支持 auto 或 manual。"
                )
            normalized_sequence_direction = sequence_direction
            normalized_sequence_step = _normalize_sequence_numeric(
                sequence_step,
                field_name="step",
                rule_id=rule_id,
                positive_only=True,
            )
            normalized_sequence_start_mode = sequence_start_mode
            if sequence_start_mode == "manual":
                normalized_sequence_start_value = _normalize_sequence_numeric(
                    sequence_start_value,
                    field_name="start_value",
                    rule_id=rule_id,
                )
            elif sequence_start_value:
                raise ValueError(
                    f"规则 '{rule_id}' 在自动起始模式下不应填写 start_value。"
                )
        elif rule_type == "composite_condition_check":
            normalized_composite_config = _normalize_composite_rule_config(
                rule_id=rule_id,
                variable=target_variable,
                composite_config=rule.composite_config,
            )
        elif rule_type == "dual_composite_compare":
            (
                normalized_reference_variable_tag,
                normalized_key_check_mode,
                normalized_dual_comparisons,
            ) = _normalize_dual_composite_rule(
                rule_id=rule_id,
                target_variable=target_variable,
                target_variable_tag=target_variable_tag,
                reference_variable_tag=reference_variable_tag,
                key_check_mode=rule.key_check_mode,
                comparisons=rule.comparisons,
                variable_map=variable_map,
            )

        normalized_rules.append(
            FixedRuleDefinition(
                rule_id=rule_id,
                group_id=group_id,
                rule_name=rule_name,
                target_variable_tag=target_variable_tag,
                rule_type=rule_type,
                operator=normalized_operator,
                expected_value=normalized_expected_value,
                reference_variable_tag=normalized_reference_variable_tag,
                sequence_direction=normalized_sequence_direction,
                sequence_step=normalized_sequence_step,
                sequence_start_mode=normalized_sequence_start_mode,
                sequence_start_value=normalized_sequence_start_value,
                composite_config=normalized_composite_config,
                key_check_mode=normalized_key_check_mode,
                comparisons=normalized_dual_comparisons,
            )
        )
        seen_rule_ids.add(rule_id)

    return normalized_rules


def _normalize_composite_rule_config(
    *,
    rule_id: str,
    variable: VariableTag,
    composite_config: CompositeRuleConfig | None,
) -> CompositeRuleConfig:
    """????????????????"""
    if composite_config is None:
        raise ValueError(f"???? '{rule_id}' ?? composite_config?")

    available_fields = _collect_composite_available_fields(variable)
    global_filters = _normalize_composite_conditions(
        rule_id=rule_id,
        conditions=composite_config.global_filters,
        section_label="??????",
        available_fields=available_fields,
        allowed_operators=SUPPORTED_COMPOSITE_FILTER_OPERATORS,
    )

    normalized_branches: list[CompositeBranch] = []
    seen_branch_ids: set[str] = set()
    if not composite_config.branches:
        raise ValueError(f"???? '{rule_id}' ???????????")

    for branch_index, branch in enumerate(composite_config.branches, start=1):
        branch_id = branch.branch_id.strip()
        if not branch_id:
            raise ValueError(f"???? '{rule_id}' ????? branch_id?")
        if branch_id in seen_branch_ids:
            raise ValueError(f"???? '{rule_id}' ??? ID ???'{branch_id}'?")
        seen_branch_ids.add(branch_id)

        filters = _normalize_composite_conditions(
            rule_id=rule_id,
            conditions=branch.filters,
            section_label=f"?? {branch_index} ?????",
            available_fields=available_fields,
            allowed_operators=SUPPORTED_COMPOSITE_FILTER_OPERATORS,
        )
        assertions = _normalize_composite_conditions(
            rule_id=rule_id,
            conditions=branch.assertions,
            section_label=f"?? {branch_index} ?????",
            available_fields=available_fields,
            allowed_operators=SUPPORTED_COMPOSITE_ASSERTION_OPERATORS,
        )
        if not assertions:
            raise ValueError(f"???? '{rule_id}' ??? {branch_index} ???????????")

        normalized_branches.append(
            CompositeBranch(
                branch_id=branch_id,
                filters=filters,
                assertions=assertions,
            )
        )

    return CompositeRuleConfig(
        global_filters=global_filters,
        branches=normalized_branches,
    )


def _normalize_dual_composite_rule(
    *,
    rule_id: str,
    target_variable: VariableTag,
    target_variable_tag: str,
    reference_variable_tag: str,
    key_check_mode: DualCompositeKeyCheckMode | None,
    comparisons: list[DualCompositeComparison],
    variable_map: dict[str, VariableTag],
) -> tuple[str, DualCompositeKeyCheckMode, list[DualCompositeComparison]]:
    """校验并规范双组合变量比对规则。"""
    if not reference_variable_tag:
        raise ValueError(f"规则 '{rule_id}' 缺少 reference_variable_tag。")
    if reference_variable_tag == target_variable_tag:
        raise ValueError(f"规则 '{rule_id}' 的目标变量不能与基准变量相同。")
    if reference_variable_tag not in variable_map:
        raise ValueError(
            f"规则 '{rule_id}' 引用了不存在的目标组合变量 '{reference_variable_tag}'。"
        )

    reference_variable = variable_map[reference_variable_tag]
    if (reference_variable.variable_kind or "single") != "composite":
        raise ValueError(
            f"规则 '{rule_id}' 的目标变量 '{reference_variable_tag}' 必须是组合变量。"
        )

    normalized_key_check_mode = str(key_check_mode or "baseline_only").strip()
    if normalized_key_check_mode not in SUPPORTED_DUAL_COMPOSITE_KEY_CHECK_MODES:
        raise ValueError(
            f"规则 '{rule_id}' 的 key_check_mode 仅支持 baseline_only 或 bidirectional。"
        )

    if not comparisons:
        raise ValueError(f"规则 '{rule_id}' 至少需要一条字段比对规则。")

    left_fields = _collect_composite_available_fields(target_variable)
    right_fields = _collect_composite_available_fields(reference_variable)
    normalized_comparisons: list[DualCompositeComparison] = []
    seen_comparison_ids: set[str] = set()

    for index, comparison in enumerate(comparisons, start=1):
        comparison_id = comparison.comparison_id.strip()
        left_field = comparison.left_field.strip()
        operator = str(comparison.operator).strip()
        right_field = comparison.right_field.strip()

        if not comparison_id:
            raise ValueError(f"规则 '{rule_id}' 的字段比对 {index} 缺少 comparison_id。")
        if comparison_id in seen_comparison_ids:
            raise ValueError(
                f"规则 '{rule_id}' 的字段比对存在重复 comparison_id '{comparison_id}'。"
            )
        if not left_field:
            raise ValueError(f"规则 '{rule_id}' 的字段比对 {index} 缺少左侧字段。")
        if left_field not in left_fields:
            raise ValueError(
                f"规则 '{rule_id}' 的字段比对 {index} 引用了无效的左侧字段 '{left_field}'。"
            )
        if operator not in SUPPORTED_DUAL_COMPOSITE_OPERATORS:
            raise ValueError(
                f"规则 '{rule_id}' 的字段比对 {index} 使用了不支持的运算符 '{operator}'。"
            )
        if not right_field:
            raise ValueError(f"规则 '{rule_id}' 的字段比对 {index} 缺少右侧字段。")
        if right_field not in right_fields:
            raise ValueError(
                f"规则 '{rule_id}' 的字段比对 {index} 引用了无效的右侧字段 '{right_field}'。"
            )

        normalized_comparisons.append(
            DualCompositeComparison(
                comparison_id=comparison_id,
                left_field=left_field,
                operator=operator,
                right_field=right_field,
            )
        )
        seen_comparison_ids.add(comparison_id)

    return (
        reference_variable_tag,
        normalized_key_check_mode,
        normalized_comparisons,
    )


def _normalize_composite_conditions(
    *,
    rule_id: str,
    conditions: list[CompositeCondition],
    section_label: str,
    available_fields: set[str],
    allowed_operators: set[str],
) -> list[CompositeCondition]:
    """????????????????"""
    normalized_conditions: list[CompositeCondition] = []
    seen_condition_ids: set[str] = set()

    for condition in conditions:
        condition_id = condition.condition_id.strip()
        field = condition.field.strip()
        operator = str(condition.operator).strip()
        value_source = condition.value_source
        expected_value = condition.expected_value.strip() if condition.expected_value else ""
        expected_field = condition.expected_field.strip() if condition.expected_field else ""

        if not condition_id:
            raise ValueError(f"???? '{rule_id}' ?{section_label}???? condition_id ????")
        if condition_id in seen_condition_ids:
            raise ValueError(
                f"???? '{rule_id}' ?{section_label}???? condition_id?'{condition_id}'?"
            )
        if not field:
            raise ValueError(f"???? '{rule_id}' ?{section_label}??????????")
        if field not in available_fields:
            raise ValueError(
                f"???? '{rule_id}' ?{section_label}????????? '{field}'?"
            )
        if operator not in allowed_operators:
            raise ValueError(
                f"???? '{rule_id}' ?{section_label}?????????? '{operator}'?"
            )

        normalized_value_source: str | None = None
        normalized_expected_value: str | None = None
        normalized_expected_field: str | None = None

        if operator in COMPARE_STYLE_OPERATORS:
            normalized_value_source = value_source or "literal"
            if normalized_value_source == "literal":
                if not expected_value:
                    raise ValueError(f"???? '{rule_id}' ?{section_label}??????")
                if operator in {"gt", "lt"}:
                    try:
                        float(expected_value)
                    except ValueError as exc:
                        raise ValueError(
                            f"???? '{rule_id}' ?{section_label}? '{operator}' ????????????"
                        ) from exc
                normalized_expected_value = expected_value
            elif normalized_value_source == "field":
                if not expected_field:
                    raise ValueError(f"???? '{rule_id}' ?{section_label}?????????")
                if expected_field not in available_fields:
                    raise ValueError(
                        f"???? '{rule_id}' ?{section_label}??????????? '{expected_field}'?"
                    )
                normalized_expected_field = expected_field
            else:
                raise ValueError(
                    f"???? '{rule_id}' ?{section_label}??????? value_source '{value_source}'?"
                )
        elif operator == "not_null":
            normalized_value_source = None
            if value_source or expected_value or expected_field:
                raise ValueError(
                    f"???? '{rule_id}' ?{section_label}? 'not_null' ????????????"
                )
        elif operator in SET_STYLE_OPERATORS:
            if value_source or expected_value or expected_field:
                raise ValueError(
                    f"???? '{rule_id}' ?{section_label}? '{operator}' ????????????"
                )
        else:
            raise ValueError(
                f"???? '{rule_id}' ?{section_label}?????????? '{operator}'?"
            )

        normalized_conditions.append(
            CompositeCondition(
                condition_id=condition_id,
                field=field,
                operator=operator,
                value_source=normalized_value_source,
                expected_value=normalized_expected_value,
                expected_field=normalized_expected_field,
            )
        )
        seen_condition_ids.add(condition_id)

    return normalized_conditions


def _collect_composite_available_fields(variable: VariableTag) -> set[str]:
    """??????????????????"""
    available_fields = {COMPOSITE_KEY_FIELD}
    key_column = (variable.key_column or "").strip()
    available_fields.update(
        column.strip()
        for column in (variable.columns or [])
        if column and column.strip() and column.strip() != key_column
    )
    return available_fields


def _normalize_local_source_path(
    source_id: str,
    raw_path: str,
    source_type: str,
) -> Path:
    """?????????????"""
    if not raw_path.strip():
        raise ValueError(f"数据源“{source_id}”缺少本地文件路径。")

    normalized_path = Path(raw_path).expanduser().resolve(strict=False)
    allowed_suffixes = SUPPORTED_LOCAL_SOURCE_SUFFIXES.get(source_type)
    if allowed_suffixes and normalized_path.suffix.lower() not in allowed_suffixes:
        suffix_text = " / ".join(sorted(allowed_suffixes))
        raise ValueError(
            f"数据源“{source_id}”的文件格式不正确，当前仅支持 {suffix_text}。"
        )
    return normalized_path


def _normalize_columns(columns: list[str]) -> list[str]:
    """?????????"""
    normalized_columns: list[str] = []
    seen_columns: set[str] = set()
    for column in columns:
        normalized_column = column.strip()
        if not normalized_column or normalized_column in seen_columns:
            continue
        normalized_columns.append(normalized_column)
        seen_columns.add(normalized_column)
    return normalized_columns


def _load_sheet_columns(
    *,
    source: DataSource,
    sheet_name: str,
    metadata_cache: dict[str, dict[str, object]],
    variable_tag: str | None = None,
    config_issues: list[FixedRulesConfigIssue] | None = None,
    issue_keys: set[tuple[str, str | None, str | None, str | None, str]] | None = None,
) -> list[str] | None:
    """????????? Sheet ???????????"""
    metadata = metadata_cache.get(source.id)
    if metadata is None:
        try:
            metadata = read_source_metadata(source)
        except FileNotFoundError:
            if config_issues is None:
                raise
            _append_config_issue(
                config_issues,
                issue_keys,
                source_id=source.id,
                variable_tag=variable_tag,
                message=(
                    f"数据源“{source.id}”的本地路径已失效：{source.pathOrUrl or source.path or ""}。"
                    "请到“数据源接入管理”中修复路径后再保存或执行。"
                ),
            )
            metadata_cache[source.id] = {"sheets": [], "__missing__": True}
            return None
        metadata_cache[source.id] = metadata
    elif metadata.get("__missing__"):
        return None

    for sheet in metadata["sheets"]:
        if sheet["name"] == sheet_name:
            return list(sheet["columns"])

    if config_issues is not None:
        _append_config_issue(
            config_issues,
            issue_keys,
            source_id=source.id,
            variable_tag=variable_tag,
            message=(
                f"变量“{variable_tag or sheet_name}”引用的 Sheet “{sheet_name}”已不存在。"
                "请到“变量池构建”中重新选择 Sheet 后再保存或执行。"
            ),
        )
        return None

    raise ValueError(f"固定规则变量引用的 Sheet '{sheet_name}' 不存在。")


def _append_config_issue(
    issues: list[FixedRulesConfigIssue],
    issue_keys: set[tuple[str, str | None, str | None, str | None, str]] | None,
    *,
    message: str,
    level: str = "warning",
    source_id: str | None = None,
    variable_tag: str | None = None,
    rule_id: str | None = None,
) -> None:
    """?????????????????"""
    issue_key = (level, source_id, variable_tag, rule_id, message)
    if issue_keys is not None and issue_key in issue_keys:
        return

    issues.append(
        FixedRulesConfigIssue(
            level=level,
            source_id=source_id,
            variable_tag=variable_tag,
            rule_id=rule_id,
            message=message,
        )
    )
    if issue_keys is not None:
        issue_keys.add(issue_key)


def _collect_working_copies(sources: list[DataSource]) -> list[Path]:
    """??????? SVN ??????????"""
    working_copies: list[Path] = []
    seen_paths: set[str] = set()

    for source in sources:
        raw_locator = (source.path or source.pathOrUrl or "").strip()
        if not raw_locator or source.type == "feishu":
            continue

        source_path = Path(raw_locator).expanduser().resolve(strict=False)
        working_copy = source_path if source.type == "svn" else source_path.parent
        normalized_key = str(working_copy).lower()
        if normalized_key in seen_paths:
            continue
        seen_paths.add(normalized_key)
        working_copies.append(working_copy)

    return working_copies


def _get_ordered_rules(
    config: FixedRulesConfig,
    *,
    selected_rule_ids: list[str] | None = None,
) -> list[FixedRuleDefinition]:
    """?????????????????????"""
    group_order = {group.group_id: index for index, group in enumerate(config.groups)}
    rule_order = {rule.rule_id: index for index, rule in enumerate(config.rules)}
    ordered_rules = sorted(
        config.rules,
        key=lambda rule: (
            group_order.get(rule.group_id, len(group_order)),
            rule_order[rule.rule_id],
        ),
    )
    if selected_rule_ids is None:
        return ordered_rules

    selected_rule_id_set = {
        rule_id.strip()
        for rule_id in selected_rule_ids
        if isinstance(rule_id, str) and rule_id.strip()
    }
    if not selected_rule_id_set:
        return []

    return [
        rule for rule in ordered_rules if rule.rule_id.strip() in selected_rule_id_set
    ]


def _build_default_group() -> FixedRuleGroup:
    """????????"""
    return FixedRuleGroup(
        group_id=UNGROUPED_GROUP_ID,
        group_name=UNGROUPED_GROUP_NAME,
        builtin=True,
    )


def _build_source_id_from_path(source_path: Path, seen_ids: set[str]) -> str:
    """?????????????? source_id?"""
    raw_stem = re.sub(r"[^0-9A-Za-z_-]+", "-", source_path.stem).strip("-").lower()
    base_id = raw_stem or "source"
    if base_id not in seen_ids:
        return base_id

    index = 2
    while f"{base_id}-{index}" in seen_ids:
        index += 1
    return f"{base_id}-{index}"


def _build_single_variable_tag(
    *,
    source_id: str,
    sheet: str,
    column: str,
    seen_tags: set[str],
) -> str:
    """???????????????"""
    base_tag = f"[{source_id}-{sheet.strip() or 'sheet'}-{column.strip() or 'column'}]"
    if base_tag not in seen_tags:
        return base_tag

    index = 2
    while f"{base_tag[:-1]}-{index}]" in seen_tags:
        index += 1
    return f"{base_tag[:-1]}-{index}]"


def _build_fixed_rule_params(
    rule: FixedRuleDefinition,
    target_variable: VariableTag,
) -> dict[str, object]:
    """???????????????? params?"""
    if rule.rule_type == "composite_condition_check":
        return {
            "target_tag": target_variable.tag,
            "rule_name": rule.rule_name,
            "composite_config": rule.composite_config.model_dump(mode="json", exclude_none=True)
            if rule.composite_config
            else None,
        }

    if rule.rule_type == "dual_composite_compare":
        return {
            "target_tag": target_variable.tag,
            "reference_tag": rule.reference_variable_tag,
            "key_check_mode": rule.key_check_mode,
            "comparisons": [
                comparison.model_dump(mode="json", exclude_none=True)
                for comparison in rule.comparisons
            ],
            "rule_name": rule.rule_name,
        }

    location = f"{target_variable.sheet} -> {target_variable.column}"

    if rule.rule_type == "fixed_value_compare":
        return {
            "target_tag": target_variable.tag,
            "operator": rule.operator,
            "expected_value": rule.expected_value,
            "rule_name": rule.rule_name,
            "location": location,
        }

    if rule.rule_type == "cross_table_mapping":
        return {
            "dict_tag": rule.reference_variable_tag,
            "target_tag": target_variable.tag,
            "rule_name": rule.rule_name,
            "location": location,
        }

    if rule.rule_type == "sequence_order_check":
        return {
            "target_tag": target_variable.tag,
            "direction": rule.sequence_direction,
            "step": rule.sequence_step,
            "start_mode": rule.sequence_start_mode,
            "start_value": rule.sequence_start_value,
            "rule_name": rule.rule_name,
            "location": location,
        }

    return {
        "target_tags": [target_variable.tag],
        "rule_name": rule.rule_name,
        "location": location,
    }

"""固定规则模块的配置持久化、迁移、校验与执行编排。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app.api.execute_api import execute_engine
from backend.app.api.fixed_rules_schemas import (
    FixedRuleBinding,
    FixedRuleDefinition,
    FixedRuleGroup,
    FixedRulesConfig,
    UNGROUPED_GROUP_ID,
    UNGROUPED_GROUP_NAME,
)
from backend.app.api.schemas import DataSource, TaskTree, ValidationRule, VariableTag
from backend.app.loaders.local_reader import read_source_metadata
from backend.app.loaders.svn_manager import update_svn_working_copy
from backend.config import settings


FIXED_RULES_SOURCE_PREFIX = "fixed_source"
FIXED_RULES_CONFIG_VERSION = 3
SUPPORTED_FIXED_RULE_TYPES = {"fixed_value_compare", "not_null", "unique"}
SUPPORTED_FIXED_RULE_OPERATORS = {"eq", "ne", "gt", "lt"}
SUPPORTED_FIXED_RULE_SUFFIXES = {".xls", ".xlsx"}
LEGACY_FIXED_RULE_KEYS = {"file_path", "sheet", "columns", "svn_enabled"}


def build_default_fixed_rules_config() -> FixedRulesConfig:
    """返回未配置状态下的固定规则默认结构。"""
    return FixedRulesConfig(
        version=FIXED_RULES_CONFIG_VERSION,
        configured=False,
        groups=[_build_default_group()],
        rules=[],
    )


def load_fixed_rules_config() -> FixedRulesConfig:
    """读取固定规则配置文件，不存在时返回默认空结构。"""
    config_path = settings.fixed_rules_config_path
    if not config_path.exists():
        return build_default_fixed_rules_config()

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"固定规则配置文件已损坏，无法解析 JSON：{exc}") from exc

    raw_config = _parse_fixed_rules_payload(payload)
    if not raw_config.configured and not raw_config.rules:
        return build_default_fixed_rules_config()
    return validate_and_normalize_fixed_rules_config(raw_config)


def save_fixed_rules_config(config: FixedRulesConfig) -> FixedRulesConfig:
    """校验并持久化固定规则配置。"""
    normalized_config = validate_and_normalize_fixed_rules_config(config)
    config_path = settings.fixed_rules_config_path
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            normalized_config.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return normalized_config


def execute_saved_fixed_rules() -> dict[str, object]:
    """读取已保存配置并执行固定规则。"""
    config = load_fixed_rules_config()
    if not config.rules:
        raise ValueError("固定规则模块尚未配置任何规则，请先保存规则后再执行。")
    return execute_engine(build_fixed_rules_task_tree(config))


def run_saved_fixed_rules_svn_update() -> dict[str, object]:
    """对当前所有已配置规则路径执行一次 SVN 更新。"""
    config = load_fixed_rules_config()
    if not config.rules:
        raise ValueError("固定规则模块尚未配置任何规则路径，无法执行 SVN 更新。")

    working_copies = _collect_working_copies(config.rules)
    if not working_copies:
        raise ValueError("当前没有可用于 SVN 更新的固定路径。")

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


def build_fixed_rules_task_tree(config: FixedRulesConfig) -> TaskTree:
    """把固定规则配置转换为可复用既有引擎的临时 TaskTree。"""
    sources: list[DataSource] = []
    variables: list[VariableTag] = []
    task_rules: list[ValidationRule] = []

    source_ids_by_key: dict[tuple[str, str], str] = {}
    variable_tags_by_key: dict[tuple[str, str], str] = {}

    for rule in _get_ordered_rules(config):
        source_key = (rule.binding.file_path, rule.binding.sheet)
        source_id = source_ids_by_key.get(source_key)
        if source_id is None:
            source_id = _build_fixed_source_id(len(source_ids_by_key) + 1)
            source_ids_by_key[source_key] = source_id
            sources.append(
                DataSource(
                    id=source_id,
                    type="local_excel",
                    path=rule.binding.file_path,
                    pathOrUrl=rule.binding.file_path,
                )
            )

        variable_key = (source_id, rule.binding.column)
        target_tag = variable_tags_by_key.get(variable_key)
        if target_tag is None:
            target_tag = _build_fixed_variable_tag(
                source_id=source_id,
                sheet=rule.binding.sheet,
                column=rule.binding.column,
            )
            variable_tags_by_key[variable_key] = target_tag
            variables.append(
                VariableTag(
                    tag=target_tag,
                    source_id=source_id,
                    sheet=rule.binding.sheet,
                    variable_kind="single",
                    column=rule.binding.column,
                )
            )

        task_rules.append(
            ValidationRule(
                rule_id=rule.rule_id,
                rule_type=rule.rule_type,
                params=_build_fixed_rule_params(rule, target_tag),
            )
        )

    return TaskTree(sources=sources, variables=variables, rules=task_rules)


def validate_and_normalize_fixed_rules_config(
    config: FixedRulesConfig,
) -> FixedRulesConfig:
    """校验并规范化固定规则配置。"""
    groups = _normalize_groups(config.groups)
    group_ids = {group.group_id for group in groups}
    metadata_cache: dict[str, dict[str, object]] = {}
    normalized_rules = _normalize_rules(
        config.rules,
        group_ids=group_ids,
        metadata_cache=metadata_cache,
    )

    return FixedRulesConfig(
        version=FIXED_RULES_CONFIG_VERSION,
        configured=True,
        groups=groups,
        rules=normalized_rules,
    )


def _parse_fixed_rules_payload(payload: object) -> FixedRulesConfig:
    """兼容解析固定规则配置的旧版与新版 JSON 结构。"""
    if not isinstance(payload, dict):
        raise ValueError("固定规则配置文件内容格式不正确，根节点必须是对象。")

    if LEGACY_FIXED_RULE_KEYS.intersection(payload):
        return _migrate_legacy_payload(payload)

    if _requires_v2_migration(payload):
        return _migrate_v2_payload(payload)

    return FixedRulesConfig.model_validate(payload)


def _requires_v2_migration(payload: dict[str, object]) -> bool:
    """识别旧版 version=2 固定规则配置，补上显式 rule_type。"""
    if int(payload.get("version") or 0) == 2:
        return True

    raw_rules = payload.get("rules")
    if not isinstance(raw_rules, list):
        return False

    return any(
        isinstance(raw_rule, dict) and "rule_type" not in raw_rule
        for raw_rule in raw_rules
    )


def _migrate_legacy_payload(payload: dict[str, object]) -> FixedRulesConfig:
    """把旧版“全局单文件配置”迁移为新版“规则级文件绑定”结构。"""
    file_path = str(payload.get("file_path") or "").strip()
    sheet = str(payload.get("sheet") or "").strip()
    raw_rules = payload.get("rules") or []

    if not isinstance(raw_rules, list):
        raise ValueError("旧版固定规则配置中的 rules 字段格式不正确。")

    migrated_rules: list[dict[str, object]] = []
    for raw_rule in raw_rules:
        if not isinstance(raw_rule, dict):
            raise ValueError("旧版固定规则配置中的单条规则格式不正确。")

        column = str(raw_rule.get("column") or "").strip()
        if not column:
            raise ValueError("旧版固定规则配置缺少规则列，无法自动迁移到新版结构。")

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
                "rule_type": "fixed_value_compare",
                "operator": raw_rule.get("operator"),
                "expected_value": raw_rule.get("expected_value", ""),
            }
        )

    migrated_payload = {
        "version": FIXED_RULES_CONFIG_VERSION,
        "configured": bool(payload.get("configured", False)),
        "groups": payload.get("groups") or [],
        "rules": migrated_rules,
    }
    return FixedRulesConfig.model_validate(migrated_payload)


def _migrate_v2_payload(payload: dict[str, object]) -> FixedRulesConfig:
    """把旧版比较型固定规则配置补齐为显式 rule_type 结构。"""
    raw_rules = payload.get("rules") or []
    if not isinstance(raw_rules, list):
        raise ValueError("旧版固定规则配置中的 rules 字段格式不正确。")

    migrated_rules: list[dict[str, object]] = []
    for raw_rule in raw_rules:
        if not isinstance(raw_rule, dict):
            raise ValueError("旧版固定规则配置中的单条规则格式不正确。")

        migrated_rules.append(
            {
                "rule_id": raw_rule.get("rule_id", ""),
                "group_id": raw_rule.get("group_id") or UNGROUPED_GROUP_ID,
                "rule_name": raw_rule.get("rule_name", ""),
                "binding": raw_rule.get("binding") or {},
                "rule_type": raw_rule.get("rule_type") or "fixed_value_compare",
                "operator": raw_rule.get("operator"),
                "expected_value": raw_rule.get("expected_value"),
            }
        )

    migrated_payload = {
        "version": FIXED_RULES_CONFIG_VERSION,
        "configured": bool(payload.get("configured", False)),
        "groups": payload.get("groups") or [],
        "rules": migrated_rules,
    }
    return FixedRulesConfig.model_validate(migrated_payload)


def _collect_working_copies(rules: list[FixedRuleDefinition]) -> list[Path]:
    """收集所有规则绑定路径对应的去重工作副本目录。"""
    working_copies: list[Path] = []
    seen_paths: set[str] = set()

    for rule in rules:
        working_copy = Path(rule.binding.file_path).parent
        normalized_key = str(working_copy).lower()
        if normalized_key in seen_paths:
            continue
        seen_paths.add(normalized_key)
        working_copies.append(working_copy)

    return working_copies


def _get_ordered_rules(config: FixedRulesConfig) -> list[FixedRuleDefinition]:
    """按规则组顺序和规则定义顺序输出可执行规则。"""
    group_order = {group.group_id: index for index, group in enumerate(config.groups)}
    rule_order = {rule.rule_id: index for index, rule in enumerate(config.rules)}
    return sorted(
        config.rules,
        key=lambda rule: (
            group_order.get(rule.group_id, len(group_order)),
            rule_order[rule.rule_id],
        ),
    )


def _normalize_groups(groups: list[FixedRuleGroup]) -> list[FixedRuleGroup]:
    """标准化规则组列表，并确保默认组存在且不可变。"""
    normalized_groups: list[FixedRuleGroup] = [_build_default_group()]
    seen_group_ids = {UNGROUPED_GROUP_ID}

    for group in groups:
        group_id = group.group_id.strip()
        group_name = group.group_name.strip()

        if not group_id or not group_name:
            raise ValueError("规则组缺少 group_id 或 group_name。")
        if group_id == UNGROUPED_GROUP_ID:
            continue
        if group_id in seen_group_ids:
            raise ValueError(f"规则组 ID 重复：'{group_id}'。")

        normalized_groups.append(
            FixedRuleGroup(
                group_id=group_id,
                group_name=group_name,
                builtin=False,
            )
        )
        seen_group_ids.add(group_id)

    return normalized_groups


def _normalize_rules(
    rules: list[FixedRuleDefinition],
    *,
    group_ids: set[str],
    metadata_cache: dict[str, dict[str, object]],
) -> list[FixedRuleDefinition]:
    """校验规则定义并输出规范化结构。"""
    normalized_rules: list[FixedRuleDefinition] = []
    seen_rule_ids: set[str] = set()

    for rule in rules:
        rule_id = rule.rule_id.strip()
        group_id = rule.group_id.strip() or UNGROUPED_GROUP_ID
        rule_name = rule.rule_name.strip()
        rule_type = str(rule.rule_type).strip()
        operator = rule.operator.strip() if rule.operator else ""
        expected_value = rule.expected_value.strip() if rule.expected_value else ""

        if not rule_id:
            raise ValueError("固定规则缺少 rule_id。")
        if rule_id in seen_rule_ids:
            raise ValueError(f"固定规则 ID 重复：'{rule_id}'。")
        if group_id not in group_ids:
            raise ValueError(f"固定规则 '{rule_id}' 引用了不存在的规则组 '{group_id}'。")
        if not rule_name:
            raise ValueError(f"固定规则 '{rule_id}' 缺少 rule_name。")
        if rule_type not in SUPPORTED_FIXED_RULE_TYPES:
            raise ValueError(f"固定规则 '{rule_id}' 使用了不支持的规则类型 '{rule_type}'。")

        normalized_operator: str | None = None
        normalized_expected_value: str | None = None
        if rule_type == "fixed_value_compare":
            if operator not in SUPPORTED_FIXED_RULE_OPERATORS:
                raise ValueError(f"固定规则 '{rule_id}' 使用了不支持的比较符 '{operator}'。")
            if not expected_value:
                raise ValueError(f"固定规则 '{rule_id}' 缺少 expected_value。")
            if operator in {"gt", "lt"}:
                try:
                    float(expected_value)
                except ValueError as exc:
                    raise ValueError(
                        f"固定规则 '{rule_id}' 的 expected_value 必须是合法数值。"
                    ) from exc
            normalized_operator = operator
            normalized_expected_value = expected_value

        binding = _normalize_rule_binding(
            rule.rule_id,
            rule.binding,
            metadata_cache=metadata_cache,
        )
        normalized_rules.append(
            FixedRuleDefinition(
                rule_id=rule_id,
                group_id=group_id,
                rule_name=rule_name,
                binding=binding,
                rule_type=rule_type,
                operator=normalized_operator,
                expected_value=normalized_expected_value,
            )
        )
        seen_rule_ids.add(rule_id)

    return normalized_rules


def _normalize_rule_binding(
    rule_id: str,
    binding: FixedRuleBinding,
    *,
    metadata_cache: dict[str, dict[str, object]],
) -> FixedRuleBinding:
    """校验单条规则的文件绑定信息。"""
    file_path = binding.file_path.strip()
    sheet = binding.sheet.strip()
    column = binding.column.strip()

    if not file_path:
        raise ValueError(f"固定规则 '{rule_id}' 缺少文件路径。")
    if not sheet:
        raise ValueError(f"固定规则 '{rule_id}' 缺少 Sheet。")
    if not column:
        raise ValueError(f"固定规则 '{rule_id}' 缺少目标列。")

    source_path = _resolve_excel_source_path(file_path)
    available_columns = _load_sheet_columns(str(source_path), sheet, metadata_cache)
    if column not in available_columns:
        raise ValueError(
            f"固定规则 '{rule_id}' 引用的列 '{column}' 不存在于文件 "
            f"'{source_path.name}' 的 Sheet '{sheet}' 中。"
        )

    return FixedRuleBinding(
        file_path=str(source_path),
        sheet=sheet,
        column=column,
    )


def _resolve_excel_source_path(raw_path: str) -> Path:
    """解析并校验规则绑定的本地 Excel 路径。"""
    source_path = Path(raw_path).expanduser()
    if source_path.suffix.lower() not in SUPPORTED_FIXED_RULE_SUFFIXES:
        raise ValueError("固定规则模块当前仅支持本地 Excel 文件（.xls / .xlsx）。")
    return source_path.resolve(strict=False)


def _load_sheet_columns(
    file_path: str,
    sheet_name: str,
    metadata_cache: dict[str, dict[str, object]],
) -> list[str]:
    """读取指定文件中目标 Sheet 的列集合，并做缓存复用。"""
    metadata = metadata_cache.get(file_path)
    if metadata is None:
        metadata = read_source_metadata(
            DataSource(
                id=f"{FIXED_RULES_SOURCE_PREFIX}_meta",
                type="local_excel",
                path=file_path,
                pathOrUrl=file_path,
            )
        )
        metadata_cache[file_path] = metadata

    for sheet in metadata["sheets"]:
        if sheet["name"] == sheet_name:
            return list(sheet["columns"])
    raise ValueError(f"固定规则引用的 Sheet '{sheet_name}' 不存在。")


def _build_default_group() -> FixedRuleGroup:
    """构建内置默认组。"""
    return FixedRuleGroup(
        group_id=UNGROUPED_GROUP_ID,
        group_name=UNGROUPED_GROUP_NAME,
        builtin=True,
    )


def _build_fixed_source_id(index: int) -> str:
    """生成固定规则执行时的临时数据源 ID。"""
    return f"{FIXED_RULES_SOURCE_PREFIX}_{index}"


def _build_fixed_variable_tag(*, source_id: str, sheet: str, column: str) -> str:
    """生成固定规则执行时使用的内部变量标签。"""
    return f"[fixed-{source_id}-{sheet}-{column}]"


def _build_fixed_rule_params(
    rule: FixedRuleDefinition,
    target_tag: str,
) -> dict[str, object]:
    """把固定规则定义转换为统一执行入口可消费的规则参数。"""
    location = f"{rule.binding.sheet} -> {rule.binding.column}"

    if rule.rule_type == "fixed_value_compare":
        return {
            "target_tag": target_tag,
            "operator": rule.operator,
            "expected_value": rule.expected_value,
            "rule_name": rule.rule_name,
            "location": location,
        }

    return {
        "target_tags": [target_tag],
        "rule_name": rule.rule_name,
        "location": location,
    }

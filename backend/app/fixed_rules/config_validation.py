"""Fixed-rules config validation and normalization."""

from __future__ import annotations

import re
from pathlib import Path

from backend.app.api.fixed_rules_schemas import (
    CompositeBranch,
    CompositeCondition,
    CompositeRuleConfig,
    DualCompositeComparison,
    DualCompositeKeyCheckMode,
    FixedRuleDefinition,
    FixedRuleGroup,
    FixedRulesConfig,
    FixedRulesConfigIssue,
    MultiCompositeMappingConfig,
    MultiCompositeMappingExclusionRange,
    MultiCompositeMappingFilter,
    MultiCompositeMappingNode,
    MultiCompositePipelineConfig,
    MultiCompositePipelineNode,
    UNGROUPED_GROUP_ID,
    UNGROUPED_GROUP_NAME,
)
from backend.app.api.schemas import DataSource, VariableTag
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
    SUPPORTED_MULTI_PIPELINE_ASSERTION_OPERATORS,
    _build_default_group,
    _normalize_columns,
    _normalize_local_path_replacement_presets,
    _normalize_local_source_path,
    _normalize_selected_local_path_replacement_preset,
    _normalize_selected_svn_path_replacement_preset,
    _normalize_svn_path_replacement_presets,
    _resolve_identifier_against_available,
    _resolve_identifiers_against_available,
)
from backend.app.fixed_rules.config_migration import _ensure_v4_config
from backend.app.loaders.local_reader import read_source_metadata
from backend.app.rules.domain.operators import (
    normalize_expected_value_mode,
    parse_expected_value_set,
)

def _normalize_expected_value_mode_for_operator(
    *,
    operator: str,
    expected_value: str,
    expected_value_mode: str | None,
    context: str,
) -> str | None:
    """校验固定值模式；仅 eq/ne 支持规则集。"""
    try:
        normalized_mode = normalize_expected_value_mode(expected_value_mode)
    except ValueError as exc:
        raise ValueError(f"{context} 的 expected_value_mode 仅支持 single 或 set。") from exc

    if normalized_mode == "set":
        if operator not in {"eq", "ne"}:
            raise ValueError(f"{context} 只有等于/不等于支持规则集比较值。")
        try:
            parse_expected_value_set(expected_value)
        except ValueError as exc:
            raise ValueError(f"{context} 的规则集至少需要一个固定值。") from exc

    return "set" if normalized_mode == "set" else None


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
    allow_legacy_mapping_config: bool = False,
    allow_unsupported_csv: bool | None = None,
) -> tuple[FixedRulesConfig, list[FixedRulesConfigIssue]]:
    """???????????????????????????"""
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


def _normalize_sources(
    sources: list[DataSource],
    *,
    allow_unsupported_csv: bool = False,
) -> list[DataSource]:
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
            if source_type == "local_csv" and not allow_unsupported_csv:
                raise ValueError(
                    f"CSV 数据源“{source_id}”已不再支持，请删除后改用 Excel 或 SVN Excel。"
                )
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
                raise ValueError(f"数据源 '{source_id}' 缺少 SVN 路径或 URL。")
            from backend.app.loaders.svn_cache import is_remote_svn_locator

            if is_remote_svn_locator(raw_locator):
                # 远端 URL 保持原样，不能 Path.resolve() 污染。
                normalized_sources.append(
                    DataSource(
                        id=source_id,
                        type=source_type,
                        pathOrUrl=raw_locator,
                        token=token or None,
                    )
                )
            else:
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
        if source.type == "local_csv":
            message = f"CSV 数据源“{source.id}”已不再支持，请删除后改用 Excel 或 SVN Excel。"
            if config_issues is None:
                raise ValueError(message)
            _append_config_issue(
                config_issues,
                issue_keys,
                source_id=source.id,
                message=message,
            )
            metadata_cache[source.id] = {"sheets": [], "__unsupported_csv__": True}
            continue

        if source.type != "local_excel":
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
        sheet = variable.sheet or ""
        variable_kind = (variable.variable_kind or "single").strip()

        if not tag:
            raise ValueError("???????? tag?")
        if tag in seen_tags:
            raise ValueError(f"???????????'{tag}'?")
        if source_id not in source_map:
            raise ValueError(f"?????? '{tag}' ?????????? '{source_id}'?")
        if not sheet.strip():
            raise ValueError(f"?????? '{tag}' ?? Sheet?")

        source = source_map[source_id]
        source_supports_variables = source.type in {"local_excel", "svn"}
        if not source_supports_variables:
            message = (
                f"项目校验变量仅支持 Excel 数据源，变量“{tag}”引用的数据源类型为“{source.type}”。"
            )
            if config_issues is None:
                raise ValueError(message)
            _append_config_issue(
                config_issues,
                issue_keys,
                source_id=source_id,
                variable_tag=tag,
                message=message,
            )

        resolved_sheet = sheet
        available_columns: list[str] | None = None
        sheet_details = (
            _load_sheet_columns(
                source=source,
                sheet_name=sheet,
                metadata_cache=metadata_cache,
                variable_tag=tag,
                config_issues=config_issues,
                issue_keys=issue_keys,
            )
            if source_supports_variables
            else None
        )
        if sheet_details is not None:
            resolved_sheet, available_columns = sheet_details

        if variable_kind == "composite":
            columns = _normalize_columns(variable.columns or [])
            key_column = variable.key_column or ""

            if len(columns) < 2:
                raise ValueError(f"???? '{tag}' ?????? 2 ??")
            if not key_column.strip():
                raise ValueError(f"???? '{tag}' ?? key_column?")
            resolved_columns = columns
            resolved_key_column = key_column

            if available_columns is not None:
                try:
                    resolved_columns = _resolve_identifiers_against_available(
                        columns,
                        available_columns,
                        identifier_label="列名",
                        context=f"变量“{tag}”",
                    )
                    resolved_key_column = _resolve_identifier_against_available(
                        key_column,
                        available_columns,
                        identifier_label="key 列",
                        context=f"变量“{tag}”",
                    )
                except ValueError as exc:
                    if config_issues is None:
                        raise
                    _append_config_issue(
                        config_issues,
                        issue_keys,
                        source_id=source_id,
                        variable_tag=tag,
                        message=f"{exc}???????????????????????",
                    )
                if resolved_key_column not in resolved_columns:
                    if config_issues is None:
                        raise ValueError(f"???? '{tag}' ? key_column ??????????")
                    _append_config_issue(
                        config_issues,
                        issue_keys,
                        source_id=source_id,
                        variable_tag=tag,
                        message=(
                            f"变量“{tag}”的 key 列“{resolved_key_column}”未包含在关联列中。"
                            "请到变量配置中修复后再保存或执行。"
                        ),
                    )

            normalized_variables.append(
                VariableTag(
                    tag=tag,
                    source_id=source_id,
                    sheet=resolved_sheet,
                    variable_kind="composite",
                    columns=resolved_columns,
                    key_column=resolved_key_column,
                    append_index_to_key=variable.append_index_to_key,
                    expected_type="json",
                )
            )
        elif variable_kind == "single":
            column = variable.column or ""
            if not column.strip():
                raise ValueError(f"??? '{tag}' ?? column?")
            resolved_column = column
            if available_columns is not None:
                try:
                    resolved_column = _resolve_identifier_against_available(
                        column,
                        available_columns,
                        identifier_label="列名",
                        context=f"变量“{tag}”",
                    )
                except ValueError as exc:
                    if config_issues is None:
                        raise
                    _append_config_issue(
                        config_issues,
                        issue_keys,
                        source_id=source_id,
                        variable_tag=tag,
                        message=f"{exc}???????????????????????",
                    )

            normalized_variables.append(
                VariableTag(
                    tag=tag,
                    source_id=source_id,
                    sheet=resolved_sheet,
                    variable_kind="single",
                    column=resolved_column,
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
    allow_legacy_mapping_config: bool = False,
    config_issues: list[FixedRulesConfigIssue] | None = None,
    issue_keys: set[tuple[str, str | None, str | None, str | None, str]] | None = None,
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
        expected_value_mode = rule.expected_value_mode
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
        if rule_type not in SUPPORTED_FIXED_RULE_TYPES:
            raise ValueError(f"???? '{rule_id}' ??????? rule_type '{rule_type}'?")

        if not rule_name:
            raise ValueError(f"???? '{rule_id}' ?? rule_name?")

        is_node_driven_rule = rule_type in {
            "multi_composite_pipeline_check",
            "multi_composite_mapping_check",
        }
        target_variable = variable_map.get(target_variable_tag)
        if not is_node_driven_rule:
            if not target_variable_tag:
                raise ValueError(f"???? '{rule_id}' ?? target_variable_tag?")
            if target_variable is None:
                raise ValueError(
                    f"???? '{rule_id}' ????????? '{target_variable_tag}'?"
                )
        variable_kind = (target_variable.variable_kind or "single") if target_variable else ""
        normalized_operator: str | None = None
        normalized_expected_value: str | None = None
        normalized_expected_value_mode: str | None = None
        normalized_reference_variable_tag: str | None = None
        normalized_sequence_direction: str | None = None
        normalized_sequence_step: str | None = None
        normalized_sequence_start_mode: str | None = None
        normalized_sequence_start_value: str | None = None
        normalized_composite_config: CompositeRuleConfig | None = None
        normalized_key_check_mode: DualCompositeKeyCheckMode | None = None
        normalized_left_key_field: str | None = None
        normalized_right_key_field: str | None = None
        normalized_dual_comparisons: list[DualCompositeComparison] = []
        normalized_left_filters: list[CompositeCondition] = []
        normalized_right_filters: list[CompositeCondition] = []
        normalized_pipeline_config: MultiCompositePipelineConfig | None = None
        normalized_mapping_config: MultiCompositeMappingConfig | None = None
        normalized_display_field: str | None = None

        if not is_node_driven_rule:
            if variable_kind == "single" and rule_type == "composite_condition_check":
                raise ValueError(
                    f"???? '{rule_id}' ???????? '{target_variable_tag}'????????????????"
                )
            if variable_kind == "single" and rule_type == "dual_composite_compare":
                raise ValueError(
                    f"规则 '{rule_id}' 引用了单变量 '{target_variable_tag}'，不能保存双组合变量比对。"
                )
            if variable_kind == "composite" and rule_type not in {
                "composite_condition_check",
                "dual_composite_compare",
            }:
                raise ValueError(
                    f"规则 '{rule_id}' 引用了组合变量 '{target_variable_tag}'，不能保存单变量规则。"
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
            normalized_expected_value_mode = _normalize_expected_value_mode_for_operator(
                operator=operator,
                expected_value=expected_value,
                expected_value_mode=expected_value_mode,
                context=f"规则 '{rule_id}'",
            )
            normalized_operator = operator
            normalized_expected_value = expected_value
        elif rule_type == "regex_check":
            if operator or reference_variable_tag or rule.composite_config is not None:
                raise ValueError(
                    f"规则 '{rule_id}' 的正则校验不应包含比较操作符、参考变量或组合配置。"
                )
            if not expected_value:
                raise ValueError(f"规则 '{rule_id}' 缺少正则表达式。")
            try:
                re.compile(expected_value)
            except re.error as exc:
                raise ValueError(
                    f"规则 '{rule_id}' 的正则表达式无效：{expected_value}"
                ) from exc
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
                normalized_left_key_field,
                normalized_right_key_field,
                normalized_dual_comparisons,
                normalized_left_filters,
                normalized_right_filters,
            ) = _normalize_dual_composite_rule(
                rule_id=rule_id,
                target_variable=target_variable,
                target_variable_tag=target_variable_tag,
                reference_variable_tag=reference_variable_tag,
                key_check_mode=rule.key_check_mode,
                left_key_field=rule.left_key_field,
                right_key_field=rule.right_key_field,
                comparisons=rule.comparisons,
                left_filters=rule.left_filters,
                right_filters=rule.right_filters,
                variable_map=variable_map,
            )
        elif rule_type == "multi_composite_pipeline_check":
            normalized_pipeline_config = _normalize_multi_composite_pipeline_config(
                rule_id=rule_id,
                pipeline_config=rule.pipeline_config,
                variable_map=variable_map,
            )
            target_variable_tag = normalized_pipeline_config.nodes[0].variable_tag
        elif rule_type == "multi_composite_mapping_check":
            normalized_mapping_config = _normalize_multi_composite_mapping_config(
                rule_id=rule_id,
                mapping_config=rule.mapping_config,
                variable_map=variable_map,
                allow_legacy_mapping_config=allow_legacy_mapping_config,
                config_issues=config_issues,
                issue_keys=issue_keys,
            )
            target_variable_tag = normalized_mapping_config.nodes[0].variable_tag

        if not is_node_driven_rule:
            normalized_display_field = _normalize_display_field(
                rule_id=rule_id,
                variable=target_variable,
                display_field=rule.display_field,
            )

        normalized_rules.append(
            FixedRuleDefinition(
                rule_id=rule_id,
                group_id=group_id,
                rule_name=rule_name,
                target_variable_tag=target_variable_tag,
                display_field=normalized_display_field,
                rule_type=rule_type,
                operator=normalized_operator,
                expected_value=normalized_expected_value,
                expected_value_mode=normalized_expected_value_mode,
                reference_variable_tag=normalized_reference_variable_tag,
                sequence_direction=normalized_sequence_direction,
                sequence_step=normalized_sequence_step,
                sequence_start_mode=normalized_sequence_start_mode,
                sequence_start_value=normalized_sequence_start_value,
                composite_config=normalized_composite_config,
                key_check_mode=normalized_key_check_mode,
                left_key_field=normalized_left_key_field,
                right_key_field=normalized_right_key_field,
                comparisons=normalized_dual_comparisons,
                left_filters=normalized_left_filters,
                right_filters=normalized_right_filters,
                pipeline_config=normalized_pipeline_config,
                mapping_config=normalized_mapping_config,
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


def _normalize_multi_composite_pipeline_config(
    *,
    rule_id: str,
    pipeline_config: MultiCompositePipelineConfig | None,
    variable_map: dict[str, VariableTag],
) -> MultiCompositePipelineConfig:
    """校验并规范多组合变量串行校验配置。"""
    if pipeline_config is None:
        raise ValueError(f"规则 '{rule_id}' 缺少 pipeline_config。")
    if not pipeline_config.nodes:
        raise ValueError(f"规则 '{rule_id}' 至少需要一个组合变量节点。")

    normalized_nodes: list[MultiCompositePipelineNode] = []
    seen_node_ids: set[str] = set()

    for node_index, node in enumerate(pipeline_config.nodes, start=1):
        node_id = node.node_id.strip()
        variable_tag = (node.variable_tag or "").strip()
        if not node_id:
            raise ValueError(f"规则 '{rule_id}' 的节点 {node_index} 缺少 node_id。")
        if node_id in seen_node_ids:
            raise ValueError(
                f"规则 '{rule_id}' 的节点存在重复 node_id '{node_id}'。"
            )
        if not variable_tag:
            raise ValueError(f"规则 '{rule_id}' 的节点 {node_index} 缺少 variable_tag。")
        if variable_tag not in variable_map:
            raise ValueError(
                f"规则 '{rule_id}' 的节点 {node_index} 引用了不存在的组合变量 '{variable_tag}'。"
            )

        variable = variable_map[variable_tag]
        if (variable.variable_kind or "single") != "composite":
            raise ValueError(
                f"规则 '{rule_id}' 的节点 {node_index} 引用了单变量 '{variable_tag}'，"
                "多组合变量串行校验仅支持组合变量。"
            )

        available_fields = _collect_composite_available_fields(variable)
        display_field = _normalize_display_field(
            rule_id=rule_id,
            variable=variable,
            display_field=node.display_field,
        )
        filters = _normalize_composite_conditions(
            rule_id=rule_id,
            conditions=node.filters,
            section_label=f"节点 {node_index} 的前置过滤",
            available_fields=available_fields,
            allowed_operators=SUPPORTED_COMPOSITE_FILTER_OPERATORS,
        )
        assertions = _normalize_composite_conditions(
            rule_id=rule_id,
            conditions=node.assertions,
            section_label=f"节点 {node_index} 的最终判定",
            available_fields=available_fields,
            allowed_operators=SUPPORTED_MULTI_PIPELINE_ASSERTION_OPERATORS,
        )
        if not assertions:
            raise ValueError(f"规则 '{rule_id}' 的节点 {node_index} 至少需要一条最终判定。")

        normalized_nodes.append(
            MultiCompositePipelineNode(
                node_id=node_id,
                variable_tag=variable_tag,
                display_field=display_field,
                filters=filters,
                assertions=assertions,
            )
        )
        seen_node_ids.add(node_id)

    return MultiCompositePipelineConfig(nodes=normalized_nodes)


def _normalize_multi_composite_mapping_config(
    *,
    rule_id: str,
    mapping_config: MultiCompositeMappingConfig | None,
    variable_map: dict[str, VariableTag],
    allow_legacy_mapping_config: bool = False,
    config_issues: list[FixedRulesConfigIssue] | None = None,
    issue_keys: set[tuple[str, str | None, str | None, str | None, str]] | None = None,
) -> MultiCompositeMappingConfig:
    """校验并规范多组映射校验配置。"""
    if mapping_config is None:
        raise ValueError(f"规则 '{rule_id}' 缺少 mapping_config。")
    if not mapping_config.nodes:
        raise ValueError(f"规则 '{rule_id}' 至少需要一个映射节点。")

    normalized_nodes: list[MultiCompositeMappingNode] = []
    seen_node_ids: set[str] = set()

    for node_index, node in enumerate(mapping_config.nodes, start=1):
        node_id = node.node_id.strip()
        variable_tag = (node.variable_tag or "").strip()
        if not node_id:
            raise ValueError(f"规则 '{rule_id}' 的映射节点 {node_index} 缺少 node_id。")
        if node_id in seen_node_ids:
            raise ValueError(
                f"规则 '{rule_id}' 的映射节点存在重复 node_id '{node_id}'。"
            )
        if not variable_tag:
            raise ValueError(f"规则 '{rule_id}' 的映射节点 {node_index} 缺少 variable_tag。")
        if variable_tag not in variable_map:
            raise ValueError(
                f"规则 '{rule_id}' 的映射节点 {node_index} 引用了不存在的组合变量 '{variable_tag}'。"
            )

        variable = variable_map[variable_tag]
        if (variable.variable_kind or "single") != "composite":
            raise ValueError(
                f"规则 '{rule_id}' 的映射节点 {node_index} 引用了单变量 '{variable_tag}'，"
                "多组映射校验仅支持组合变量。"
            )

        available_fields = _collect_composite_available_fields(variable)
        display_field = _normalize_display_field(
            rule_id=rule_id,
            variable=variable,
            display_field=node.display_field,
        )
        filters = _normalize_multi_composite_mapping_filters(
            rule_id=rule_id,
            conditions=node.filters,
            node_index=node_index,
            available_fields=available_fields,
            allow_legacy_mapping_config=allow_legacy_mapping_config,
            config_issues=config_issues,
            issue_keys=issue_keys,
        )
        if not filters:
            if allow_legacy_mapping_config and _has_legacy_mapping_node_content(node):
                normalized_nodes.append(
                    MultiCompositeMappingNode(
                        node_id=node_id,
                        variable_tag=variable_tag,
                        display_field=display_field,
                        filters=[],
                    )
                )
                seen_node_ids.add(node_id)
                continue
            raise ValueError(f"规则 '{rule_id}' 的映射节点 {node_index} 至少需要一条筛选条件。")

        normalized_nodes.append(
            MultiCompositeMappingNode(
                node_id=node_id,
                variable_tag=variable_tag,
                display_field=display_field,
                filters=filters,
            )
        )
        seen_node_ids.add(node_id)

    return MultiCompositeMappingConfig(nodes=normalized_nodes)


def _has_legacy_mapping_node_content(node: MultiCompositeMappingNode) -> bool:
    """识别旧版字段检查配置，读取时允许丢弃，保存时仍要求重配筛选。"""
    return bool(node.field_checks or node.field or node.ranges)


def _normalize_multi_composite_mapping_filters(
    *,
    rule_id: str,
    conditions: list[MultiCompositeMappingFilter],
    node_index: int,
    available_fields: list[str],
    allow_legacy_mapping_config: bool = False,
    config_issues: list[FixedRulesConfigIssue] | None = None,
    issue_keys: set[tuple[str, str | None, str | None, str | None, str]] | None = None,
) -> list[MultiCompositeMappingFilter]:
    """校验并规范单个映射节点下的筛选检查列表。"""
    normalized_conditions = _normalize_composite_conditions(
        rule_id=rule_id,
        conditions=conditions,
        section_label=f"映射节点 {node_index} 的筛选条件",
        available_fields=available_fields,
        allowed_operators=SUPPORTED_COMPOSITE_FILTER_OPERATORS,
    )
    normalized_filters: list[MultiCompositeMappingFilter] = []

    for filter_index, condition in enumerate(conditions, start=1):
        normalized_condition = normalized_conditions[filter_index - 1]
        exclusion_ranges = _normalize_multi_composite_mapping_exclusion_ranges(
            rule_id=rule_id,
            node_index=node_index,
            filter_index=filter_index,
            ranges=condition.exclusion_ranges,
            allow_legacy_mapping_config=allow_legacy_mapping_config,
            config_issues=config_issues,
            issue_keys=issue_keys,
        )
        normalized_filters.append(
            MultiCompositeMappingFilter(
                **normalized_condition.model_dump(mode="python"),
                exclusion_ranges=exclusion_ranges,
            )
        )

    return normalized_filters


def _normalize_multi_composite_mapping_exclusion_ranges(
    *,
    rule_id: str,
    node_index: int,
    filter_index: int,
    ranges: list[MultiCompositeMappingExclusionRange],
    allow_legacy_mapping_config: bool = False,
    config_issues: list[FixedRulesConfigIssue] | None = None,
    issue_keys: set[tuple[str, str | None, str | None, str | None, str]] | None = None,
) -> list[MultiCompositeMappingExclusionRange]:
    """校验并规范单条筛选失败后的排除行号范围。"""
    if not ranges:
        return []

    normalized_ranges: list[MultiCompositeMappingExclusionRange] = []
    seen_range_ids: set[str] = set()

    for range_index, row_range in enumerate(ranges, start=1):
        range_id = row_range.range_id.strip()
        start_row = row_range.start_row
        end_row = row_range.end_row
        expected_value = (row_range.expected_value or "").strip()

        if not range_id:
            raise ValueError(
                f"规则 '{rule_id}' 的映射节点 {node_index} 筛选条件 {filter_index} "
                f"第 {range_index} 段排除范围缺少 range_id。"
            )
        if range_id in seen_range_ids:
            raise ValueError(
                f"规则 '{rule_id}' 的映射节点 {node_index} 筛选条件 {filter_index} "
                f"存在重复 range_id '{range_id}'。"
            )
        if start_row <= 0 or end_row <= 0:
            raise ValueError(
                f"规则 '{rule_id}' 的映射节点 {node_index} 筛选条件 {filter_index} "
                f"第 {range_index} 段排除范围行号必须大于 0。"
            )
        if start_row > end_row:
            raise ValueError(
                f"规则 '{rule_id}' 的映射节点 {node_index} 筛选条件 {filter_index} "
                f"第 {range_index} 段排除范围开始行不能大于结束行。"
            )
        if not expected_value:
            message = (
                f"规则 '{rule_id}' 的映射节点 {node_index} 筛选条件 {filter_index} "
                f"第 {range_index} 段排除范围缺少判定值。"
            )
            if allow_legacy_mapping_config and config_issues is not None:
                _append_config_issue(
                    config_issues,
                    issue_keys,
                    rule_id=rule_id,
                    message=f"{message} 请补齐后重新保存或执行。",
                )
            else:
                raise ValueError(message)
        else:
            try:
                parse_expected_value_set(expected_value)
            except ValueError as exc:
                raise ValueError(
                    f"规则 '{rule_id}' 的映射节点 {node_index} 筛选条件 {filter_index} "
                    f"第 {range_index} 段排除范围判定值至少需要一个固定值。"
                ) from exc

        seen_range_ids.add(range_id)
        normalized_ranges.append(
            MultiCompositeMappingExclusionRange(
                range_id=range_id,
                start_row=start_row,
                end_row=end_row,
                expected_value=expected_value or None,
            )
        )

    return normalized_ranges


def _normalize_dual_composite_rule(
    *,
    rule_id: str,
    target_variable: VariableTag,
    target_variable_tag: str,
    reference_variable_tag: str,
    key_check_mode: DualCompositeKeyCheckMode | None,
    left_key_field: str | None,
    right_key_field: str | None,
    comparisons: list[DualCompositeComparison],
    left_filters: list[CompositeCondition],
    right_filters: list[CompositeCondition],
    variable_map: dict[str, VariableTag],
) -> tuple[
    str,
    DualCompositeKeyCheckMode,
    str,
    str,
    list[DualCompositeComparison],
    list[CompositeCondition],
    list[CompositeCondition],
]:
    """校验并规范双组合变量比对规则。"""
    if not reference_variable_tag:
        raise ValueError(f"规则 '{rule_id}' 缺少 reference_variable_tag。")
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
    normalized_left_key_field = _normalize_dual_key_field(
        rule_id=rule_id,
        field=left_key_field,
        available_fields=left_fields,
        section_label="左侧关联 Key 字段",
    )
    normalized_right_key_field = _normalize_dual_key_field(
        rule_id=rule_id,
        field=right_key_field,
        available_fields=right_fields,
        section_label="右侧关联 Key 字段",
    )
    normalized_left_filters = _normalize_composite_conditions(
        rule_id=rule_id,
        conditions=left_filters,
        section_label="左侧筛选条件",
        available_fields=left_fields,
        allowed_operators=SUPPORTED_COMPOSITE_FILTER_OPERATORS,
    )
    normalized_right_filters = _normalize_composite_conditions(
        rule_id=rule_id,
        conditions=right_filters,
        section_label="右侧筛选条件",
        available_fields=right_fields,
        allowed_operators=SUPPORTED_COMPOSITE_FILTER_OPERATORS,
    )
    if reference_variable_tag == target_variable_tag and (
        not normalized_left_filters or not normalized_right_filters
    ):
        raise ValueError(
            f"规则 '{rule_id}' 同一组合变量进行筛选对比时，左右筛选条件都不能为空。"
        )

    normalized_comparisons: list[DualCompositeComparison] = []
    seen_comparison_ids: set[str] = set()

    for index, comparison in enumerate(comparisons, start=1):
        comparison_id = comparison.comparison_id.strip()
        left_field = comparison.left_field or ""
        operator = str(comparison.operator).strip()
        right_field = comparison.right_field or ""

        if not comparison_id:
            raise ValueError(f"规则 '{rule_id}' 的字段比对 {index} 缺少 comparison_id。")
        if comparison_id in seen_comparison_ids:
            raise ValueError(
                f"规则 '{rule_id}' 的字段比对存在重复 comparison_id '{comparison_id}'。"
            )
        if not left_field.strip():
            raise ValueError(f"规则 '{rule_id}' 的字段比对 {index} 缺少左侧字段。")
        try:
            resolved_left_field = _resolve_identifier_against_available(
                left_field,
                left_fields,
                identifier_label="左侧字段",
                context=f"规则 '{rule_id}' 的字段比对 {index}",
            )
        except ValueError as exc:
            raise ValueError(
                f"规则 '{rule_id}' 的字段比对 {index} 引用了无效的左侧字段 '{left_field}'。"
            ) from exc
        if operator not in SUPPORTED_DUAL_COMPOSITE_OPERATORS:
            raise ValueError(
                f"规则 '{rule_id}' 的字段比对 {index} 使用了不支持的运算符 '{operator}'。"
            )
        if not right_field.strip():
            raise ValueError(f"规则 '{rule_id}' 的字段比对 {index} 缺少右侧字段。")
        try:
            resolved_right_field = _resolve_identifier_against_available(
                right_field,
                right_fields,
                identifier_label="右侧字段",
                context=f"规则 '{rule_id}' 的字段比对 {index}",
            )
        except ValueError as exc:
            raise ValueError(
                f"规则 '{rule_id}' 的字段比对 {index} 引用了无效的右侧字段 '{right_field}'。"
            ) from exc

        normalized_comparisons.append(
            DualCompositeComparison(
                comparison_id=comparison_id,
                left_field=resolved_left_field,
                operator=operator,
                right_field=resolved_right_field,
            )
        )
        seen_comparison_ids.add(comparison_id)

    return (
        reference_variable_tag,
        normalized_key_check_mode,
        normalized_left_key_field,
        normalized_right_key_field,
        normalized_comparisons,
        normalized_left_filters,
        normalized_right_filters,
    )


def _normalize_dual_key_field(
    *,
    rule_id: str,
    field: str | None,
    available_fields: list[str],
    section_label: str,
) -> str:
    """规范跨组变量比对的显式关联 Key 字段，缺省兼容内部 `__key__`。"""
    normalized_field = (field or COMPOSITE_KEY_FIELD).strip() or COMPOSITE_KEY_FIELD
    try:
        return _resolve_identifier_against_available(
            normalized_field,
            available_fields,
            identifier_label=section_label,
            context=f"规则 '{rule_id}'",
        )
    except ValueError as exc:
        raise ValueError(
            f"规则 '{rule_id}' 的{section_label} '{normalized_field}' 不属于对应组合变量。"
        ) from exc


def _normalize_composite_conditions(
    *,
    rule_id: str,
    conditions: list[CompositeCondition],
    section_label: str,
    available_fields: list[str],
    allowed_operators: set[str],
) -> list[CompositeCondition]:
    """????????????????"""
    normalized_conditions: list[CompositeCondition] = []
    seen_condition_ids: set[str] = set()

    for condition in conditions:
        condition_id = condition.condition_id.strip()
        field = condition.field or ""
        operator = str(condition.operator).strip()
        value_source = condition.value_source
        expected_value = condition.expected_value.strip() if condition.expected_value else ""
        expected_value_mode = condition.expected_value_mode
        expected_field = condition.expected_field or ""

        if not condition_id:
            raise ValueError(f"???? '{rule_id}' ?{section_label}???? condition_id ????")
        if condition_id in seen_condition_ids:
            raise ValueError(
                f"???? '{rule_id}' ?{section_label}???? condition_id?'{condition_id}'?"
            )
        if not field.strip():
            raise ValueError(f"???? '{rule_id}' ?{section_label}??????????")
        try:
            resolved_field = _resolve_identifier_against_available(
                field,
                available_fields,
                identifier_label="字段",
                context=f"规则 '{rule_id}' 的{section_label}",
            )
        except ValueError as exc:
            raise ValueError(
                f"???? '{rule_id}' ?{section_label}????????? '{field}'?"
            ) from exc
        if operator not in allowed_operators:
            raise ValueError(
                f"???? '{rule_id}' ?{section_label}?????????? '{operator}'?"
            )

        normalized_value_source: str | None = None
        normalized_expected_value: str | None = None
        normalized_expected_value_mode: str | None = None
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
                normalized_expected_value_mode = _normalize_expected_value_mode_for_operator(
                    operator=operator,
                    expected_value=expected_value,
                    expected_value_mode=expected_value_mode,
                    context=f"规则 '{rule_id}' 的{section_label}",
                )
                normalized_expected_value = expected_value
            elif normalized_value_source == "field":
                if normalize_expected_value_mode(expected_value_mode) == "set":
                    raise ValueError(
                        f"规则 '{rule_id}' 的{section_label}字段对比不支持规则集比较值。"
                    )
                if not expected_field.strip():
                    raise ValueError(f"???? '{rule_id}' ?{section_label}?????????")
                try:
                    resolved_expected_field = _resolve_identifier_against_available(
                        expected_field,
                        available_fields,
                        identifier_label="右侧字段",
                        context=f"规则 '{rule_id}' 的{section_label}",
                    )
                except ValueError as exc:
                    raise ValueError(
                        f"???? '{rule_id}' ?{section_label}??????????? '{expected_field}'?"
                    ) from exc
                normalized_expected_field = resolved_expected_field
            else:
                raise ValueError(
                    f"???? '{rule_id}' ?{section_label}??????? value_source '{value_source}'?"
                )
        elif operator in {"contains", "not_contains"}:
            normalized_value_source = "literal"
            if value_source == "field":
                raise ValueError(
                    f"规则 '{rule_id}' 的{section_label}操作符 '{operator}' 只支持固定值。"
                )
            if not expected_value:
                raise ValueError(f"规则 '{rule_id}' 的{section_label}缺少比较值。")
            if expected_field:
                raise ValueError(
                    f"规则 '{rule_id}' 的{section_label}操作符 '{operator}' 不支持右侧字段。"
                )
            normalized_expected_value = expected_value
        elif operator == "not_null":
            normalized_value_source = None
            if value_source or expected_value or expected_field:
                raise ValueError(
                    f"???? '{rule_id}' ?{section_label}? 'not_null' ????????????"
                )
        elif operator == "regex":
            normalized_value_source = None
            if value_source:
                raise ValueError(
                    f"规则 '{rule_id}' 的{section_label}操作符 'regex' 不支持右值来源。"
                )
            if not expected_value:
                raise ValueError(f"规则 '{rule_id}' 的{section_label}缺少正则表达式。")
            if expected_field:
                raise ValueError(
                    f"规则 '{rule_id}' 的{section_label}操作符 'regex' 不支持右侧字段。"
                )
            try:
                re.compile(expected_value)
            except re.error as exc:
                raise ValueError(
                    f"规则 '{rule_id}' 的{section_label}正则表达式无效：{expected_value}"
                ) from exc
            normalized_expected_value = expected_value
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
                field=resolved_field,
                operator=operator,
                value_source=normalized_value_source,
                expected_value=normalized_expected_value,
                expected_value_mode=normalized_expected_value_mode,
                expected_field=normalized_expected_field,
            )
        )
        seen_condition_ids.add(condition_id)

    return normalized_conditions


def _collect_composite_available_fields(variable: VariableTag) -> list[str]:
    """??????????????????"""
    available_fields = [COMPOSITE_KEY_FIELD]
    key_column = variable.key_column or ""
    if key_column.strip():
        available_fields.append(key_column)
    available_fields.extend(
        column
        for column in (variable.columns or [])
        if column and column.strip()
    )
    available_fields = list(dict.fromkeys(available_fields))
    return available_fields


def _normalize_display_field(
    *,
    rule_id: str,
    variable: VariableTag,
    display_field: str | None,
) -> str | None:
    """校验规则结果显示字段，并限制在当前关联变量内。"""
    normalized_field = (display_field or "").strip()
    if not normalized_field:
        return None

    if (variable.variable_kind or "single") == "composite":
        available_fields = _collect_composite_available_fields(variable)
    else:
        available_fields = [variable.column] if variable.column else []

    if normalized_field not in available_fields:
        raise ValueError(
            f"规则 '{rule_id}' 的结果显示字段 '{normalized_field}' 不属于当前关联变量。"
        )
    return normalized_field


def _load_sheet_columns(
    *,
    source: DataSource,
    sheet_name: str,
    metadata_cache: dict[str, dict[str, object]],
    variable_tag: str | None = None,
    config_issues: list[FixedRulesConfigIssue] | None = None,
    issue_keys: set[tuple[str, str | None, str | None, str | None, str]] | None = None,
) -> tuple[str, list[str]] | None:
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
                    f"数据源“{source.id}”的本地路径已失效：{source.pathOrUrl or source.path or ''}。"
                    "请到“数据源接入管理”中修复路径后再保存或执行。"
                ),
            )
            metadata_cache[source.id] = {"sheets": [], "__missing__": True}
            return None
        metadata_cache[source.id] = metadata
    elif metadata.get("__missing__") or metadata.get("__unsupported_csv__"):
        return None

    try:
        resolved_sheet_name = _resolve_identifier_against_available(
            sheet_name,
            [str(sheet["name"]) for sheet in metadata["sheets"]],
            identifier_label="Sheet",
            context=f"数据源“{source.id}”",
        )
    except ValueError as exc:
        if config_issues is not None:
            _append_config_issue(
                config_issues,
                issue_keys,
                source_id=source.id,
                variable_tag=variable_tag,
                message=f"{exc}请到“数据源接入管理”或变量配置中修复后再保存或执行。",
            )
            return None
        raise

    for sheet in metadata["sheets"]:
        if sheet["name"] == resolved_sheet_name:
            return resolved_sheet_name, list(sheet["columns"])

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

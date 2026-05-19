"""从自然语言规则描述中抽取 AI 工作流结构化线索。"""

from __future__ import annotations

import re

from backend.app.ai.extractors.source import (
    derive_source_id as _derive_source_id,
    extract_source_url as _extract_source_url,
    guess_source_type as _guess_source_type,
)
from backend.app.ai.extractors.value import (
    extract_fixed_value_compare as _extract_fixed_value_compare,
    extract_sequence as _extract_sequence,
)
from backend.app.ai.template.labels import (
    RULE_TYPE_ALIASES,
    SUPPORTED_RULE_TYPES,
    TEMPLATE_LABELS,
    TEMPLATE_PLACEHOLDERS,
)
from backend.app.ai.template.legacy_adapter import normalize_legacy_template_text
from backend.app.ai.template.template_dsl import (
    extract_template_sections,
    normalize_inline_template_labels,
    normalize_text,
)
from backend.app.ai.workflow_hints import AiRuleFilterHint, AiRuleWorkflowHints


SERVER_CONFIG_PATTERN = r"^(?:(?:all|\d+(?:-\d+)?):[01](;(?:all|\d+(?:-\d+)?):[01])*)?$"
FIELD_TOKEN_PATTERN = r"(?<![A-Za-z0-9_])[A-Z][A-Za-z0-9]*_[A-Za-z0-9_]+(?![A-Za-z0-9_])"


def _is_placeholder_key_column(value: str | None) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text:
        return False
    if "未识别" in text or "需要用户确认" in text:
        return True
    compact = re.sub(r"[\s:：=为是列字段、，。；;]+", "", text).lower()
    return compact in {
        "key",
        "关联key",
        "业务key",
        "比对key",
        "对齐key",
        "主键",
        "唯一键",
        "索引",
    }


def extract_workflow_hints_from_text(text: str) -> AiRuleWorkflowHints:
    """用确定性规则抽取常见导表规则描述中的数据源、Sheet、字段和组合变量线索。"""
    dsl_text = normalize_legacy_template_text(text)
    normalized_text = _normalize_text(dsl_text)
    template_sections = _extract_template_sections(dsl_text)
    natural_target_text = _extract_natural_target_text(normalized_text)
    natural_filter_text = _extract_natural_filter_text(normalized_text)
    natural_rule_text = _extract_natural_rule_text(normalized_text)
    natural_extra_text = _extract_natural_extra_text(normalized_text)
    explicit_rule_semantic_text = " ".join(
        item
        for item in (
            template_sections.get("规则类型"),
            template_sections.get("校验规则"),
            template_sections.get("规则是"),
            template_sections.get("判定"),
            template_sections.get("最终判定"),
            template_sections.get("校验判定"),
            template_sections.get("断言"),
            template_sections.get("规则参数"),
            template_sections.get("补充说明"),
            natural_rule_text,
            natural_extra_text,
        )
        if item
    )
    rule_semantic_text = explicit_rule_semantic_text or normalized_text
    source_value = _extract_source_value(normalized_text)
    source_url = (
        source_value
        if source_value and _looks_like_source_path_or_url(source_value)
        else _extract_source_url(normalized_text)
    )
    source_id = _derive_source_id(source_url) if source_url else source_value
    sheet = _extract_sheet(normalized_text)
    template_columns = _extract_template_variable_columns(normalized_text)
    target_variable_tag = _extract_labeled_variable_tag(normalized_text, ("目标变量", "变量"))
    reference_variable_tag = _extract_labeled_variable_tag(normalized_text, ("引用变量", "字典变量"))
    left_variable_tag = _extract_labeled_variable_tag(normalized_text, ("左侧变量", "基准变量"))
    right_variable_tag = _extract_labeled_variable_tag(normalized_text, ("右侧变量", "对比变量"))
    template_reference_variable_tag, template_reference_field = _extract_template_reference(
        template_sections.get("引用对象")
    )
    (
        left_filter_field,
        left_filter_operator,
        left_filter_value,
        right_filter_field,
        right_filter_operator,
        right_filter_value,
    ) = _extract_dual_filters(normalized_text)
    template_key_column = _extract_template_key_column(template_sections)
    natural_key_column = _extract_natural_key_column(normalized_text)
    template_filters = _extract_template_filters(template_sections)
    if template_filters:
        template_filter_field = template_filters[0].field
        template_filter_value = template_filters[0].value
        template_filter_operator = template_filters[0].operator
    else:
        template_filter_field, template_filter_value, template_filter_operator = _extract_template_filter(template_sections)
    natural_filter_tuple = (
        _parse_filter_expression_with_operator(natural_filter_text) if natural_filter_text else (None, None, None)
    )
    natural_filter_field, natural_filter_value, natural_filter_operator = natural_filter_tuple
    natural_filters = (
        [
            AiRuleFilterHint(
                field=natural_filter_field,
                operator=natural_filter_operator or "eq",
                value=natural_filter_value,
            )
        ]
        if natural_filter_field and natural_filter_value
        else []
    )
    extracted_filter_hints = template_filters or natural_filters
    if template_filter_field:
        filter_field, filter_value, filter_operator_source = template_filter_field, template_filter_value, template_filter_operator
    elif natural_filter_field:
        filter_field, filter_value, filter_operator_source = natural_filter_field, natural_filter_value, natural_filter_operator
    else:
        filter_field, filter_value = _extract_filter(normalized_text)
        filter_operator_source = None
    filter_operator = template_filter_operator or _extract_filter_operator(
        natural_filter_text or template_sections.get("筛选条件") or normalized_text,
        filter_field,
        filter_value,
    )
    filter_operator = filter_operator_source or filter_operator
    display_field = _extract_display_field(normalized_text)
    key_column = template_key_column or natural_key_column or _extract_key_column(normalized_text)
    compare_fields = _extract_compare_fields(
        normalized_text,
        key_column=key_column,
        filter_fields=[filter_field, left_filter_field, right_filter_field],
        display_field=display_field,
    )
    compare_fields = [
        field for field in compare_fields if field not in {sheet, source_id, _derive_source_id(source_url) if source_url else None}
    ]
    explicit_rule_type_hint = _normalize_rule_type(
        template_sections.get("规则类型") or template_sections.get("rule_type")
    )
    rule_type_hint = explicit_rule_type_hint or _extract_rule_type_hint(template_sections, rule_semantic_text)
    if _looks_like_dual_compare_shape(
        normalized_text,
        left_filter_field=left_filter_field,
        left_filter_value=left_filter_value,
        right_filter_field=right_filter_field,
        right_filter_value=right_filter_value,
        key_column=key_column,
        compare_fields=compare_fields,
    ):
        rule_type_hint = "dual_composite_compare"
    if rule_type_hint == "dual_composite_compare":
        filter_field = None
        filter_value = None
        filter_operator = None
        extracted_filter_hints = []
    else:
        left_filter_field = None
        left_filter_value = None
        right_filter_field = None
        right_filter_value = None
    template_target_field = _extract_template_field_value(
        template_sections.get("目标字段")
        or template_sections.get("目标列名")
        or template_sections.get("目标")
        or template_sections.get("校验字段")
    )
    natural_target_field = _extract_template_field_value(natural_target_text)
    target_field = template_target_field or natural_target_field or _extract_target_field(
        normalized_text,
        filter_field=filter_field,
        display_field=display_field,
        key_column=key_column if rule_type_hint != "dual_composite_compare" else None,
        compare_fields=compare_fields,
    ) or (template_columns[0] if template_columns else None)
    if rule_type_hint == "dual_composite_compare" and key_column:
        target_field = target_field or key_column
    rule_parameter_text = "\n".join(
        item
        for item in (
            template_sections.get("校验规则"),
            template_sections.get("规则是"),
            template_sections.get("判定"),
            template_sections.get("最终判定"),
            template_sections.get("校验判定"),
            template_sections.get("断言"),
            template_sections.get("规则参数"),
            template_sections.get("补充说明"),
            natural_rule_text,
            natural_extra_text,
        )
        if item
    ) or normalized_text
    regex_pattern = _extract_regex_pattern(rule_parameter_text)
    operator, expected_value, expected_value_mode = _extract_fixed_value_compare(rule_parameter_text)
    compare_operator = _extract_dual_compare_operator(rule_parameter_text)
    key_check_mode = _extract_key_check_mode(normalized_text)
    assertion_field, assertion_operator, assertion_value, assertion_value_source, assertion_expected_field = _extract_assertion_compare(
        rule_parameter_text,
        filter_field=filter_field,
        candidate_fields=[*template_columns, key_column or "", target_field or ""],
    )
    if not assertion_field and target_field:
        (
            assertion_field,
            assertion_operator,
            assertion_value,
            assertion_value_source,
            assertion_expected_field,
        ) = _extract_target_based_assertion(rule_parameter_text, target_field) or (
            assertion_field,
            assertion_operator,
            assertion_value,
            assertion_value_source,
            assertion_expected_field,
        )
    if (
        filter_field == assertion_field
        and filter_operator == "not_null"
        and assertion_operator == "not_null"
        and not template_filter_field
        and not natural_filter_field
    ):
        filter_field = None
        filter_value = None
        filter_operator = None
    if (
        assertion_value_source == "field"
        and assertion_expected_field
        and (not explicit_rule_type_hint or explicit_rule_type_hint == "composite_condition_check")
    ):
        rule_type_hint = "composite_condition_check"
    if _has_filter_assertion_pair(
        rule_type_hint,
        filter_field=filter_field,
        filter_value=filter_value,
        assertion_field=assertion_field,
        assertion_value=assertion_value,
        assertion_expected_field=assertion_expected_field,
        assertion_operator=assertion_operator,
        filter_operator=filter_operator,
    ) and (not explicit_rule_type_hint or explicit_rule_type_hint == "composite_condition_check"):
        rule_type_hint = "composite_condition_check"
    target_field = assertion_field or target_field
    sequence_direction, sequence_step, sequence_start_mode, sequence_start_value = _extract_sequence(
        rule_parameter_text
    )
    if source_id == "server_config" and sheet == "switch" and target_field == "STR_ServersParam":
        rule_type_hint = "composite_condition_check"
        key_column = key_column or "INT_Id"
        display_field = display_field or "STR_Func"
        filter_field = filter_field or "DES"
        filter_value = filter_value or "废弃"
        filter_operator = "not_contains"
        regex_pattern = regex_pattern or SERVER_CONFIG_PATTERN
    composite_columns = _dedupe_values(
        [
            *_build_composite_columns(
                key_column=key_column,
                display_field=display_field,
                target_field=target_field,
                filter_field=filter_field,
                filter_fields=[item.field for item in extracted_filter_hints],
                left_filter_field=left_filter_field,
                right_filter_field=right_filter_field,
                compare_fields=compare_fields,
            ),
            *template_columns,
        ]
    )

    return AiRuleWorkflowHints(
        rule_type_hint=rule_type_hint,
        target_variable_tag=target_variable_tag or left_variable_tag,
        reference_variable_tag=template_reference_variable_tag or reference_variable_tag or right_variable_tag,
        left_variable_tag=left_variable_tag,
        right_variable_tag=right_variable_tag,
        source_id=source_id,
        source_type=_guess_source_type(source_url) if source_url else None,
        source_url=source_url,
        sheet=sheet,
        target_field=target_field,
        display_field=display_field,
        filter_field=filter_field,
        filter_operator=filter_operator,
        filter_value=filter_value,
        filters=extracted_filter_hints,
        assertion_field=assertion_field,
        assertion_operator=assertion_operator,
        assertion_value_source=assertion_value_source,
        assertion_expected_field=assertion_expected_field,
        assertion_value=assertion_value,
        operator=operator,
        expected_value=expected_value,
        expected_value_mode=expected_value_mode,
        regex_pattern=regex_pattern,
        sequence_direction=sequence_direction,
        sequence_step=sequence_step,
        sequence_start_mode=sequence_start_mode,
        sequence_start_value=sequence_start_value,
        key_column=key_column,
        composite_columns=composite_columns,
        reference_field=template_reference_field,
        left_filter_field=left_filter_field,
        left_filter_operator=left_filter_operator if left_filter_field else None,
        left_filter_value=left_filter_value,
        right_filter_field=right_filter_field,
        right_filter_operator=right_filter_operator if right_filter_field else None,
        right_filter_value=right_filter_value,
        left_key_field=key_column if rule_type_hint == "dual_composite_compare" else None,
        right_key_field=key_column if rule_type_hint == "dual_composite_compare" else None,
        compare_operator=compare_operator if rule_type_hint == "dual_composite_compare" else None,
        key_check_mode=key_check_mode,
        compare_fields=compare_fields,
        pipeline_nodes=_extract_multi_nodes(normalized_text, mode="pipeline"),
        mapping_nodes=_extract_multi_nodes(normalized_text, mode="mapping"),
    )


def _normalize_text(text: str) -> str:
    return normalize_text(text)


def _unwrap_natural_value(value: str | None) -> str | None:
    text = (value or "").strip()
    text = re.sub(r"^【|】$", "", text)
    text = re.sub(r"[；;。]$", "", text).strip()
    if not text or text in TEMPLATE_PLACEHOLDERS or "【" in text or "】" in text:
        return None
    return text


def _extract_natural_target_text(text: str) -> str | None:
    return _unwrap_natural_value(_first_match(text, [r"我想检查\s*([^。；;\n\r]+)"]))


def _extract_natural_filter_text(text: str) -> str | None:
    value = _unwrap_natural_value(_first_match(text, [r"只检查\s*([^。；;\n\r]+)"]))
    if not value or re.match(r"^(全部数据|所有数据|无|不限制)$", value, re.IGNORECASE):
        return None
    return re.sub(r"(?:的)?数据$", "", re.sub(r"^满足\s*", "", value)).strip() or None


def _extract_natural_rule_text(text: str) -> str | None:
    return _unwrap_natural_value(_first_match(text, [r"(?:规则是|判定|最终判定|校验判定)\s*[：:=]?\s*([^。；;\n\r]+)"]))


def _extract_natural_extra_text(text: str) -> str | None:
    value = _unwrap_natural_value(_first_match(text, [r"补充说明\s*[：:=]?\s*([^。；;\n\r]+)"]))
    if not value or re.match(r"^(无|可选|无需)$", value, re.IGNORECASE):
        return None
    return value


def _extract_natural_key_column(text: str) -> str | None:
    value = _first_match(
        text,
        [
            r"(?:Key值选择|Key选择|Key值|选择Key)\s*[：:=]?\s*([A-Za-z][A-Za-z0-9_]*)",
            r"用\s*([A-Za-z][A-Za-z0-9_]*)\s*(?:字段)?\s*作为\s*(?:Key|key|主键|唯一键)",
        ],
    )
    return None if _is_placeholder_key_column(value) else value


def _extract_source_value(text: str) -> str | None:
    return _extract_template_value(text, ("数据源", "配置表链接", "配置表路径"))


def _extract_sheet(text: str) -> str | None:
    template_sheet = _extract_template_value(text, ("sheet分页", "Sheet分页", "sheet", "Sheet"))
    if template_sheet:
        return template_sheet
    patterns = [
        r"\$?\s*([A-Za-z][A-Za-z0-9_]*)\s*(?:分页|页签|工作表|sheet|Sheet)",
        r"(?:Sheet|sheet)\s*[：:=为是]?\s*([A-Za-z][A-Za-z0-9_]*)",
    ]
    return _first_match(text, patterns)


def _extract_template_variable_columns(text: str) -> list[str]:
    value = _extract_template_value(text, ("变量选择", "变量"))
    if not value:
        return []
    return [
        item.strip()
        for item in value.replace("，", ",").split(",")
        if re.match(r"^[A-Za-z][A-Za-z0-9_]*$", item.strip())
    ]


def _extract_template_value(text: str, labels: tuple[str, ...]) -> str | None:
    text = _normalize_inline_template_labels(text)
    label_pattern = "|".join(re.escape(label) for label in labels)
    stop_labels = "|".join(re.escape(label) for label in TEMPLATE_LABELS)
    match = re.search(
        rf"(?:{label_pattern})\s*[：:=]\s*(.*?)(?=\s*(?:{stop_labels})\s*[：:=]|$)",
        text,
        re.IGNORECASE,
    )
    value = match.group(1).strip() if match else ""
    if not value or value in TEMPLATE_PLACEHOLDERS:
        return None
    return re.sub(r"[；;。]$", "", value).strip() or None


def _extract_template_sections(text: str) -> dict[str, str]:
    return extract_template_sections(text)


def _normalize_inline_template_labels(text: str) -> str:
    """允许用户把短模板写成一行，用逗号隔开不同标签。"""
    return normalize_inline_template_labels(text)


def _extract_rule_type_hint(sections: dict[str, str], text: str) -> str | None:
    explicit = _normalize_rule_type(sections.get("规则类型") or sections.get("rule_type"))
    return explicit or _infer_rule_type(text)


def _normalize_rule_type(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if not text or text in TEMPLATE_PLACEHOLDERS:
        return None
    for candidate in re.split(r"[/,，、；;\s]+", text):
        normalized = candidate.strip()
        if not normalized:
            continue
        if normalized in SUPPORTED_RULE_TYPES:
            return normalized
        alias = RULE_TYPE_ALIASES.get(normalized.lower()) or RULE_TYPE_ALIASES.get(normalized)
        if alias:
            return alias
    for alias, rule_type in RULE_TYPE_ALIASES.items():
        if alias in text:
            return rule_type
    for rule_type in SUPPORTED_RULE_TYPES:
        if rule_type in text:
            return rule_type
    return None


def _extract_template_field_value(value: str | None) -> str | None:
    if _is_empty_template_section(value):
        return None
    text = re.sub(r"(?:字段|列名|列)$", "", str(value).strip()).strip()
    match = re.search(FIELD_TOKEN_PATTERN, text)
    if match:
        return match.group(0)
    if re.match(r"^[A-Za-z][A-Za-z0-9_]*$", text) and text not in TEMPLATE_PLACEHOLDERS:
        return text
    return None


def _extract_template_reference(value: str | None) -> tuple[str | None, str | None]:
    if _is_empty_template_section(value):
        return None, None
    text = str(value).strip()
    tag_match = re.search(r"(\[[^\]\r\n]+\]|[A-Za-z0-9_\-]+\[[^\]\r\n]+\])", text)
    field_match = re.search(FIELD_TOKEN_PATTERN, text)
    return (
        tag_match.group(1).strip() if tag_match else None,
        field_match.group(0).strip() if field_match else None,
    )


def _extract_template_key_column(sections: dict[str, str]) -> str | None:
    explicit_key = _extract_template_field_value(
        sections.get("Key字段")
        or sections.get("Key 字段")
        or sections.get("Key值选择")
        or sections.get("Key选择")
        or sections.get("Key值")
        or sections.get("选择Key")
        or sections.get("Key")
        or sections.get("关联Key")
    )
    if explicit_key:
        return explicit_key
    for label in ("筛选", "筛选条件", "筛选规则1", "筛选规则2", "补充说明"):
        value = sections.get(label, "")
        if _is_empty_template_section(value):
            continue
        unique_field = _extract_unique_precondition_field(value)
        if unique_field:
            return unique_field
    return None


def _extract_template_filters(sections: dict[str, str]) -> list[AiRuleFilterHint]:
    filters: list[AiRuleFilterHint] = []
    for label in ("筛选", "筛选条件", "筛选规则1", "筛选规则2"):
        value = sections.get(label, "")
        if _is_empty_template_section(value) or _looks_like_dual_filter_text(value):
            continue
        for item in _split_filter_items(value):
            if _extract_unique_precondition_field(item):
                continue
            field, filter_value, operator = _parse_filter_expression_with_operator(item)
            if field and _filter_value_is_present(operator, filter_value):
                filter_hint = AiRuleFilterHint(
                    field=field,
                    operator=operator or "eq",
                    value=filter_value or "",
                )
                if filter_hint not in filters:
                    filters.append(filter_hint)
    return filters


def _split_filter_items(value: str) -> list[str]:
    text = str(value).replace("\r", "\n")
    lines = [
        re.sub(r"^\s*[-*]\s*", "", line).strip()
        for line in text.split("\n")
        if line.strip()
    ]
    if len(lines) > 1:
        return lines
    split_items = [
        item.strip()
        for item in re.split(
            r"[,，]\s*(?=[A-Za-z][A-Za-z0-9_]*\s*(?:字段)?\s*(?:唯一|不能重复|不可重复|unique|!=|=|>|<|等于|不等于|大于|小于|非空|不能为空|not\s*null|not_null))",
            text,
            flags=re.IGNORECASE,
        )
        if item.strip()
    ]
    if len(split_items) > 1:
        return split_items
    return [
        item.strip()
        for item in re.split(r"[；;]+", text)
        if item.strip()
    ] or ([text.strip()] if text.strip() else [])


def _extract_unique_precondition_field(value: str) -> str | None:
    if _is_empty_template_section(value):
        return None
    match = re.search(r"([A-Za-z][A-Za-z0-9_]*)\s*(?:字段)?\s*(?:唯一|不能重复|不可重复|unique)", value, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _extract_template_filter(sections: dict[str, str]) -> tuple[str | None, str | None, str | None]:
    for label in ("筛选", "筛选条件", "筛选规则1", "筛选规则2"):
        value = sections.get(label, "")
        if _is_empty_template_section(value):
            continue
        if label == "筛选条件" and _looks_like_dual_filter_text(value):
            continue
        if re.search(r"(?:唯一|不能重复|不可重复|必须重复|需要重复|至少一组重复|unique|duplicate_required)", value, re.IGNORECASE):
            continue
        field, filter_value, operator = _parse_filter_expression_with_operator(value)
        if field and _filter_value_is_present(operator, filter_value):
            return field, filter_value, operator
    return None, None, None


def _looks_like_dual_filter_text(value: str) -> bool:
    return bool(re.search(r"(?:左侧|右侧|left|right)", value, re.IGNORECASE))


def _is_empty_template_section(value: str | None) -> bool:
    if not value:
        return True
    return value.strip().lower() in {"无", "空", "none", "null", "-"}


def _looks_like_source_path_or_url(value: str) -> bool:
    return bool(
        re.search(r"^(https?:|svn:)", value, re.IGNORECASE)
        or re.search(r"^[A-Za-z]:[\\/]", value)
        or value.startswith("\\\\")
        or "/" in value
        or "\\" in value
        or re.search(r"\.xls[xm]?($|[?#])", value, re.IGNORECASE)
    )


def _extract_filter(text: str) -> tuple[str | None, str | None]:
    field, value, operator = _parse_filter_expression_with_operator(text)
    if field and _filter_value_is_present(operator, value):
        return field, value
    patterns = [
        r"(?:筛选规则\d*)\s*[：:=]\s*([A-Za-z][A-Za-z0-9_]*)\s*=\s*([^。；;\n\r]+)",
        r"(?:筛选|过滤)\s*([A-Za-z][A-Za-z0-9_]*)\s*=\s*([^。；;\n\r]+)",
        r"(?:筛选|过滤)[^。；;\n\r]*?([A-Za-z][A-Za-z0-9_]*)\s*(?:等于|为|是)\s*([^。；;\n\r]+)",
        r"(?:过滤掉|过滤|排除)[^，。；;]*?([A-Za-z][A-Za-z0-9_]*)\s*字段[^，。；;]*?(?:包含|含有)\s*[\"']?([^\"'，。；;、\s]+)",
        r"([A-Za-z][A-Za-z0-9_]*)\s*字段[^，。；;]*?(?:包含|含有)\s*[\"']?([^\"'，。；;、\s]+)[^，。；;]*?(?:过滤|排除)",
        r"([A-Za-z][A-Za-z0-9_]*)\s*=\s*([^,，。；;\s]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = _clean_filter_value(_trim_filter_tail(match.group(2)))
            if re.fullmatch(FIELD_TOKEN_PATTERN, value):
                continue
            return match.group(1).strip(), value
    return None, None


def _extract_filter_operator(
    text: str,
    filter_field: str | None,
    filter_value: str | None,
) -> str | None:
    if not filter_field:
        return None
    lowered = text.lower()
    if "不包含" in text or "过滤掉" in text or "排除" in text or "not_contains" in lowered or "not contains" in lowered:
        return "not_contains"
    if "包含" in text or "含有" in text or "contains" in lowered:
        return "contains"
    if any(keyword in text for keyword in ("不等于", "!=")):
        return "ne"
    if any(keyword in text for keyword in ("大于", ">")):
        return "gt"
    if any(keyword in text for keyword in ("小于", "<")):
        return "lt"
    if re.search(r"(?:非空|不能为空|not\s*null|not_null)", text, re.IGNORECASE):
        return "not_null"
    return "eq"


def _clean_filter_value(value: str) -> str:
    cleaned = _clean_set_value(value)
    return re.sub(r"(?:的)?(?:字段|列|行|数据|记录|配置)$", "", cleaned).strip() or cleaned


def _trim_filter_tail(value: str) -> str:
    """筛选值后面常直接接 Key/判断语义，先截断这些结构化片段。"""
    cleaned = value.strip()
    cleaned = re.split(
        r"(?:[,，]\s*)?(?:以|按)\s*[A-Za-z][A-Za-z0-9_]*\s*(?:字段)?\s*(?:为|作为)?\s*(?:Key|key|主键|唯一键)",
        cleaned,
        maxsplit=1,
    )[0]
    cleaned = re.split(r"(?:[,，]\s*)?(?:判断|比较|比对|校验|检查)\s*[：:]", cleaned, maxsplit=1)[0]
    cleaned = re.split(
        r"(?:[,，]\s*)?(?:Key值选择|Key选择|Key值|选择Key|最终判定|校验判定|判定|断言|校验规则)\s*[：:]",
        cleaned,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    cleaned = re.split(
        r"[,，]\s*[A-Za-z][A-Za-z0-9_]*\s*(?:=|!=|>|<|等于|不等于|大于|小于|必须等于字段|等于字段)",
        cleaned,
        maxsplit=1,
    )[0]
    return cleaned.strip()


def _extract_assertion_compare(
    text: str,
    *,
    filter_field: str | None,
    candidate_fields: list[str | None] | None = None,
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    candidate_field_set = {field for field in (candidate_fields or []) if field}
    field_compare_pattern = r"([A-Za-z][A-Za-z0-9_]*)\s*(?:字段)?\s*(=|等于字段|等于\s*字段|必须等于字段|不等于字段|大于字段|小于字段)\s*([A-Za-z][A-Za-z0-9_]*)\b"
    for field_compare in re.finditer(field_compare_pattern, text, re.IGNORECASE):
        field = field_compare.group(1).strip()
        expected_field = field_compare.group(3).strip()
        if not filter_field or field != filter_field:
            if (
                expected_field in candidate_field_set
                or field in candidate_field_set
                or re.fullmatch(FIELD_TOKEN_PATTERN, expected_field)
            ):
                return field, _operator_from_text(field_compare.group(2)), None, "field", expected_field
    patterns = [
        r"([A-Za-z][A-Za-z0-9_]*)\s*字段\s*(=|!=|>|<|等于|不等于|大于|小于)\s*([^。；;\n\r]+)",
        r"(?:校验|验证|检查)\s*([A-Za-z][A-Za-z0-9_]*)\s*字段\s*(等于|不等于|大于|小于|=|!=|>|<|为|是)\s*([^。；;\n\r]+)",
        r"([A-Za-z][A-Za-z0-9_]*)\s*字段\s*(等于|不等于|大于|小于|=|!=|>|<|为|是)\s*([^。；;\n\r]+)",
        r"([A-Za-z][A-Za-z0-9_]*)\s*(=|!=|>|<|等于|不等于|大于|小于)\s*([^。；;\n\r]+)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            field = match.group(1).strip()
            if filter_field and field == filter_field:
                continue
            operator = _operator_from_text(match.group(2))
            value = _clean_set_value(match.group(3))
            if re.fullmatch(FIELD_TOKEN_PATTERN, value):
                return field, operator, None, "field", value
            return field, operator, value, None, None
    set_style = re.search(
        r"([A-Za-z][A-Za-z0-9_]*)\s*(?:字段)?\s*(必须重复|需要重复|至少一组重复|至少重复|duplicate_required|唯一|不能重复|不可重复|unique)",
        text,
        re.IGNORECASE,
    )
    if set_style:
        operator_text = set_style.group(2).lower()
        operator = (
            "duplicate_required"
            if "重复" in set_style.group(2) and not any(keyword in set_style.group(2) for keyword in ("不能", "不可", "唯一"))
            or "duplicate_required" in operator_text
            else "unique"
        )
        return set_style.group(1).strip(), operator, None, None, None
    not_null = re.search(
        r"([A-Za-z][A-Za-z0-9_]*)\s*(?:字段)?\s*(?:不能为空|非空|必填|not\s*null|not_null)",
        text,
        re.IGNORECASE,
    )
    if not_null:
        return not_null.group(1).strip(), "not_null", None, None, None
    regex_match = re.search(
        r"([A-Za-z][A-Za-z0-9_]*)\s*(?:字段)?\s*(?:匹配正则|正则|regex)\s*[：:=]?\s*([^。；;\n\r]+)",
        text,
        re.IGNORECASE,
    )
    if regex_match:
        pattern = regex_match.group(2).strip()
        if pattern and not pattern.startswith(("校验", "检查")):
            return regex_match.group(1).strip(), "regex", pattern, None, None
    return None, None, None, None, None


def _extract_target_based_assertion(
    text: str,
    target_field: str,
) -> tuple[str | None, str | None, str | None, str | None, str | None] | None:
    if not text.strip():
        return None
    expected_field = _first_match(
        text,
        [
            r"(?:=|等于字段|等于\s*字段|必须等于字段|必须\s*等于\s*字段)\s*([A-Za-z][A-Za-z0-9_]*)\b",
        ],
    )
    if expected_field:
        return target_field, "eq", None, "field", expected_field
    for pattern, operator in (
        (r"(?:!=|不等于字段|不等于\s*字段)\s*([A-Za-z][A-Za-z0-9_]*)\b", "ne"),
        (r"(?:>|大于字段|大于\s*字段)\s*([A-Za-z][A-Za-z0-9_]*)\b", "gt"),
        (r"(?:<|小于字段|小于\s*字段)\s*([A-Za-z][A-Za-z0-9_]*)\b", "lt"),
    ):
        expected_field = _first_match(text, [pattern])
        if expected_field:
            return target_field, operator, None, "field", expected_field
    if re.search(r"(不能为空|非空|必填|not\s*null|not_null)", text, re.IGNORECASE):
        return target_field, "not_null", None, None, None
    if re.search(r"(必须重复|需要重复|至少一组重复|至少重复|duplicate_required)", text, re.IGNORECASE):
        return target_field, "duplicate_required", None, None, None
    if re.search(r"(唯一|不能重复|不可重复|unique)", text, re.IGNORECASE):
        return target_field, "unique", None, None, None
    regex_pattern = _extract_regex_pattern(text)
    if regex_pattern:
        return target_field, "regex", regex_pattern, None, None
    return None


def _clean_set_value(value: str) -> str:
    cleaned = value.strip().strip("\"'")
    cleaned = re.sub(r"\s+(?:or|OR)\s+", ",", cleaned)
    cleaned = cleaned.replace("，", ",").replace("、", ",")
    cleaned = re.sub(
        r"(?:,\s*)?(?:两种类型|两个类型|两类|两种|这些类型|这几种类型|多个类型|多个值)$",
        "",
        cleaned,
    )
    cleaned = re.sub(r"\s+", "", cleaned)
    cleaned = re.sub(r",+", ",", cleaned).strip(",")
    return cleaned


def _extract_display_field(text: str) -> str | None:
    return _first_match(
        text,
        [
            r"(?:结果显示|显示字段|展示字段|结果字段)\s*[：:=为是]?\s*([A-Za-z][A-Za-z0-9_]*)",
            r"([A-Za-z][A-Za-z0-9_]*)\s*(?:作为|为)\s*(?:结果显示|展示字段)",
        ],
    )


def _extract_target_field(
    text: str,
    *,
    filter_field: str | None,
    display_field: str | None,
    key_column: str | None,
    compare_fields: list[str],
) -> str | None:
    explicit = _first_match(
        text,
        [
            r"(?:校验|验证|检查)\s*([A-Za-z][A-Za-z0-9_]*)\s*字段",
            r"([A-Za-z][A-Za-z0-9_]*)\s*字段[^，。；;]*?(?:配置数据格式|配置格式|格式)",
            r"(?:目标字段|目标列名|校验字段)\s*[：:=为是]?\s*([A-Za-z][A-Za-z0-9_]*)",
        ],
    )
    if explicit and not _is_placeholder_key_column(explicit):
        return explicit

    excluded = {item for item in (filter_field, display_field, key_column, *compare_fields) if item}
    for candidate in re.findall(r"([A-Za-z][A-Za-z0-9_]*)\s*字段", text):
        if candidate not in excluded:
            return candidate
    return None


def _extract_key_column(text: str) -> str | None:
    explicit = _first_match(
        text,
        [
            r"([A-Za-z][A-Za-z0-9_]*)\s*(?:字段)?\s*(?:唯一|不能重复|不可重复|unique)",
            r"(?:关联\s*Key|业务\s*Key|比对\s*Key|对齐\s*Key|关联键|业务键|比对键|对齐键)\s*(?:列|字段)?\s*[：:=为是]?\s*([A-Za-z][A-Za-z0-9_]*)",
            r"(?:Key|key|索引|主键|唯一键)\s*(?:列|字段)?\s*[：:=为是]?\s*([A-Za-z][A-Za-z0-9_]*)",
            r"([A-Za-z][A-Za-z0-9_]*)\s*字段\s*(?:作为|为)\s*(?:Key|key|索引|主键|唯一键)",
            r"([A-Za-z][A-Za-z0-9_]*)\s*(?:作为|为)\s*(?:Key|key|索引|主键|唯一键)",
        ],
    )
    if explicit:
        return explicit
    match = re.search(r"\bINT_Id\b", text)
    return match.group(0) if match else None


def _extract_regex_pattern(text: str) -> str | None:
    explicit = _first_match(
        text,
        [
            r"(?:正则|regex|pattern)\s*[：:=]\s*([^。；;\n\r]+)",
        ],
    )
    if explicit:
        return explicit.strip().strip("\"'")
    if "冒号" in text and ("只能配置 1 或 0" in text or "只能配置1或0" in text):
        return SERVER_CONFIG_PATTERN
    if ("冒号" in text or ":" in text) and re.search(r"(?:1\s*(?:或|or|/)\s*0|0\s*(?:或|or|/)\s*1)", text, re.IGNORECASE):
        return SERVER_CONFIG_PATTERN
    if re.search(r"\d+\s*:\s*[01](?:\s*;\s*\d+\s*:\s*[01])+", text):
        return SERVER_CONFIG_PATTERN
    return None


def _infer_rule_type(text: str) -> str | None:
    for rule_type in SUPPORTED_RULE_TYPES:
        if re.search(rf"(^|\s){re.escape(rule_type)}(\s|$)", text, re.IGNORECASE):
            return rule_type
    raw_explicit = _first_match(
        text,
        [
            r"(?:规则类型|rule_type)\s*[：:=]\s*([^。；;\n\r]+)",
            r"(?:规则类型|rule_type)\s+([^。；;\n\r]+)",
        ],
    )
    if raw_explicit:
        for label in TEMPLATE_LABELS:
            if label in {"规则类型", "rule_type"}:
                continue
            raw_explicit = re.split(rf"\s*{re.escape(label)}\s*[：:=]", raw_explicit, maxsplit=1)[0]
    explicit = _normalize_rule_type(raw_explicit)
    if explicit:
        return explicit
    lowered = text.lower()
    if _looks_like_unsupported(text):
        return None
    if any(keyword in text for keyword in ("两组", "两个配置", "两份配置", "是不是相等", "是否相等")) and any(
        keyword in text for keyword in ("以", "key", "Key", "筛选")
    ):
        return "dual_composite_compare"
    if any(keyword in text for keyword in ("多组串行", "多节点串行", "多级链路", "链路", "pipeline")):
        return "multi_composite_pipeline_check"
    if any(keyword in text for keyword in ("多组映射", "多节点映射", "映射校验", "mapping")):
        return "multi_composite_mapping_check"
    if any(keyword in text for keyword in ("存在于", "字典表", "字典变量", "包含(in)", " in ")) and any(
        keyword in text for keyword in ("另一", "引用", "字典", "表")
    ):
        return "cross_table_mapping"
    if any(keyword in text for keyword in ("筛选", "过滤", "当", "如果")) and any(
        keyword in text for keyword in ("校验", "检查", "判断", "必须", "格式", "正则")
    ):
        return "composite_condition_check"
    if any(keyword in text for keyword in ("不能为空", "非空", "必填", "not null", "not_null")):
        return "not_null"
    if any(keyword in text for keyword in ("唯一", "不能重复", "不可重复", "unique")):
        return "unique"
    if any(keyword in text for keyword in ("升序", "降序", "递增", "递减", "连续", "步长", "顺序", "sequence")):
        return "sequence_order_check"
    if any(keyword in text for keyword in ("正则", "格式", "匹配", "regex")):
        return "regex_check"
    if any(keyword in text for keyword in ("等于", "不等于", "大于", "小于", "只能是", "必须是", "=", "!=", ">", "<")):
        return "fixed_value_compare"
    if "not_null" in lowered or "unique" in lowered:
        return "not_null" if "not_null" in lowered else "unique"
    return None


def _has_filter_assertion_pair(
    rule_type_hint: str | None,
    *,
    filter_field: str | None,
    filter_value: str | None,
    assertion_field: str | None,
    assertion_value: str | None,
    assertion_expected_field: str | None,
    assertion_operator: str | None = None,
    filter_operator: str | None = None,
) -> bool:
    if rule_type_hint in {
        "dual_composite_compare",
        "multi_composite_pipeline_check",
        "multi_composite_mapping_check",
        "cross_table_mapping",
    }:
        return False
    has_filter = bool(filter_field and (filter_value or filter_operator == "not_null"))
    return bool(has_filter and assertion_field and (assertion_value or assertion_expected_field or assertion_operator))


def _extract_labeled_variable_tag(text: str, labels: tuple[str, ...]) -> str | None:
    label_pattern = "|".join(re.escape(label) for label in labels)
    patterns = [
        rf"(?:{label_pattern})\s*[：:=]\s*(\[[^\]\r\n]+\])",
        rf"(?:{label_pattern})\s*[：:=]\s*([A-Za-z0-9_\-]+\[[^\]\r\n]+\])",
    ]
    return _first_match(text, patterns)


def _looks_like_unsupported(text: str) -> bool:
    return any(keyword in text for keyword in ("公式", "聚合", "平均", "求和", "脚本", "计算后", "跨行统计"))


def _extract_dual_filters(
    text: str,
) -> tuple[str | None, str | None, str | None, str | None, str | None, str | None]:
    left_section = _extract_template_value(text, ("左侧筛选", "筛选规则1"))
    right_section = _extract_template_value(text, ("右侧筛选", "筛选规则2"))
    left_filter = _parse_filter_expression_with_operator(left_section or "")
    right_filter = _parse_filter_expression_with_operator(right_section or "")
    if (
        left_filter[0]
        and _filter_value_is_present(left_filter[2], left_filter[1])
        and right_filter[0]
        and _filter_value_is_present(right_filter[2], right_filter[1])
        and left_filter[0] == right_filter[0]
    ):
        return left_filter[0], left_filter[2] or "eq", left_filter[1], right_filter[0], right_filter[2] or "eq", right_filter[1]

    filter_section = _extract_template_value(text, ("筛选", "筛选条件"))
    if filter_section:
        left_item = _first_match(filter_section, [r"(?:左侧|left)\s*([^；;\n\r]+)"])
        right_item = _first_match(filter_section, [r"(?:右侧|right)\s*([^；;\n\r]+)"])
        left_filter = _parse_filter_expression_with_operator(left_item or "")
        right_filter = _parse_filter_expression_with_operator(right_item or "")
        if (
            left_filter[0]
            and right_filter[0]
            and left_filter[0] == right_filter[0]
            and _filter_value_is_present(left_filter[2], left_filter[1])
            and _filter_value_is_present(right_filter[2], right_filter[1])
        ):
            return left_filter[0], left_filter[2] or "eq", left_filter[1], right_filter[0], right_filter[2] or "eq", right_filter[1]
        common_filter = _parse_filter_expression_with_operator(filter_section)
        split_values = _split_dual_filter_values(common_filter[1])
        if (
            _has_dual_compare_text_signal(text)
            and common_filter[0]
            and (common_filter[2] or "eq") == "eq"
            and split_values is not None
        ):
            return common_filter[0], "eq", split_values[0], common_filter[0], "eq", split_values[1]

    patterns = [
        r"筛选\s*[：:]?\s*[-*]?\s*([A-Za-z][A-Za-z0-9_]*)\s*(=|!=|>|<|等于|不等于|大于|小于)\s*([^和，。；;\s]+)\s*和\s*\1\s*(=|!=|>|<|等于|不等于|大于|小于)\s*([^，。；;\s]+)",
        r"筛选[^，。；;]*?([A-Za-z][A-Za-z0-9_]*)\s*(等于|不等于|大于|小于|=|!=|>|<)\s*([^和，。；;\s]+)\s*和\s*\1\s*(等于|不等于|大于|小于|=|!=|>|<)\s*([^，。；;\s]+)",
        r"(?:筛选|过滤)\s*[：:]?\s*[-*]?\s*([A-Za-z][A-Za-z0-9_]*)\s*=\s*([^,，。；;\s]+)\s*[,，]\s*([^,，。；;\s]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            field = match.group(1).strip()
            if len(match.groups()) >= 5:
                left_operator = _operator_from_text(match.group(2))
                right_operator = _operator_from_text(match.group(4))
                return field, left_operator, _clean_filter_value(match.group(3)), field, right_operator, _clean_filter_value(match.group(5))
            return field, "eq", _clean_filter_value(match.group(2)), field, "eq", _clean_filter_value(match.group(3))
    values = re.findall(r"([A-Za-z][A-Za-z0-9_]*)\s*(=|!=|>|<|等于|不等于|大于|小于)\s*([^,，和。；;\s]+)", text)
    if len(values) >= 2 and values[0][0] == values[1][0]:
        field = values[0][0].strip()
        return (
            field,
            _operator_from_text(values[0][1]),
            _clean_filter_value(values[0][2]),
            field,
            _operator_from_text(values[1][1]),
            _clean_filter_value(values[1][2]),
        )
    return None, None, None, None, None, None


def _split_dual_filter_values(value: str | None) -> tuple[str, str] | None:
    if not value:
        return None
    values = [
        item.strip()
        for item in re.split(r"[,，]", value)
        if item.strip()
    ]
    if len(values) != 2:
        return None
    return values[0], values[1]


def _parse_filter_expression(text: str) -> tuple[str | None, str | None]:
    field, value, _operator = _parse_filter_expression_with_operator(text)
    return field, value


def _parse_filter_expression_with_operator(text: str) -> tuple[str | None, str | None, str | None]:
    not_null_match = re.search(
        r"([A-Za-z][A-Za-z0-9_]*)\s*(?:字段)?\s*(?:非空|不能为空|not\s*null|not_null)",
        text,
        re.IGNORECASE,
    )
    if not_null_match:
        return not_null_match.group(1).strip(), "", "not_null"
    contains_match = re.search(
        r"([A-Za-z][A-Za-z0-9_]*)\s*(not_contains|not\s+contains|不包含|排除|过滤掉|contains|包含|含有)\s*([^。；;\n\r]+)",
        text,
        re.IGNORECASE,
    )
    if contains_match:
        operator_text = contains_match.group(2).lower()
        operator = (
            "not_contains"
            if operator_text in {"not_contains", "not contains"} or contains_match.group(2) in {"不包含", "排除", "过滤掉"}
            else "contains"
        )
        return (
            contains_match.group(1).strip(),
            _clean_filter_value(_trim_filter_tail(contains_match.group(3))),
            operator,
        )
    match = re.search(
        r"([A-Za-z][A-Za-z0-9_]*)\s*(?:!=|不等于|不能是|不可为|>=|<=|>|<|=|等于|为|是|大于|小于)\s*([^。；;\n\r]+)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None, None, None
    operator = _operator_from_text(match.group(0))
    return match.group(1).strip(), _clean_filter_value(_trim_filter_tail(match.group(2))), operator


def _filter_value_is_present(operator: str | None, value: str | None) -> bool:
    return operator == "not_null" or bool(value)


def _operator_from_text(text: str) -> str:
    if re.search(r"(?:!=|不等于|不能是|不可为)", text):
        return "ne"
    if re.search(r"(?:>=|大于等于|不小于)", text):
        return "gt"
    if re.search(r"(?:<=|小于等于|不大于)", text):
        return "lt"
    if re.search(r"(?:>|大于)", text):
        return "gt"
    if re.search(r"(?:<|小于)", text):
        return "lt"
    return "eq"


def _looks_like_dual_compare_shape(
    text: str,
    *,
    left_filter_field: str | None,
    left_filter_value: str | None,
    right_filter_field: str | None,
    right_filter_value: str | None,
    key_column: str | None,
    compare_fields: list[str],
) -> bool:
    if not (
        left_filter_field
        and left_filter_value
        and right_filter_field
        and right_filter_value
        and left_filter_field == right_filter_field
        and key_column
        and compare_fields
    ):
        return False
    has_compare_intent = any(keyword in text for keyword in ("相等", "一致", "相同", "不相等", "不一致"))
    has_compare_verb = any(keyword in text for keyword in ("判断", "比较", "比对", "校验", "检查", "判定", "断言"))
    has_key_intent = any(keyword in text for keyword in ("Key", "key", "主键", "唯一键", "对齐"))
    return has_compare_intent and has_compare_verb and has_key_intent


def _has_dual_compare_text_signal(text: str) -> bool:
    has_compare_intent = any(keyword in text for keyword in ("两组", "两个配置", "两份配置", "左右", "相等", "一致", "相同"))
    has_key_intent = any(keyword in text for keyword in ("Key", "key", "主键", "唯一键", "对齐"))
    return has_compare_intent and has_key_intent


def _extract_compare_fields(
    text: str,
    *,
    key_column: str | None,
    filter_fields: list[str | None],
    display_field: str | None,
) -> list[str]:
    explicit = _first_match(
        text,
        [
            r"(?:比较字段|比对字段)\s*[：:=]\s*([^。；;]+)",
            r"(?:判断|比较|比对|校验)([^。；;]*?)(?:这|的)?(?:四个|多个|这些)?字段",
            r"(?:四个|多个|这些)字段[：:=为是]?\s*([^。；;]+)",
        ],
    )
    source = explicit or text
    candidates = re.findall(FIELD_TOKEN_PATTERN, source)
    if explicit and not candidates:
        candidates = [
            item.strip()
            for item in re.split(r"[,，、/\s]+", explicit)
            if re.match(r"^[A-Za-z][A-Za-z0-9_]*$", item.strip())
        ]
    excluded = {item for item in [key_column, display_field, *filter_fields] if item}
    result: list[str] = []
    for candidate in candidates:
        if candidate in excluded or candidate in result:
            continue
        result.append(candidate)
    return result


def _extract_dual_compare_operator(text: str) -> str | None:
    if re.search(r"(?:非空|不能为空|not\s*null|not_null)", text, re.IGNORECASE):
        return "not_null"
    if re.search(r"(?:不相等|不一致|不等于|!=)", text):
        return "ne"
    if re.search(r"(?:大于|>)", text):
        return "gt"
    if re.search(r"(?:小于|<)", text):
        return "lt"
    if re.search(r"(?:相等|一致|相同|等于|=)", text):
        return "eq"
    return None


def _extract_key_check_mode(text: str) -> str | None:
    if re.search(r"(?:双向检查|双向校验|双向对比|两边都要有|左右都要有|bidirectional)", text, re.IGNORECASE):
        return "bidirectional"
    if re.search(r"(?:基准变量为准|以左侧为准|以基准为准|baseline_only)", text, re.IGNORECASE):
        return "baseline_only"
    return None


def _extract_multi_nodes(text: str, *, mode: str) -> list[dict[str, object]]:
    if mode == "pipeline" and "multi_composite_pipeline_check" not in text and "多组串行" not in text:
        return []
    if mode == "mapping" and "multi_composite_mapping_check" not in text and "多组映射" not in text:
        return []
    node_headers = list(re.finditer(r"(?:节点|node)\s*(\d+)\s*[：:=]?", text, re.IGNORECASE))
    nodes: list[dict[str, object]] = []
    for index, match in enumerate(node_headers):
        next_start = node_headers[index + 1].start() if index + 1 < len(node_headers) else len(text)
        body = text[match.end():next_start].strip(" ；;。")
        variable_tag = _first_match(body, [r"(?:变量|variable)\s*[：:=]\s*([A-Za-z0-9_\-\[\]]+)"])
        filter_text = _first_match(body, [r"筛选\s*[：:=]?\s*([^；;。]+)"]) or body
        assertion_text = _first_match(body, [r"断言\s*[：:=]?\s*([^；;。]+)"]) or body
        filter_field, filter_value, filter_operator = _parse_filter_expression_with_operator(filter_text)
        assertion_field, assertion_operator, assertion_value, assertion_value_source, assertion_expected_field = _extract_assertion_compare(
            assertion_text,
            filter_field=filter_field,
            candidate_fields=[],
        )
        filters: list[dict[str, str]] = []
        if filter_field and _filter_value_is_present(filter_operator, filter_value):
            filters.append(
                {
                    "field": filter_field,
                    "operator": filter_operator or "eq",
                    "value": filter_value or "",
                }
            )
        assertions: list[dict[str, str]] = []
        if assertion_field and assertion_operator:
            item = {
                "field": assertion_field,
                "operator": assertion_operator,
            }
            if assertion_value:
                item["expected_value"] = assertion_value
            if assertion_value_source == "field" and assertion_expected_field:
                item["value_source"] = "field"
                item["expected_field"] = assertion_expected_field
            assertions.append(item)
        if variable_tag or filters or assertions:
            nodes.append(
                {
                    "node_id": f"ai-node-{match.group(1)}",
                    "variable_tag": variable_tag or "",
                    "filters": filters,
                    "assertions": assertions,
                }
            )
    return nodes


def _build_composite_columns(
    *,
    key_column: str | None,
    display_field: str | None,
    target_field: str | None,
    filter_field: str | None,
    filter_fields: list[str],
    left_filter_field: str | None,
    right_filter_field: str | None,
    compare_fields: list[str],
) -> list[str]:
    columns: list[str] = []
    for value in (
        key_column,
        display_field,
        target_field,
        filter_field,
        *filter_fields,
        left_filter_field,
        right_filter_field,
        *compare_fields,
    ):
        if value and not _is_placeholder_key_column(value) and value not in columns:
            columns.append(value)
    return columns


def _dedupe_values(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _first_match(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


"""从自然语言规则描述中抽取 AI 工作流结构化线索。"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from backend.app.ai.schemas import AiRuleWorkflowHints


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
    normalized_text = _normalize_text(text)
    source_url = _extract_source_url(normalized_text)
    source_id = _derive_source_id(source_url)
    sheet = _extract_sheet(normalized_text)
    target_variable_tag = _extract_labeled_variable_tag(normalized_text, ("目标变量", "变量"))
    reference_variable_tag = _extract_labeled_variable_tag(normalized_text, ("引用变量", "字典变量"))
    left_variable_tag = _extract_labeled_variable_tag(normalized_text, ("左侧变量", "基准变量"))
    right_variable_tag = _extract_labeled_variable_tag(normalized_text, ("右侧变量", "对比变量"))
    left_filter_field, left_filter_value, right_filter_field, right_filter_value = _extract_dual_filters(
        normalized_text
    )
    filter_field, filter_value = _extract_filter(normalized_text)
    filter_operator = _extract_filter_operator(normalized_text, filter_field, filter_value)
    display_field = _extract_display_field(normalized_text)
    key_column = _extract_key_column(normalized_text)
    compare_fields = _extract_compare_fields(
        normalized_text,
        key_column=key_column,
        filter_fields=[filter_field, left_filter_field, right_filter_field],
        display_field=display_field,
    )
    rule_type_hint = _infer_rule_type(normalized_text)
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
    else:
        left_filter_field = None
        left_filter_value = None
        right_filter_field = None
        right_filter_value = None
    target_field = _extract_target_field(
        normalized_text,
        filter_field=filter_field,
        display_field=display_field,
        key_column=key_column if rule_type_hint != "dual_composite_compare" else None,
        compare_fields=compare_fields,
    )
    if rule_type_hint == "dual_composite_compare" and key_column:
        target_field = target_field or key_column
    regex_pattern = _extract_regex_pattern(normalized_text)
    operator, expected_value, expected_value_mode = _extract_fixed_value_compare(normalized_text)
    assertion_field, assertion_operator, assertion_value = _extract_assertion_compare(
        normalized_text,
        filter_field=filter_field,
    )
    if _has_filter_assertion_pair(
        rule_type_hint,
        filter_field=filter_field,
        filter_value=filter_value,
        assertion_field=assertion_field,
        assertion_value=assertion_value,
    ):
        rule_type_hint = "composite_condition_check"
    target_field = assertion_field or target_field
    sequence_direction, sequence_step, sequence_start_mode, sequence_start_value = _extract_sequence(
        normalized_text
    )
    if source_id == "server_config" and sheet == "switch" and target_field == "STR_ServersParam":
        rule_type_hint = "composite_condition_check"
        key_column = key_column or "INT_Id"
        display_field = display_field or "STR_Func"
        filter_field = filter_field or "DES"
        filter_value = filter_value or "废弃"
        filter_operator = filter_operator or "not_contains"
        regex_pattern = regex_pattern or SERVER_CONFIG_PATTERN
    composite_columns = _build_composite_columns(
        key_column=key_column,
        display_field=display_field,
        target_field=target_field,
        filter_field=filter_field,
        left_filter_field=left_filter_field,
        right_filter_field=right_filter_field,
        compare_fields=compare_fields,
    )

    return AiRuleWorkflowHints(
        rule_type_hint=rule_type_hint,
        target_variable_tag=target_variable_tag or left_variable_tag,
        reference_variable_tag=reference_variable_tag or right_variable_tag,
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
        assertion_field=assertion_field,
        assertion_operator=assertion_operator,
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
        left_filter_field=left_filter_field,
        left_filter_operator="eq" if left_filter_field and left_filter_value else None,
        left_filter_value=left_filter_value,
        right_filter_field=right_filter_field,
        right_filter_operator="eq" if right_filter_field and right_filter_value else None,
        right_filter_value=right_filter_value,
        left_key_field=key_column if rule_type_hint == "dual_composite_compare" else None,
        right_key_field=key_column if rule_type_hint == "dual_composite_compare" else None,
        compare_fields=compare_fields,
    )


def _normalize_text(text: str) -> str:
    return (
        text.replace("\r", " ")
        .replace("\n", " ")
        .replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
        .strip()
    )


def _extract_source_url(text: str) -> str | None:
    match = re.search(r"https?://[A-Za-z0-9_./:%?=&~#+-]+\.xls[xm]?", text, re.IGNORECASE)
    return match.group(0) if match else None


def _extract_sheet(text: str) -> str | None:
    patterns = [
        r"\$?\s*([A-Za-z][A-Za-z0-9_]*)\s*(?:分页|页签|工作表|sheet|Sheet)",
        r"(?:Sheet|sheet)\s*[：:=为是]?\s*([A-Za-z][A-Za-z0-9_]*)",
    ]
    return _first_match(text, patterns)


def _extract_filter(text: str) -> tuple[str | None, str | None]:
    patterns = [
        r"(?:筛选|过滤)\s*([A-Za-z][A-Za-z0-9_]*)\s*=\s*([^。；;\n\r]+)",
        r"(?:筛选|过滤)[^。；;\n\r]*?([A-Za-z][A-Za-z0-9_]*)\s*(?:等于|为|是)\s*([^。；;\n\r]+)",
        r"(?:过滤掉|过滤|排除)[^，。；;]*?([A-Za-z][A-Za-z0-9_]*)\s*字段[^，。；;]*?(?:包含|含有)\s*[\"']?([^\"'，。；;、\s]+)",
        r"([A-Za-z][A-Za-z0-9_]*)\s*字段[^，。；;]*?(?:包含|含有)\s*[\"']?([^\"'，。；;、\s]+)[^，。；;]*?(?:过滤|排除)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip(), _clean_filter_value(_trim_filter_tail(match.group(2)))
    return None, None


def _extract_filter_operator(
    text: str,
    filter_field: str | None,
    filter_value: str | None,
) -> str | None:
    if not filter_field or not filter_value:
        return None
    if "不包含" in text or "过滤掉" in text or "排除" in text:
        return "not_contains"
    if "包含" in text or "含有" in text:
        return "contains"
    if any(keyword in text for keyword in ("不等于", "!=")):
        return "ne"
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
    return cleaned.strip()


def _extract_assertion_compare(
    text: str,
    *,
    filter_field: str | None,
) -> tuple[str | None, str | None, str | None]:
    patterns = [
        r"([A-Za-z][A-Za-z0-9_]*)\s*字段\s*=\s*([^。；;\n\r]+)",
        r"(?:校验|验证|检查)\s*([A-Za-z][A-Za-z0-9_]*)\s*字段\s*(?:等于|为|是)\s*([^。；;\n\r]+)",
        r"([A-Za-z][A-Za-z0-9_]*)\s*字段\s*(?:等于|为|是)\s*([^。；;\n\r]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        field = match.group(1).strip()
        if filter_field and field == filter_field:
            continue
        return field, "eq", _clean_set_value(match.group(2))
    return None, None, None


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
    if "冒号" in text and ("只能配置 1 或 0" in text or "只能配置1或0" in text):
        return SERVER_CONFIG_PATTERN
    if ("冒号" in text or ":" in text) and re.search(r"(?:1\s*(?:或|or|/)\s*0|0\s*(?:或|or|/)\s*1)", text, re.IGNORECASE):
        return SERVER_CONFIG_PATTERN
    if re.search(r"\d+\s*:\s*[01](?:\s*;\s*\d+\s*:\s*[01])+", text):
        return SERVER_CONFIG_PATTERN
    return None


def _infer_rule_type(text: str) -> str | None:
    explicit = _first_match(
        text,
        [
            r"(?:规则类型|rule_type)\s*[：:=]\s*([A-Za-z_]+)",
            r"(?:规则类型|rule_type)\s+([A-Za-z_]+)",
        ],
    )
    if explicit in {
        "not_null",
        "unique",
        "regex_check",
        "sequence_order_check",
        "fixed_value_compare",
        "cross_table_mapping",
        "composite_condition_check",
        "dual_composite_compare",
        "multi_composite_pipeline_check",
        "multi_composite_mapping_check",
    }:
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
) -> bool:
    if rule_type_hint in {
        "dual_composite_compare",
        "multi_composite_pipeline_check",
        "multi_composite_mapping_check",
        "cross_table_mapping",
    }:
        return False
    return bool(filter_field and filter_value and assertion_field and assertion_value)


def _extract_labeled_variable_tag(text: str, labels: tuple[str, ...]) -> str | None:
    label_pattern = "|".join(re.escape(label) for label in labels)
    patterns = [
        rf"(?:{label_pattern})\s*[：:=]\s*(\[[^\]\r\n]+\])",
        rf"(?:{label_pattern})\s*[：:=]\s*([A-Za-z0-9_\-]+\[[^\]\r\n]+\])",
    ]
    return _first_match(text, patterns)


def _looks_like_unsupported(text: str) -> bool:
    return any(keyword in text for keyword in ("公式", "聚合", "平均", "求和", "脚本", "计算后", "跨行统计"))


def _extract_dual_filters(text: str) -> tuple[str | None, str | None, str | None, str | None]:
    patterns = [
        r"筛选\s*([A-Za-z][A-Za-z0-9_]*)\s*=\s*([^和，。；;\s]+)\s*和\s*\1\s*=\s*([^，。；;\s]+)",
        r"筛选[^，。；;]*?([A-Za-z][A-Za-z0-9_]*)\s*(?:等于|为|是)\s*([^和，。；;\s]+)\s*和\s*\1\s*(?:等于|为|是)\s*([^，。；;\s]+)",
        r"(?:筛选|过滤)\s*([A-Za-z][A-Za-z0-9_]*)\s*=\s*([^,，。；;\s]+)\s*[,，]\s*([^,，。；;\s]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            field = match.group(1).strip()
            return field, _clean_filter_value(match.group(2)), field, _clean_filter_value(match.group(3))
    values = re.findall(r"([A-Za-z][A-Za-z0-9_]*)\s*=\s*([^,，和。；;\s]+)", text)
    if len(values) >= 2 and values[0][0] == values[1][0]:
        field = values[0][0].strip()
        return field, _clean_filter_value(values[0][1]), field, _clean_filter_value(values[1][1])
    return None, None, None, None


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
    has_compare_verb = any(keyword in text for keyword in ("判断", "比较", "比对", "校验", "检查"))
    has_key_intent = any(keyword in text for keyword in ("Key", "key", "主键", "唯一键", "对齐"))
    return has_compare_intent and has_compare_verb and has_key_intent


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
            r"(?:判断|比较|比对|校验)([^。；;]*?)(?:这|的)?(?:四个|多个|这些)?字段",
            r"(?:四个|多个|这些)字段[：:=为是]?\s*([^。；;]+)",
        ],
    )
    source = explicit or text
    candidates = re.findall(FIELD_TOKEN_PATTERN, source)
    excluded = {item for item in [key_column, display_field, *filter_fields] if item}
    result: list[str] = []
    for candidate in candidates:
        if candidate in excluded or candidate in result:
            continue
        result.append(candidate)
    return result


def _extract_fixed_value_compare(text: str) -> tuple[str | None, str | None, str | None]:
    patterns = [
        (r"(?:只能是|必须是|等于|为|是)\s*[\"']?([^\"'，。；;、\s]+)", "eq"),
        (r"(?:不等于|不能是|不可为|!=)\s*[\"']?([^\"'，。；;、\s]+)", "ne"),
        (r"(?:大于|>)\s*[\"']?([^\"'，。；;、\s]+)", "gt"),
        (r"(?:小于|<)\s*[\"']?([^\"'，。；;、\s]+)", "lt"),
    ]
    for pattern, operator in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if _looks_like_meta_expected_value(value):
                continue
            mode = "set" if "," in value or "，" in value or "或" in value else "single"
            return operator, value.replace("，", ","), mode
    return None, None, None


def _looks_like_meta_expected_value(value: str) -> bool:
    return value.startswith(("更适合", "适合")) or value in {"AI", "ai", "解析"}


def _extract_sequence(text: str) -> tuple[str | None, str | None, str | None, str | None]:
    direction = None
    if any(keyword in text for keyword in ("降序", "递减")):
        direction = "desc"
    elif any(keyword in text for keyword in ("升序", "递增", "连续", "顺序")):
        direction = "asc"
    step_match = re.search(r"步长\s*[：:=为是]?\s*(\d+)", text)
    start_match = re.search(r"(?:起始值|从)\s*[：:=为是]?\s*(\d+)", text)
    return (
        direction,
        step_match.group(1) if step_match else None,
        "manual" if start_match else ("auto" if direction else None),
        start_match.group(1) if start_match else None,
    )


def _build_composite_columns(
    *,
    key_column: str | None,
    display_field: str | None,
    target_field: str | None,
    filter_field: str | None,
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
        left_filter_field,
        right_filter_field,
        *compare_fields,
    ):
        if value and not _is_placeholder_key_column(value) and value not in columns:
            columns.append(value)
    return columns


def _first_match(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _derive_source_id(source_url: str | None) -> str | None:
    if not source_url:
        return None
    raw_name = urlparse(source_url).path.rstrip("/").split("/")[-1]
    stem = raw_name.rsplit(".", 1)[0] if "." in raw_name else raw_name
    source_id = re.sub(r"[^A-Za-z0-9_]+", "_", stem).strip("_")
    return source_id or None


def _guess_source_type(source_url: str | None) -> str | None:
    if not source_url:
        return None
    if source_url.lower().startswith(("http://", "https://", "svn://")):
        return "svn"
    return "local_excel"

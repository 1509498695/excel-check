"""Value, comparison, and sequence extractors."""

from __future__ import annotations

import re


def extract_fixed_value_compare(text: str) -> tuple[str | None, str | None, str | None]:
    """Extract fixed-value comparison operator/value/mode."""
    if re.search(r"(?:等于\s*字段|必须\s*等于\s*字段)", text, re.IGNORECASE):
        return None, None, None
    if re.search(r"(不能为空|非空|必填|not\s*null|not_null)", text, re.IGNORECASE) and not re.search(
        r"(期望值|比较值|固定值|只能是|必须是|等于|不等于|大于|小于|!=|>|<)",
        text,
        re.IGNORECASE,
    ):
        return None, None, None
    patterns = [
        (r"(?:期望值|比较值|固定值)\s*[：:=]\s*[\"']?([^\"'，。；;、\s]+)", "eq"),
        (r"(?:只能是|必须是|等于|为|是)\s*[\"']?([^\"'，。；;、\s]+)", "eq"),
        (r"(?:不等于|不能是|不可为|!=)\s*[\"']?([^\"'，。；;、\s]+)", "ne"),
        (r"(?:大于|>)\s*[\"']?([^\"'，。；;、\s]+)", "gt"),
        (r"(?:小于|<)\s*[\"']?([^\"'，。；;、\s]+)", "lt"),
    ]
    for pattern, operator in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if looks_like_meta_expected_value(value):
                continue
            mode = "set" if "," in value or "，" in value or "或" in value else "single"
            return operator, value.replace("，", ","), mode
    return None, None, None


def extract_sequence(text: str) -> tuple[str | None, str | None, str | None, str | None]:
    """Extract sequence direction, step, start mode, and start value."""
    direction = None
    if any(keyword in text for keyword in ("降序", "递减", "方向=降序", "方向：降序")):
        direction = "desc"
    elif any(keyword in text for keyword in ("升序", "递增", "连续", "顺序", "方向=升序", "方向：升序")):
        direction = "asc"
    step_match = re.search(r"步长\s*[：:=为是]?\s*(\d+)", text)
    start_match = re.search(r"(?:起始值|起始|从)\s*[：:=为是]?\s*(\d+)", text)
    auto_start = bool(re.search(r"(?:起始值|起始)\s*[：:=为是]?\s*(?:自动|auto)", text, re.IGNORECASE))
    return (
        direction,
        step_match.group(1) if step_match else None,
        "manual" if start_match else ("auto" if auto_start or direction else None),
        start_match.group(1) if start_match else None,
    )


def looks_like_meta_expected_value(value: str) -> bool:
    """Return whether a value is prompt/meta text rather than a real expected value."""
    return value.startswith(("更适合", "适合")) or value in {"AI", "ai", "解析"}

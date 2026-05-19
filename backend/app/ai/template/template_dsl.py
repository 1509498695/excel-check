"""Short-template DSL helpers for AI smart-rule descriptions."""

from __future__ import annotations

import re

from backend.app.ai.template.labels import TEMPLATE_LABELS


def normalize_text(text: str) -> str:
    """Normalize whitespace and quotes while preserving current parser semantics."""
    return (
        text.replace("\r", " ")
        .replace("\n", " ")
        .replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
        .strip()
    )


def normalize_inline_template_labels(text: str) -> str:
    """Allow short templates to be written on one line with comma-separated labels."""
    label_pattern = "|".join(re.escape(label) for label in TEMPLATE_LABELS)
    return re.sub(
        rf"([,，；;]\s*)({label_pattern})\s*[：:=]",
        lambda match: f"\n{match.group(2)}：",
        text,
        flags=re.IGNORECASE,
    )


def extract_template_sections(text: str) -> dict[str, str]:
    """Parse current short-template labels into sections without changing label meanings."""
    normalized = normalize_inline_template_labels(text)
    label_pattern = "|".join(re.escape(label) for label in TEMPLATE_LABELS)
    sections: dict[str, list[str]] = {}
    current_label: str | None = None
    for raw_line in normalized.replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(rf"^({label_pattern})\s*[：:=]\s*(.*)$", line, re.IGNORECASE)
        if match:
            current_label = match.group(1)
            sections.setdefault(current_label, []).append(match.group(2).strip())
        elif current_label:
            sections[current_label].append(line)
    return {
        label: re.sub(r"[；;。]$", "", "\n".join(value for value in values if value).strip())
        for label, values in sections.items()
        if any(value.strip() for value in values)
    }

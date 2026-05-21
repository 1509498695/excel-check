"""固定规则分组归一化。"""

from __future__ import annotations

from backend.app.api.fixed_rules_schemas import FixedRuleGroup, UNGROUPED_GROUP_ID
from backend.app.fixed_rules.config_common import _build_default_group, _normalize_group_name


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

"""AI 规则草稿生成与确定性编译服务。"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.ai.hint_extractor import extract_workflow_hints_from_text
from backend.app.ai.prompts import (
    SUPPORTED_RULE_TYPES,
    build_prompt_optimize_system_prompt,
    build_prompt_optimize_user_prompt,
    build_system_prompt,
    build_user_prompt,
    get_rule_intent_json_schema,
    get_rule_prompt_optimize_json_schema,
)
from backend.app.ai.providers import ProviderConnectionError, call_provider_json
from backend.app.ai.rule_candidate import critique_rule_candidate
from backend.app.ai.schemas import (
    AiProviderPreset,
    AiRuleFilterHint,
    AiRuleWorkflowHints,
    MissingItem,
    RuleDraftPayload,
    RuleDraftResponse,
    RuleIntent,
    RulePromptOptimizeClues,
    RulePromptOptimizeResponse,
    VariableIntent,
)
from backend.app.api.fixed_rules_schemas import FixedRuleDefinition, FixedRuleGroup
from backend.app.api.schemas import DataSource, VariableTag
from backend.app.loaders.local_reader import read_source_metadata
from backend.app.models import AiProviderCredentialRecord, AiRuleDraftRecord, WorkbenchConfigRecord
from backend.app.security.crypto import decrypt_secret


DEFAULT_GROUP_ID = "ungrouped"
DEFAULT_GROUP_NAME = "未分组"
DRAFT_HISTORY_LIMIT = 20
VALID_MISSING_KINDS = {"source", "variable", "rule", "parameter", "ability"}
VALID_MISSING_ACTIONS = {
    "open_source_dialog",
    "open_single_variable_dialog",
    "open_composite_variable_dialog",
    "edit_description",
    "none",
}


class AiProviderNotConfigured(ValueError):
    """当前用户尚未配置 AI 供应商。"""


class AiProviderInvalid(ValueError):
    """当前用户的 AI 凭据无法解密。"""


async def optimize_rule_prompt(
    *,
    db: AsyncSession,
    project_id: int,
    user_id: int,
    raw_description: str,
    selected_variable_tags: list[str],
    allow_auto_complete: bool = False,
    context: dict[str, Any] | None = None,
) -> RulePromptOptimizeResponse:
    """优化智能规则输入文本；不生成草稿、不写历史、不改配置。"""
    description = (raw_description or "").strip()
    if not description:
        return RulePromptOptimizeResponse(
            status="needs_input",
            raw_description=description,
            missing=["请先输入规则描述。"],
            warnings=["优化输入前需要先填写规则描述。"],
            fallback=True,
        )

    selected_tags = _normalize_selected_variable_tags(selected_variable_tags, workflow_hints=None)
    if not selected_tags and not allow_auto_complete:
        fallback = _build_prompt_optimize_fallback(
            description,
            selected_variables=[],
            warnings=["未选择目标变量，建议先选择变量以提高解析准确率。"],
            require_selected_variables=True,
        )
        fallback.status = "needs_input"
        fallback.missing = ["请先选择一个或多个目标变量。"]
        return fallback

    workbench_context = await _load_workbench_context(db, project_id, user_id)
    selected_variables, unknown_tags = _resolve_selected_prompt_variables(
        workbench_context,
        selected_tags,
    )
    fallback = _build_prompt_optimize_fallback(
        description,
        selected_variables=selected_variables,
        require_selected_variables=not allow_auto_complete,
    )
    if unknown_tags:
        fallback.status = "needs_input"
        fallback.missing = [f"变量池中不存在：{', '.join(unknown_tags)}。"]
        fallback.warnings.append("请重新选择当前变量池中已存在的目标变量。")
        return fallback

    try:
        credential = await _load_user_credential(db, user_id)
        api_key = _decrypt_credential_key(credential)
        raw_result, _meta = await call_provider_json(
            provider_preset=credential.provider_preset,  # type: ignore[arg-type]
            base_url=credential.base_url,
            model=credential.model,
            api_key=api_key,
            system_prompt=build_prompt_optimize_system_prompt(),
            user_prompt=build_prompt_optimize_user_prompt(
                raw_description=description,
                selected_variables=_prompt_variable_metadata(selected_variables),
                rule_library=_rule_library_summary(),
                deterministic_clues=fallback.detected_clues.model_dump(exclude_none=True),
                context={**(context or {}), "allow_auto_complete": allow_auto_complete},
            ),
            json_schema=get_rule_prompt_optimize_json_schema(),
            extra_headers=_parse_extra_headers(credential.extra_headers_json),
            timeout_seconds=20.0,
        )
        response = RulePromptOptimizeResponse.model_validate(raw_result)
    except (AiProviderNotConfigured, AiProviderInvalid, ProviderConnectionError, ValidationError) as exc:
        fallback.status = "failed"
        fallback.fallback = True
        fallback.warnings.append(_prompt_optimize_failure_message(exc))
        return fallback

    response.raw_description = response.raw_description or description
    if not response.optimized_description.strip():
        fallback.status = "failed"
        fallback.warnings.append("模型没有返回可用的优化描述，已展示兜底优化结果。")
        return fallback
    response.optimized_description = _coerce_optimized_description_to_template(
        response.optimized_description,
        fallback=fallback.optimized_description,
    )
    response.fallback = False
    return response


async def generate_rule_draft(
    *,
    db: AsyncSession,
    project_id: int,
    user_id: int,
    description: str,
    extra_hints: str | None = None,
    workflow_hints: AiRuleWorkflowHints | None = None,
    input_mode: str = "free_text",
    allow_auto_complete: bool = True,
    selected_variable_tags: list[str] | None = None,
) -> RuleDraftResponse:
    """生成规则草稿，持久化历史，并返回前端可展示的结果。"""
    credential = await _load_user_credential(db, user_id)
    api_key = _decrypt_credential_key(credential)
    context = await _load_workbench_context(db, project_id, user_id)
    effective_workflow_hints = _merge_workflow_hints(
        workflow_hints,
        extract_workflow_hints_from_text(description),
    )
    selected_tags = _normalize_selected_variable_tags(
        selected_variable_tags,
        workflow_hints=effective_workflow_hints,
    )
    candidate_critique = critique_rule_candidate(
        description,
        workflow_hints=effective_workflow_hints,
    )
    if candidate_critique.verdict == "ready":
        effective_workflow_hints = candidate_critique.workflow_hints
    has_effective_workflow_hints = _has_workflow_hints(effective_workflow_hints)
    critique_extra_hints = candidate_critique.prompt_summary()
    merged_extra_hints = "\n\n".join(
        item for item in (extra_hints, critique_extra_hints) if item
    )
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(
        description=description,
        context=context["prompt_context"],
        extra_hints=merged_extra_hints,
        workflow_hints=(
            effective_workflow_hints.model_dump(exclude_none=True)
            if has_effective_workflow_hints
            else None
        ),
        input_mode=input_mode,
        allow_auto_complete=allow_auto_complete,
        selected_variable_tags=selected_tags,
    )

    response = None
    if candidate_critique.should_stop:
        response = RuleDraftResponse(
            verdict=candidate_critique.verdict,
            rule_type=candidate_critique.rule_type,
            confidence=candidate_critique.confidence,
            reasoning_summary=candidate_critique.reasoning_summary,
            missing=candidate_critique.missing,
            rejection_reason=candidate_critique.rejection_reason,
        )

    if (
        response is None
        and allow_auto_complete
        and has_effective_workflow_hints
        and _workflow_hints_have_minimum_auto_complete_template(
            effective_workflow_hints,
            description=description,
        )
        and not _description_mentions_unsupported_rule(description)
    ):
        response = _compile_with_workflow_hints(
            RuleIntent(verdict="needs_input", confidence=0.72, reasoning_summary=""),
            workflow_hints=effective_workflow_hints,
            context=context,
            description=description,
            selected_variable_tags=selected_tags,
            allow_auto_complete=allow_auto_complete,
        )
        if response is not None and response.verdict == "ready":
            response.reasoning_summary = _prepend_deterministic_ready_summary(response.reasoning_summary)
        else:
            response = None

    try:
        if response is None:
            raw_intent, _meta = await call_provider_json(
                provider_preset=credential.provider_preset,  # type: ignore[arg-type]
                base_url=credential.base_url,
                model=credential.model,
                api_key=api_key,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                json_schema=get_rule_intent_json_schema(),
                extra_headers=_parse_extra_headers(credential.extra_headers_json),
            )
            intent = RuleIntent.model_validate(_normalize_raw_rule_intent(raw_intent))
            response = _compile_intent(intent, context=context, description=description)
            if has_effective_workflow_hints and (
                response.verdict == "needs_input" or not allow_auto_complete
            ):
                hinted_response = _compile_with_workflow_hints(
                    intent,
                    workflow_hints=effective_workflow_hints,
                    context=context,
                    description=description,
                    selected_variable_tags=selected_tags,
                    allow_auto_complete=allow_auto_complete,
                )
                if hinted_response is not None and hinted_response.verdict == "ready":
                    response = hinted_response
                elif hinted_response is not None and response.verdict == "needs_input":
                    if hinted_response.verdict == "needs_input" and response.missing:
                        existing_messages = {item.message for item in response.missing}
                        response.missing.extend(
                            item for item in hinted_response.missing if item.message not in existing_messages
                        )
                        response.reasoning_summary = hinted_response.reasoning_summary
                    else:
                        response = hinted_response
    except ProviderConnectionError as exc:
        response = None
        if has_effective_workflow_hints:
            response = _compile_with_workflow_hints(
                RuleIntent(verdict="needs_input", confidence=0, reasoning_summary=""),
                workflow_hints=effective_workflow_hints,
                context=context,
                description=description,
                selected_variable_tags=selected_tags,
                allow_auto_complete=allow_auto_complete,
            )
            if response is not None and response.verdict == "ready":
                response.reasoning_summary = "大模型调用超时，已根据结构化线索生成可预校验草稿。"
        if response is None:
            response = RuleDraftResponse(
                verdict="rejected",
                reasoning_summary="大模型调用失败，未能生成可用草稿。",
                rejection_reason=exc.message,
            )
    except ValidationError as exc:
        response = None
        if has_effective_workflow_hints:
            response = _compile_with_workflow_hints(
                RuleIntent(verdict="needs_input", confidence=0, reasoning_summary=""),
                workflow_hints=effective_workflow_hints,
                context=context,
                description=description,
                selected_variable_tags=selected_tags,
                allow_auto_complete=allow_auto_complete,
            )
            if response is not None and response.verdict == "ready":
                response.reasoning_summary = "模型输出不符合协议，已根据自然语言线索生成可预校验草稿。"
        if response is None:
            response = RuleDraftResponse(
                verdict="rejected",
                reasoning_summary="模型输出不符合 Excel Check 协议。",
                rejection_reason=f"模型输出字段不合法：{_summarize_validation_error(exc)}",
            )

    response = _enforce_variable_scope(
        response,
        context=context,
        selected_variable_tags=selected_tags,
        allow_auto_complete=allow_auto_complete,
    )
    response = _attach_extension_suggestions(response, description=description)
    response.description = description

    record = await _persist_draft_history(
        db,
        project_id=project_id,
        user_id=user_id,
        description=description,
        response=response,
    )
    response.draft_id = record.id
    response.created_at = _format_dt(record.created_at)
    return response


def _normalize_raw_rule_intent(raw_intent: Any) -> Any:
    """修正常见模型输出包装字段，其余核心规则协议继续交给 Pydantic 严格校验。"""
    if not isinstance(raw_intent, dict):
        return raw_intent
    normalized = {**raw_intent}
    for wrapper_key in ("parameters", "params", "arguments"):
        normalized.pop(wrapper_key, None)
    normalized["missing"] = _normalize_missing_items(raw_intent.get("missing"))
    for key in ("target", "reference"):
        if key in normalized:
            normalized[key] = _normalize_raw_variable_intent(normalized[key])
    return normalized


def _normalize_raw_variable_intent(raw_variable: Any) -> Any:
    if isinstance(raw_variable, str):
        return {"tag": raw_variable}
    if not isinstance(raw_variable, dict):
        return raw_variable

    normalized = {**raw_variable}
    nested_variable = normalized.pop("variable", None)
    if isinstance(nested_variable, dict):
        normalized = {**nested_variable, **normalized}

    alias_map = {
        "variable_tag": "tag",
        "target_variable_tag": "tag",
        "reference_variable_tag": "tag",
        "pathOrUrl": "path_or_url",
        "path": "path_or_url",
        "url": "path_or_url",
        "source_url": "path_or_url",
        "kind": "variable_kind",
    }
    for source_key, target_key in alias_map.items():
        if source_key in normalized and target_key not in normalized:
            normalized[target_key] = normalized.pop(source_key)
        else:
            normalized.pop(source_key, None)
    if _is_placeholder_key_column(normalized.get("key_column")):
        normalized["key_column"] = None
    if isinstance(normalized.get("columns"), list):
        normalized["columns"] = [
            str(column).strip()
            for column in normalized["columns"]
            if isinstance(column, str)
            and column.strip()
            and not _is_placeholder_key_column(column)
        ]
    return normalized


def _merge_workflow_hints(
    explicit_hints: AiRuleWorkflowHints | None,
    extracted_hints: AiRuleWorkflowHints,
) -> AiRuleWorkflowHints:
    """合并前端线索与后端自然语言抽取结果，显式线索优先。"""
    if explicit_hints is None:
        return _sanitize_workflow_hints(extracted_hints)
    merged = AiRuleWorkflowHints(
        rule_type_hint=explicit_hints.rule_type_hint or extracted_hints.rule_type_hint,
        target_variable_tag=_first_text(
            explicit_hints.target_variable_tag,
            extracted_hints.target_variable_tag,
        ),
        reference_variable_tag=_first_text(
            explicit_hints.reference_variable_tag,
            extracted_hints.reference_variable_tag,
        ),
        left_variable_tag=_first_text(
            explicit_hints.left_variable_tag,
            extracted_hints.left_variable_tag,
        ),
        right_variable_tag=_first_text(
            explicit_hints.right_variable_tag,
            extracted_hints.right_variable_tag,
        ),
        source_id=_first_text(explicit_hints.source_id, extracted_hints.source_id),
        source_type=explicit_hints.source_type or extracted_hints.source_type,
        source_url=_first_text(explicit_hints.source_url, extracted_hints.source_url),
        sheet=_first_text(explicit_hints.sheet, extracted_hints.sheet),
        target_field=_first_text(explicit_hints.target_field, extracted_hints.target_field),
        display_field=_first_text(explicit_hints.display_field, extracted_hints.display_field),
        filter_field=_first_text(explicit_hints.filter_field, extracted_hints.filter_field),
        filter_operator=explicit_hints.filter_operator or extracted_hints.filter_operator,
        filter_value=_first_text(explicit_hints.filter_value, extracted_hints.filter_value),
        filters=(
            explicit_hints.filters
            if explicit_hints.filters
            else extracted_hints.filters
        ),
        assertion_field=_first_text(explicit_hints.assertion_field, extracted_hints.assertion_field),
        assertion_operator=explicit_hints.assertion_operator or extracted_hints.assertion_operator,
        assertion_value_source=explicit_hints.assertion_value_source or extracted_hints.assertion_value_source,
        assertion_expected_field=_first_text(
            explicit_hints.assertion_expected_field,
            extracted_hints.assertion_expected_field,
        ),
        assertion_value=_first_text(explicit_hints.assertion_value, extracted_hints.assertion_value),
        operator=explicit_hints.operator or extracted_hints.operator,
        expected_value=_first_text(explicit_hints.expected_value, extracted_hints.expected_value),
        expected_value_mode=explicit_hints.expected_value_mode or extracted_hints.expected_value_mode,
        regex_pattern=_first_text(explicit_hints.regex_pattern, extracted_hints.regex_pattern),
        sequence_direction=explicit_hints.sequence_direction or extracted_hints.sequence_direction,
        sequence_step=_first_text(explicit_hints.sequence_step, extracted_hints.sequence_step),
        sequence_start_mode=explicit_hints.sequence_start_mode or extracted_hints.sequence_start_mode,
        sequence_start_value=_first_text(
            explicit_hints.sequence_start_value,
            extracted_hints.sequence_start_value,
        ),
        key_column=_first_text(explicit_hints.key_column, extracted_hints.key_column),
        composite_columns=(
            explicit_hints.composite_columns
            if explicit_hints.composite_columns
            else extracted_hints.composite_columns
        ),
        reference_source_id=_first_text(
            explicit_hints.reference_source_id,
            extracted_hints.reference_source_id,
        ),
        reference_source_type=explicit_hints.reference_source_type or extracted_hints.reference_source_type,
        reference_source_url=_first_text(
            explicit_hints.reference_source_url,
            extracted_hints.reference_source_url,
        ),
        reference_sheet=_first_text(explicit_hints.reference_sheet, extracted_hints.reference_sheet),
        reference_field=_first_text(explicit_hints.reference_field, extracted_hints.reference_field),
        reference_key_column=_first_text(
            explicit_hints.reference_key_column,
            extracted_hints.reference_key_column,
        ),
        reference_composite_columns=(
            explicit_hints.reference_composite_columns
            if explicit_hints.reference_composite_columns
            else extracted_hints.reference_composite_columns
        ),
        left_filter_field=_first_text(
            explicit_hints.left_filter_field,
            extracted_hints.left_filter_field,
        ),
        left_filter_operator=explicit_hints.left_filter_operator or extracted_hints.left_filter_operator,
        left_filter_value=_first_text(
            explicit_hints.left_filter_value,
            extracted_hints.left_filter_value,
        ),
        right_filter_field=_first_text(
            explicit_hints.right_filter_field,
            extracted_hints.right_filter_field,
        ),
        right_filter_operator=explicit_hints.right_filter_operator or extracted_hints.right_filter_operator,
        right_filter_value=_first_text(
            explicit_hints.right_filter_value,
            extracted_hints.right_filter_value,
        ),
        left_key_field=_first_text(explicit_hints.left_key_field, extracted_hints.left_key_field),
        right_key_field=_first_text(explicit_hints.right_key_field, extracted_hints.right_key_field),
        compare_operator=explicit_hints.compare_operator or extracted_hints.compare_operator,
        key_check_mode=explicit_hints.key_check_mode or extracted_hints.key_check_mode,
        compare_fields=(
            explicit_hints.compare_fields
            if explicit_hints.compare_fields
            else extracted_hints.compare_fields
        ),
        pipeline_nodes=(
            explicit_hints.pipeline_nodes
            if explicit_hints.pipeline_nodes
            else extracted_hints.pipeline_nodes
        ),
        mapping_nodes=(
            explicit_hints.mapping_nodes
            if explicit_hints.mapping_nodes
            else extracted_hints.mapping_nodes
        ),
    )
    if (
        merged.source_id == "server_config"
        and merged.sheet == "switch"
        and merged.target_field == "STR_ServersParam"
        and merged.filter_field == "DES"
        and merged.filter_value == "废弃"
    ):
        merged.filter_operator = "not_contains"
    return _sanitize_workflow_hints(merged)


def _sanitize_workflow_hints(workflow_hints: AiRuleWorkflowHints) -> AiRuleWorkflowHints:
    """清理优化提示词里的占位 Key，避免把说明文字当成真实列。"""
    updates: dict[str, Any] = {}
    for attr in (
        "key_column",
        "reference_key_column",
        "left_key_field",
        "right_key_field",
        "assertion_expected_field",
        "compare_operator",
        "key_check_mode",
    ):
        value = getattr(workflow_hints, attr)
        if _is_placeholder_key_column(value):
            updates[attr] = None

    for attr in ("composite_columns", "reference_composite_columns", "compare_fields"):
        values = getattr(workflow_hints, attr)
        if not isinstance(values, list):
            continue
        cleaned = [
            item.strip()
            for item in values
            if isinstance(item, str) and item.strip() and not _is_placeholder_key_column(item)
        ]
        if cleaned != values:
            updates[attr] = cleaned

    cleaned_filters: list[AiRuleFilterHint] = []
    for raw_item in workflow_hints.filters:
        item = _coerce_filter_hint(raw_item)
        if item is None:
            continue
        if _is_placeholder_key_column(item.field) or (item.operator != "not_null" and not item.value.strip()):
            continue
        if item not in cleaned_filters:
            cleaned_filters.append(item)
    if cleaned_filters != workflow_hints.filters:
        updates["filters"] = cleaned_filters

    return workflow_hints.model_copy(update=updates) if updates else workflow_hints


def _coerce_filter_hint(value: Any) -> AiRuleFilterHint | None:
    if isinstance(value, AiRuleFilterHint):
        return value
    if isinstance(value, dict):
        try:
            return AiRuleFilterHint.model_validate(value)
        except ValidationError:
            return None
    return None


def _normalize_selected_variable_tags(
    selected_variable_tags: list[str] | None,
    *,
    workflow_hints: AiRuleWorkflowHints | None,
) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in [
        *(selected_variable_tags or []),
        workflow_hints.target_variable_tag if workflow_hints else None,
        workflow_hints.reference_variable_tag if workflow_hints else None,
        workflow_hints.left_variable_tag if workflow_hints else None,
        workflow_hints.right_variable_tag if workflow_hints else None,
    ]:
        tag = value.strip() if isinstance(value, str) else ""
        if tag and tag not in seen:
            seen.add(tag)
            result.append(tag)
    return result


def _has_workflow_hints(workflow_hints: AiRuleWorkflowHints) -> bool:
    payload = workflow_hints.model_dump(exclude_none=True)
    return any(value for value in payload.values())


def _workflow_hints_have_minimum_auto_complete_template(
    workflow_hints: AiRuleWorkflowHints,
    *,
    description: str,
) -> bool:
    """固定模板线索完整时可先走确定性编译，降低模型输出波动。"""
    has_source = bool(workflow_hints.source_id or workflow_hints.source_url)
    has_sheet = bool(workflow_hints.sheet)
    has_fields = bool(
        workflow_hints.target_field
        or workflow_hints.assertion_field
        or workflow_hints.filters
        or workflow_hints.composite_columns
        or workflow_hints.compare_fields
    )
    has_rule = bool(_infer_hint_rule_type(
        RuleIntent(verdict="needs_input", confidence=0, reasoning_summary=""),
        workflow_hints,
        description,
    ))
    return has_source and has_sheet and has_fields and has_rule


def _description_mentions_unsupported_rule(description: str) -> bool:
    return any(
        keyword in description
        for keyword in ("公式", "聚合", "平均", "求和", "脚本", "计算后", "跨行统计")
    )


def _prepend_deterministic_ready_summary(summary: str) -> str:
    prefix = "已优先根据固定模板、结构化线索或自然语言线索生成可预校验草稿。"
    text = summary.strip()
    if not text or text == prefix:
        return prefix
    if text.startswith("已优先根据固定模板"):
        return text
    return f"{prefix} {text}"


def _normalize_missing_items(raw_missing: Any) -> list[dict[str, Any]]:
    if raw_missing is None:
        return []
    if isinstance(raw_missing, dict):
        candidates = [raw_missing]
    elif isinstance(raw_missing, list):
        candidates = raw_missing
    else:
        candidates = [raw_missing]

    items: list[dict[str, Any]] = []
    for candidate in candidates:
        if isinstance(candidate, dict):
            message = _string_or_default(candidate.get("message"), "配置缺口需要补充。")
            prefill = candidate.get("prefill")
            if not isinstance(prefill, dict):
                prefill = {}
            kind = _normalize_missing_kind(candidate.get("kind"), message, candidate, prefill)
            suggested_action = _normalize_missing_action(
                candidate.get("suggested_action"),
                kind,
                prefill,
            )
        else:
            message = _string_or_default(candidate, "配置缺口需要补充。")
            prefill = {}
            kind = _infer_missing_kind(message=message, action=None, prefill=prefill)
            suggested_action = _infer_missing_action(kind, prefill)
        items.append(
            {
                "kind": kind,
                "message": message,
                "suggested_action": suggested_action,
                "prefill": prefill,
            }
        )
    return items


def _normalize_missing_kind(
    raw_kind: Any,
    message: str,
    raw_item: dict[str, Any],
    prefill: dict[str, Any],
) -> str:
    kind = raw_kind.strip() if isinstance(raw_kind, str) else ""
    if kind in VALID_MISSING_KINDS:
        return kind
    action = raw_item.get("suggested_action")
    return _infer_missing_kind(message=message, action=action, prefill=prefill)


def _infer_missing_kind(
    *,
    message: str,
    action: Any,
    prefill: dict[str, Any],
) -> str:
    if action == "open_source_dialog":
        return "source"
    if action in {"open_single_variable_dialog", "open_composite_variable_dialog"}:
        return "variable"

    text = message.lower()
    if any(keyword in text for keyword in ("数据源", "source", "svn", "url", "文件", "路径")):
        return "source"
    if any(keyword in text for keyword in ("变量", "字段", "列", "sheet", "工作表", "column")):
        return "variable"
    if any(keyword in text for keyword in ("规则类型", "rule_type", "规则")):
        return "rule"
    if any(keyword in text for keyword in ("能力", "不支持", "无法表达", "不能表达", "unsupported")):
        return "ability"
    if any(key in prefill for key in ("sheet", "column", "columns", "key_column")):
        return "variable"
    if any(key in prefill for key in ("source_id", "pathOrUrl", "path_or_url", "url")):
        return "source"
    return "parameter"


def _normalize_missing_action(
    raw_action: Any,
    kind: str,
    prefill: dict[str, Any],
) -> str:
    action = raw_action.strip() if isinstance(raw_action, str) else ""
    if action in VALID_MISSING_ACTIONS:
        return action
    return _infer_missing_action(kind, prefill)


def _infer_missing_action(kind: str, prefill: dict[str, Any]) -> str:
    if kind == "source":
        return "open_source_dialog"
    if kind == "variable":
        if prefill.get("variable_kind") == "composite" or any(
            key in prefill for key in ("columns", "key_column")
        ):
            return "open_composite_variable_dialog"
        if any(key in prefill for key in ("sheet", "column", "source_id")):
            return "open_single_variable_dialog"
        return "edit_description"
    if kind in {"rule", "parameter"}:
        return "edit_description"
    return "none"


def _string_or_default(value: Any, default: str) -> str:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or default
    if value is None:
        return default
    return str(value).strip() or default


async def list_rule_drafts(
    *,
    db: AsyncSession,
    project_id: int,
    user_id: int,
    limit: int = DRAFT_HISTORY_LIMIT,
) -> list[RuleDraftResponse]:
    """读取当前用户当前项目最近的 AI 草稿历史。"""
    normalized_limit = max(1, min(DRAFT_HISTORY_LIMIT, limit))
    result = await db.execute(
        select(AiRuleDraftRecord)
        .where(
            AiRuleDraftRecord.project_id == project_id,
            AiRuleDraftRecord.user_id == user_id,
        )
        .order_by(AiRuleDraftRecord.created_at.desc(), AiRuleDraftRecord.id.desc())
        .limit(normalized_limit)
    )
    records = result.scalars().all()
    items: list[RuleDraftResponse] = []
    for record in records:
        try:
            payload = json.loads(record.response_json)
            item = RuleDraftResponse.model_validate(payload)
        except (json.JSONDecodeError, ValidationError):
            item = RuleDraftResponse(
                verdict=record.verdict,  # type: ignore[arg-type]
                rule_type=record.rule_type,  # type: ignore[arg-type]
                reasoning_summary="历史草稿格式已过期，无法完整展示。",
                rejection_reason="历史草稿格式已过期。",
            )
        item.draft_id = record.id
        item.description = record.description
        item.applied = record.applied
        item.created_at = _format_dt(record.created_at)
        items.append(item)
    return items


async def mark_draft_applied(
    *,
    db: AsyncSession,
    project_id: int,
    user_id: int,
    draft_id: int,
) -> bool:
    """把某条草稿标记为已应用。"""
    record = await _get_owned_draft(db, project_id, user_id, draft_id)
    if record is None:
        return False
    record.applied = True
    record.applied_at = datetime.now(timezone.utc)
    db.add(record)
    await db.commit()
    return True


async def delete_draft(
    *,
    db: AsyncSession,
    project_id: int,
    user_id: int,
    draft_id: int,
) -> bool:
    """删除某条草稿历史。"""
    record = await _get_owned_draft(db, project_id, user_id, draft_id)
    if record is None:
        return False
    await db.delete(record)
    await db.commit()
    return True


async def clear_drafts(
    *,
    db: AsyncSession,
    project_id: int,
    user_id: int,
) -> int:
    """清空当前用户当前项目草稿历史。"""
    result = await db.execute(
        delete(AiRuleDraftRecord).where(
            AiRuleDraftRecord.project_id == project_id,
            AiRuleDraftRecord.user_id == user_id,
        )
    )
    await db.commit()
    return int(result.rowcount or 0)


async def _load_user_credential(
    db: AsyncSession, user_id: int
) -> AiProviderCredentialRecord:
    result = await db.execute(
        select(AiProviderCredentialRecord).where(AiProviderCredentialRecord.user_id == user_id)
    )
    credential = result.scalar_one_or_none()
    if credential is None:
        raise AiProviderNotConfigured("请先在个人设置中配置 AI 模型。")
    return credential


def _decrypt_credential_key(credential: AiProviderCredentialRecord) -> str:
    try:
        return decrypt_secret(credential.encrypted_api_key)
    except ValueError as exc:
        raise AiProviderInvalid("AI 凭据已损坏，请重新填写 API Key。") from exc


async def _load_workbench_context(
    db: AsyncSession,
    project_id: int,
    user_id: int,
) -> dict[str, Any]:
    result = await db.execute(
        select(WorkbenchConfigRecord).where(
            WorkbenchConfigRecord.project_id == project_id,
            WorkbenchConfigRecord.user_id == user_id,
        )
    )
    record = result.scalar_one_or_none()
    raw_config: dict[str, Any] = {}
    if record is not None:
        try:
            parsed = json.loads(record.config_json)
            raw_config = parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            raw_config = {}

    sources = _validate_list(raw_config.get("sources"), DataSource)
    variables = _validate_list(raw_config.get("variables"), VariableTag)
    groups = _validate_list(raw_config.get("ruleGroups"), FixedRuleGroup)
    rules = _validate_list(raw_config.get("orchestrationRules"), FixedRuleDefinition)
    source_metadata = _read_safe_source_metadata(sources)

    prompt_context = {
        "sources": [
            {
                "id": source.id,
                "type": source.type,
                "locator": source.pathOrUrl or source.path or source.url or "",
                "sheets": source_metadata.get(source.id, {}).get("sheets", []),
            }
            for source in sources
        ],
        "variables": [
            {
                "tag": variable.tag,
                "source_id": variable.source_id,
                "sheet": variable.sheet,
                "variable_kind": variable.variable_kind,
                "column": variable.column,
                "columns": variable.columns,
                "key_column": variable.key_column,
                "expected_type": variable.expected_type,
            }
            for variable in variables
        ],
        "rules": [
            {
                "rule_id": rule.rule_id,
                "rule_name": rule.rule_name,
                "rule_type": rule.rule_type,
                "target_variable_tag": rule.target_variable_tag,
            }
            for rule in rules
        ],
    }
    return {
        "sources": sources,
        "variables": variables,
        "groups": groups or [FixedRuleGroup(group_id=DEFAULT_GROUP_ID, group_name=DEFAULT_GROUP_NAME, builtin=True)],
        "rules": rules,
        "source_metadata": source_metadata,
        "prompt_context": prompt_context,
    }


def _resolve_selected_prompt_variables(
    context: dict[str, Any],
    selected_tags: list[str],
) -> tuple[list[VariableTag], list[str]]:
    variables = {
        variable.tag: variable
        for variable in context.get("variables", [])
        if isinstance(variable, VariableTag)
    }
    selected_variables: list[VariableTag] = []
    unknown_tags: list[str] = []
    for tag in selected_tags:
        variable = variables.get(tag)
        if variable is None:
            unknown_tags.append(tag)
        else:
            selected_variables.append(variable)
    return selected_variables, unknown_tags


def _prompt_variable_metadata(variables: list[VariableTag]) -> list[dict[str, Any]]:
    """只暴露变量池元数据，不包含任何业务单元格值。"""
    return [
        {
            "tag": variable.tag,
            "name": variable.tag,
            "variable_type": variable.variable_kind or "single",
            "source_id": variable.source_id,
            "sheet_name": variable.sheet,
            "column_name": variable.column,
            "columns": variable.columns or [],
            "key_column": variable.key_column,
            "data_type": variable.expected_type,
        }
        for variable in variables
    ]


def _rule_library_summary() -> list[dict[str, str]]:
    labels = {
        "not_null": "非空校验",
        "unique": "唯一校验",
        "regex_check": "正则校验",
        "sequence_order_check": "顺序校验",
        "fixed_value_compare": "固定值比较",
        "cross_table_mapping": "包含(in) 字典映射",
        "composite_condition_check": "组合分支校验",
        "dual_composite_compare": "跨组变量校验",
        "multi_composite_pipeline_check": "多组串行校验",
        "multi_composite_mapping_check": "多组映射校验",
    }
    return [
        {
            "type": rule_type,
            "name": labels.get(rule_type, rule_type),
            "description": "当前 Excel Check 已支持的规则类型。",
        }
        for rule_type in SUPPORTED_RULE_TYPES
    ]


def _build_prompt_optimize_fallback(
    raw_description: str,
    *,
    selected_variables: list[VariableTag],
    warnings: list[str] | None = None,
    require_selected_variables: bool = True,
) -> RulePromptOptimizeResponse:
    hints = extract_workflow_hints_from_text(raw_description)
    critique = critique_rule_candidate(raw_description, workflow_hints=hints)
    if critique.verdict == "ready":
        hints = critique.workflow_hints
    hints, correction_warnings, unresolved_fields = _canonicalize_workflow_hints_fields(
        hints,
        selected_variables[0] if selected_variables else None,
    )
    clues = _prompt_optimize_clues_from_hints(hints, selected_variables)
    missing = _prompt_optimize_missing_items(
        hints,
        selected_variables,
        require_selected_variables=require_selected_variables,
    )
    missing.extend(f"请确认变量池中不存在或不明确的字段：{field}。" for field in unresolved_fields)
    optimized = _format_fallback_optimized_description(
        raw_description,
        selected_variables=selected_variables,
        hints=hints,
        clues=clues,
        missing=missing,
    )
    all_warnings = list(warnings or ["已基于本地规则做兜底优化，结果仅供参考。"])
    all_warnings.extend(item for item in correction_warnings if item not in all_warnings)
    return RulePromptOptimizeResponse(
        status="failed",
        raw_description=raw_description,
        optimized_description=optimized,
        detected_clues=clues,
        missing=missing,
        warnings=all_warnings,
        fallback=True,
    )


def _prompt_optimize_clues_from_hints(
    hints: AiRuleWorkflowHints,
    selected_variables: list[VariableTag],
) -> RulePromptOptimizeClues:
    filters: list[dict[str, Any]] = []
    for raw_item in hints.filters:
        item = _coerce_filter_hint(raw_item)
        if item is None:
            continue
        filters.append(
            {
                "field": item.field,
                "operator": item.operator or "eq",
                "value": item.value,
                "side": "global",
            }
        )
    if hints.filter_field and hints.filter_value and not any(
        item.get("field") == hints.filter_field and item.get("value") == hints.filter_value for item in filters
    ):
        filters.append(
            {
                "field": hints.filter_field,
                "operator": hints.filter_operator or "eq",
                "value": hints.filter_value,
                "side": "global",
            }
        )
    if hints.left_filter_field and hints.left_filter_value:
        filters.append(
            {
                "field": hints.left_filter_field,
                "operator": hints.left_filter_operator or "eq",
                "value": hints.left_filter_value,
                "side": "left",
            }
        )
    if hints.right_filter_field and hints.right_filter_value:
        filters.append(
            {
                "field": hints.right_filter_field,
                "operator": hints.right_filter_operator or "eq",
                "value": hints.right_filter_value,
                "side": "right",
            }
        )
    compare_operator = hints.compare_operator or (hints.operator if hints.operator in {"eq", "ne", "gt", "lt"} else None)
    compare_fields = list(hints.compare_fields)
    if hints.assertion_value_source == "field" and hints.assertion_expected_field:
        compare_fields = _unique_texts([hints.assertion_field, hints.assertion_expected_field, *compare_fields])
    if compare_operator is None and compare_fields:
        compare_operator = "eq"
    return RulePromptOptimizeClues(
        rule_type_hint=hints.rule_type_hint,
        involved_variables=[variable.tag for variable in selected_variables],
        target_field=hints.assertion_field or hints.target_field,
        key_field=hints.key_column or hints.left_key_field or hints.right_key_field,
        filters=filters,
        compare_fields=compare_fields,
        compare_operator=compare_operator,  # type: ignore[arg-type]
    )


def _prompt_optimize_missing_items(
    hints: AiRuleWorkflowHints,
    selected_variables: list[VariableTag],
    *,
    require_selected_variables: bool = True,
) -> list[str]:
    missing: list[str] = []
    if not selected_variables and require_selected_variables:
        missing.append("请先选择一个或多个目标变量。")
    elif not selected_variables and not (
        (hints.source_id or hints.source_url) and hints.sheet and hints.composite_columns
    ):
        missing.append("请确认数据源、Sheet、字段和变量标签；AI 校验时可尝试自动补齐。")
    if not hints.rule_type_hint:
        missing.append("请确认期望规则类型或判断关系。")
    if hints.rule_type_hint == "dual_composite_compare":
        if not (hints.left_filter_field and hints.left_filter_value and hints.right_filter_field and hints.right_filter_value):
            missing.append("请确认左右两组筛选条件。")
        if not (hints.key_column or hints.left_key_field or hints.right_key_field):
            missing.append("请确认用于对齐两组数据的 Key 字段。")
        if not hints.compare_fields:
            missing.append("请确认需要比较的字段列表。")
    if hints.rule_type_hint == "composite_condition_check" and not (
        hints.assertion_field or hints.target_field
    ):
        missing.append("请确认需要校验的目标字段。")
    return missing


def _format_fallback_optimized_description(
    raw_description: str,
    *,
    selected_variables: list[VariableTag],
    hints: AiRuleWorkflowHints,
    clues: RulePromptOptimizeClues,
    missing: list[str],
) -> str:
    selected_fields = _selected_prompt_variable_fields(selected_variables)
    target_field = hints.assertion_field or hints.target_field or clues.target_field or (selected_fields[0] if selected_fields else "")
    summary_hints = hints.model_copy(update={"target_field": target_field}) if target_field and not (hints.target_field or hints.assertion_field) else hints
    return _format_dsl_optimized_description(
        raw_description,
        hints=summary_hints,
        rule_type_hint=clues.rule_type_hint or hints.rule_type_hint,
        key_field=clues.key_field or hints.key_column or hints.left_key_field or hints.right_key_field,
        compare_fields=clues.compare_fields or hints.compare_fields,
        missing=missing,
    )


def _format_dsl_optimized_description(
    raw_description: str,
    *,
    hints: AiRuleWorkflowHints,
    rule_type_hint: str | None,
    key_field: str | None,
    compare_fields: list[str],
    missing: list[str],
) -> str:
    rule_type = rule_type_hint or hints.rule_type_hint or "需要用户确认：规则类型"
    rule_type = _normalize_prompt_dsl_rule_type(rule_type, hints)
    if rule_type == "dual_composite_compare":
        fields = ", ".join(_dedupe_prompt_values(compare_fields or hints.compare_fields)) or "需要用户确认：比较字段"
        key = key_field or hints.key_column or hints.left_key_field or hints.right_key_field or "需要用户确认：Key"
        return "\n".join(
            [
                "dual_composite_compare",
                f"左侧筛选：{_format_single_filter_text(hints.left_filter_field, hints.left_filter_operator, hints.left_filter_value)}",
                f"右侧筛选：{_format_single_filter_text(hints.right_filter_field, hints.right_filter_operator, hints.right_filter_value)}",
                f"Key：{key}",
                f"比较字段：{fields}",
                "断言：左右两组按 Key 对齐后比较字段必须相等",
                *_format_missing_dsl_lines(missing),
            ]
        ).strip()

    if rule_type == "composite_condition_check":
        target = hints.assertion_field or hints.target_field or "需要用户确认：目标字段"
        key = key_field or hints.key_column or "无"
        filter_lines = _format_global_filter_lines(hints, key_field=key if key != "无" else None)
        assertion = _format_dsl_assertion(hints, target_field=target, raw_description=raw_description)
        return "\n".join(
            [
                "composite_condition_check",
                "筛选：",
                *(filter_lines or ["- 无"]),
                f"Key：{key}",
                f"断言：{assertion}",
                *_format_missing_dsl_lines(missing),
            ]
        ).strip()

    target = hints.assertion_field or hints.target_field or "需要用户确认：目标字段"
    return "\n".join(
        [
            str(rule_type),
            f"目标：{target}",
            f"断言：{_format_dsl_assertion(hints, target_field=target, raw_description=raw_description)}",
            *_format_missing_dsl_lines(missing),
        ]
    ).strip()


def _format_missing_dsl_lines(missing: list[str]) -> list[str]:
    return [f"需要用户确认：{'；'.join(missing)}"] if missing else []


def _format_global_filter_lines(hints: AiRuleWorkflowHints, *, key_field: str | None) -> list[str]:
    lines: list[str] = []
    for raw_item in hints.filters:
        item = _coerce_filter_hint(raw_item)
        if item is None:
            continue
        line = f"- {_format_single_filter_text(item.field, item.operator, item.value)}"
        if line not in lines:
            lines.append(line)
    if hints.filter_field and hints.filter_value:
        line = f"- {_format_single_filter_text(hints.filter_field, hints.filter_operator, hints.filter_value)}"
        if line not in lines:
            lines.append(line)
    if key_field:
        key_line = f"- {key_field} 唯一"
        if key_line not in lines:
            lines.append(key_line)
    return lines


def _format_single_filter_text(field: str | None, operator: str | None, value: str | None) -> str:
    if not field:
        return "需要用户确认：筛选条件"
    if operator == "not_null":
        return f"{field} 非空"
    if not value:
        return "需要用户确认：筛选条件"
    operator_label = {
        "eq": "=",
        "ne": "!=",
        "gt": ">",
        "lt": "<",
        "contains": "包含",
        "not_contains": "不包含",
    }.get(operator or "eq", operator or "=")
    return f"{field} {operator_label} {value}"


def _normalize_prompt_dsl_rule_type(rule_type: str, hints: AiRuleWorkflowHints) -> str:
    """优化输入展示用：无组合上下文时保留简单规则类型，避免把简单断言包成组合 DSL。"""
    if rule_type != "composite_condition_check":
        return rule_type
    has_composite_context = bool(
        hints.filters
        or hints.filter_field
        or hints.display_field
        or hints.key_column
        or hints.assertion_expected_field
        or hints.assertion_value_source == "field"
    )
    if has_composite_context:
        return rule_type
    if hints.rule_type_hint in {
        "not_null",
        "unique",
        "fixed_value_compare",
        "regex_check",
        "sequence_order_check",
        "cross_table_mapping",
    }:
        return hints.rule_type_hint
    if hints.assertion_operator == "not_null":
        return "not_null"
    if hints.assertion_operator == "unique":
        return "unique"
    if hints.assertion_operator == "regex" or hints.regex_pattern:
        return "regex_check"
    if hints.assertion_operator in {"eq", "ne", "gt", "lt"} or hints.assertion_value or hints.expected_value:
        return "fixed_value_compare"
    return rule_type


def _format_dsl_assertion(
    hints: AiRuleWorkflowHints,
    *,
    target_field: str,
    raw_description: str,
) -> str:
    operator_label = {
        "eq": "等于",
        "ne": "不等于",
        "gt": "大于",
        "lt": "小于",
        "not_null": "不能为空",
        "regex": "匹配正则",
        "unique": "不能重复",
        "duplicate_required": "必须重复",
    }
    if hints.assertion_value_source == "field" and hints.assertion_expected_field:
        return f"{target_field} 等于字段 {hints.assertion_expected_field}"
    if hints.assertion_operator in {"not_null", "unique", "duplicate_required"}:
        return f"{target_field} {operator_label.get(hints.assertion_operator, hints.assertion_operator)}"
    if hints.assertion_operator == "regex" or hints.regex_pattern:
        regex = hints.regex_pattern or hints.assertion_value or "需要用户确认：正则"
        return f"{target_field} 匹配正则 {regex}"
    compare_operator = hints.assertion_operator or hints.operator
    expected = hints.assertion_value or hints.expected_value
    if compare_operator and expected:
        return f"{target_field} {operator_label.get(compare_operator, compare_operator)} {expected}"
    if hints.rule_type_hint == "not_null":
        return f"{target_field} 不能为空"
    if hints.rule_type_hint == "unique":
        return f"{target_field} 不能重复"
    natural_rule = _extract_natural_rule_from_text(raw_description)
    return natural_rule or "需要用户确认：最终断言"


def _coerce_optimized_description_to_template(optimized_description: str, *, fallback: str) -> str:
    text = optimized_description.strip()
    if not text:
        return fallback
    fallback_hints = extract_workflow_hints_from_text(fallback)
    model_hints = extract_workflow_hints_from_text(text)
    rule_type_hint = model_hints.rule_type_hint or fallback_hints.rule_type_hint
    key_field = (
        model_hints.key_column
        or model_hints.left_key_field
        or model_hints.right_key_field
        or fallback_hints.key_column
        or fallback_hints.left_key_field
        or fallback_hints.right_key_field
    )
    compare_fields = model_hints.compare_fields or fallback_hints.compare_fields
    active_hints = _merge_template_hints_for_prompt(model_hints, fallback_hints)
    critique = critique_rule_candidate(text, workflow_hints=active_hints)
    if critique.verdict == "ready":
        active_hints = critique.workflow_hints
        rule_type_hint = critique.rule_type or active_hints.rule_type_hint or rule_type_hint
        key_field = active_hints.key_column or active_hints.left_key_field or active_hints.right_key_field or key_field
        compare_fields = active_hints.compare_fields or compare_fields
    return _format_dsl_optimized_description(
        text,
        hints=active_hints,
        rule_type_hint=rule_type_hint,
        key_field=key_field,
        compare_fields=compare_fields,
        missing=[],
    )


def _merge_template_hints_for_prompt(
    model_hints: AiRuleWorkflowHints,
    fallback_hints: AiRuleWorkflowHints,
) -> AiRuleWorkflowHints:
    updates: dict[str, Any] = {}
    for field_name in (
        "rule_type_hint",
        "target_field",
        "assertion_field",
        "assertion_operator",
        "assertion_value_source",
        "assertion_expected_field",
        "assertion_value",
        "operator",
        "expected_value",
        "expected_value_mode",
        "regex_pattern",
        "sequence_direction",
        "sequence_step",
        "sequence_start_mode",
        "sequence_start_value",
        "key_column",
        "reference_variable_tag",
        "reference_field",
        "reference_sheet",
        "filter_field",
        "filter_operator",
        "filter_value",
        "left_filter_field",
        "left_filter_operator",
        "left_filter_value",
        "right_filter_field",
        "right_filter_operator",
        "right_filter_value",
    ):
        value = getattr(model_hints, field_name)
        fallback_value = getattr(fallback_hints, field_name)
        if not value and fallback_value:
            updates[field_name] = fallback_value
    for field_name in ("filters", "composite_columns", "compare_fields", "pipeline_nodes", "mapping_nodes"):
        value = getattr(model_hints, field_name)
        fallback_value = getattr(fallback_hints, field_name)
        if not value and fallback_value:
            updates[field_name] = fallback_value
    return model_hints.model_copy(update=updates) if updates else model_hints


def _format_rule_summary_for_template(
    raw_description: str,
    *,
    hints: AiRuleWorkflowHints,
    rule_type_hint: str | None,
    key_field: str | None,
    compare_fields: list[str],
    missing: list[str],
) -> str:
    """把确定性线索压成模板内更容易被规则解析器识别的校验规则短语。"""
    field = hints.assertion_field or hints.target_field
    operator_labels = {
        "eq": "等于",
        "ne": "不等于",
        "gt": "大于",
        "lt": "小于",
        "not_null": "不能为空",
        "regex": "匹配正则",
        "unique": "不能重复",
        "duplicate_required": "必须重复",
    }
    parts: list[str] = []
    if rule_type_hint:
        parts.append(f"规则类型：{rule_type_hint}")
    if field:
        parts.append(f"字段：{field}")
    if rule_type_hint == "not_null" and field:
        parts.append(f"断言：{field} 不能为空")
    elif rule_type_hint == "unique" and field:
        parts.append(f"断言：{field} 不能重复")
    elif rule_type_hint == "regex_check" and field:
        regex_text = f"，正则：{hints.regex_pattern}" if hints.regex_pattern else ""
        parts.append(f"断言：{field} 必须匹配指定格式{regex_text}")
    elif rule_type_hint == "sequence_order_check" and field:
        sequence_parts = [
            f"方向：{hints.sequence_direction}" if hints.sequence_direction else "",
            f"步长：{hints.sequence_step}" if hints.sequence_step else "",
            f"起始：{hints.sequence_start_value}" if hints.sequence_start_value else "",
        ]
        parts.append(f"断言：{field} 按顺序连续；" + "；".join(item for item in sequence_parts if item))
    elif rule_type_hint == "fixed_value_compare" and field:
        operator = operator_labels.get(str(hints.operator or hints.assertion_operator or ""), hints.operator or hints.assertion_operator or "符合条件")
        expected = hints.expected_value or hints.assertion_value
        expected_text = f"；期望值：{expected}" if expected else ""
        mode_text = f"；期望值模式：{hints.expected_value_mode}" if hints.expected_value_mode else ""
        parts.append(f"断言：{field} {operator}{expected_text}{mode_text}")
    elif rule_type_hint == "cross_table_mapping" and field:
        reference = hints.reference_field or hints.reference_variable_tag or "需要用户确认：引用字段或引用变量"
        parts.append(f"断言：{field} 必须能在引用表中找到；引用：{reference}")
    elif rule_type_hint == "composite_condition_check":
        assertion_operator = operator_labels.get(
            str(hints.assertion_operator or ""),
            hints.assertion_operator or "符合条件",
        )
        target = field or "需要用户确认：目标字段"
        if hints.assertion_value_source == "field" and hints.assertion_expected_field:
            parts.append(
                f"断言：命中筛选条件后，{target} {assertion_operator}字段 {hints.assertion_expected_field}"
            )
        else:
            assertion_value = f"；期望值：{hints.assertion_value}" if hints.assertion_value else ""
            parts.append(f"断言：命中筛选条件后，{target} {assertion_operator}{assertion_value}")
    elif rule_type_hint == "dual_composite_compare":
        fields = ", ".join(compare_fields) if compare_fields else "需要用户确认：比较字段"
        key_text = key_field or "需要用户确认：Key 字段"
        parts.append(f"Key：{key_text}")
        parts.append(f"断言：左右两组按 Key 对齐后，比较字段 {fields} 必须相等")
    elif rule_type_hint in {"multi_composite_pipeline_check", "multi_composite_mapping_check"}:
        parts.append("断言：按多组组合变量节点执行筛选和映射校验")
    raw_text = raw_description.strip()
    fixed_template_labels = ("规则类型：", "目标字段：", "校验规则：")
    if raw_text and raw_text not in "；".join(parts) and not all(label in raw_text for label in fixed_template_labels):
        parts.append(f"原始规则：{raw_text}")
    if missing:
        parts.append(f"需要用户确认：{'；'.join(missing)}")
    return "；".join(item for item in parts if item) or "请填写校验条件。"


def _format_v3_filter_conditions(hints: AiRuleWorkflowHints) -> str | None:
    items: list[str] = []
    for raw_item in hints.filters:
        item = _coerce_filter_hint(raw_item)
        if item is None:
            continue
        items.append(f"{item.field} {item.operator or 'eq'} {item.value}")
    if hints.left_filter_field and hints.left_filter_value:
        items.append(f"左侧 {hints.left_filter_field} {hints.left_filter_operator or 'eq'} {hints.left_filter_value}")
    if hints.right_filter_field and hints.right_filter_value:
        items.append(f"右侧 {hints.right_filter_field} {hints.right_filter_operator or 'eq'} {hints.right_filter_value}")
    if hints.filter_field and hints.filter_value:
        items.append(f"{hints.filter_field} {hints.filter_operator or 'eq'} {hints.filter_value}")
    return "；".join(items) if items else None


def _format_prompt_filter_item(item: dict[str, Any]) -> str:
    side = str(item.get("side", "global"))
    side_label = {"left": "左侧", "right": "右侧", "global": ""}.get(side, side)
    prefix = f"{side_label} " if side_label else ""
    return f"{prefix}{item.get('field')} {item.get('operator')} {item.get('value')}"


def _selected_prompt_variable_fields(selected_variables: list[VariableTag]) -> list[str]:
    fields: list[str] = []
    for variable in selected_variables:
        if (variable.variable_kind or "single") == "composite":
            fields.extend(variable.columns or [])
            if variable.key_column:
                fields.insert(0, variable.key_column)
        elif variable.column:
            fields.append(variable.column)
    return _dedupe_prompt_values(fields)


def _format_rule_params_for_template(hints: AiRuleWorkflowHints) -> str:
    params: list[str] = []
    if hints.expected_value:
        params.append(f"期望值={hints.expected_value}")
    if hints.expected_value_mode:
        params.append(f"期望值模式={hints.expected_value_mode}")
    if hints.regex_pattern:
        params.append(f"正则={hints.regex_pattern}")
    if hints.sequence_direction:
        direction = "升序" if hints.sequence_direction == "asc" else "降序"
        params.append(f"方向={direction}")
    if hints.sequence_step:
        params.append(f"步长={hints.sequence_step}")
    if hints.sequence_start_mode:
        start = "自动" if hints.sequence_start_mode == "auto" else hints.sequence_start_value or "需要用户确认"
        params.append(f"起始={start}")
    if hints.assertion_value_source == "field" and hints.assertion_expected_field:
        params.append(f"字段比较={hints.assertion_field or hints.target_field}={hints.assertion_expected_field}")
    elif hints.assertion_value:
        params.append(f"断言值={hints.assertion_value}")
    if hints.reference_variable_tag or hints.reference_field or hints.reference_sheet:
        params.append(f"引用对象={hints.reference_variable_tag or hints.reference_field or hints.reference_sheet}")
    if hints.pipeline_nodes:
        params.append("节点=按 pipeline_nodes 配置")
    if hints.mapping_nodes:
        params.append("节点=按 mapping_nodes 配置")
    return "；".join(item for item in params if item) or "无"


def _clean_natural_sentence(value: str | None) -> str:
    text = (value or "").strip()
    text = re.sub(r"^(?:规则是|校验规则|补充说明|规则参数)\s*[：:=]\s*", "", text)
    text = re.sub(r"[。；;]+$", "", text).strip()
    return text


def _is_empty_natural_value(value: str | None) -> bool:
    text = (value or "").strip().lower()
    return not text or text in {"无", "空", "none", "null", "-"}


def _build_natural_prompt_description(
    *,
    target_text: str,
    filter_text: str,
    key_text: str,
    rule_text: str,
    extra_text: str,
) -> str:
    target = _clean_natural_sentence(target_text) or "需要用户确认：字段或内容"
    filter_value = _clean_natural_sentence(filter_text)
    key_value = _clean_natural_sentence(key_text)
    rule_value = _clean_natural_sentence(rule_text) or "请填写校验条件"
    extra_value = _clean_natural_sentence(extra_text) or "无"

    if _is_empty_natural_value(filter_value) or re.match(r"^(全部数据|所有数据|不限制)$", filter_value, re.IGNORECASE):
        filter_line = "只检查全部数据。"
    elif filter_value.startswith("满足") or re.search(r"^(左侧|右侧|left|right)\b", filter_value, re.IGNORECASE):
        filter_line = f"只检查{filter_value}。"
    else:
        filter_line = f"只检查满足 {filter_value} 的数据。"

    if _is_empty_natural_value(key_value):
        key_line = "如果需要按同一条配置对齐，用无作为 Key；不需要就写“无”。"
    else:
        key_line = f"如果需要按同一条配置对齐，用{key_value}作为 Key；不需要就写“无”。"

    return "\n\n".join(
        [
            f"我想检查{target}。",
            filter_line,
            key_line,
            f"规则是：{rule_value}。",
            f"补充说明：{extra_value}",
        ]
    )


def _format_natural_rule_sentence(
    raw_description: str,
    *,
    hints: AiRuleWorkflowHints,
    rule_type_hint: str | None,
    key_field: str | None,
    compare_fields: list[str],
    fallback: str,
) -> str:
    rule_type = rule_type_hint or hints.rule_type_hint
    field = hints.assertion_field or hints.target_field
    operator_labels = {
        "eq": "等于",
        "ne": "不等于",
        "gt": "大于",
        "lt": "小于",
        "not_null": "不能为空",
        "regex": "匹配正则",
        "unique": "不能重复",
        "duplicate_required": "必须重复",
    }
    if rule_type == "not_null" and field:
        return f"{field} 不能为空"
    if rule_type == "unique" and field:
        return f"{field} 不能重复"
    if rule_type == "regex_check" and field:
        suffix = f" {hints.regex_pattern}" if hints.regex_pattern else ""
        return f"{field} 匹配正则{suffix}".strip()
    if rule_type == "sequence_order_check" and field:
        direction = "升序" if hints.sequence_direction == "asc" else "降序" if hints.sequence_direction == "desc" else "指定顺序"
        step = f"，步长 {hints.sequence_step}" if hints.sequence_step else ""
        start = f"，起始 {hints.sequence_start_value}" if hints.sequence_start_value else ""
        return f"{field} 按{direction}连续{step}{start}"
    if rule_type == "fixed_value_compare" and field:
        operator = operator_labels.get(str(hints.operator or hints.assertion_operator or ""), hints.operator or hints.assertion_operator or "符合")
        expected = hints.expected_value or hints.assertion_value
        if hints.expected_value_mode == "set" and expected:
            return f"{field} 只能是 {expected}"
        return f"{field} {operator} {expected or '需要用户确认：期望值'}"
    if rule_type == "cross_table_mapping" and field:
        reference = hints.reference_field or hints.reference_variable_tag or hints.reference_sheet or "引用对象"
        return f"{field} 必须存在于{reference}"
    if rule_type == "composite_condition_check":
        target = field or "需要用户确认：目标字段"
        operator = operator_labels.get(str(hints.assertion_operator or ""), hints.assertion_operator or "符合条件")
        if hints.assertion_value_source == "field" and hints.assertion_expected_field:
            return f"{target} {operator}字段 {hints.assertion_expected_field}"
        if hints.assertion_operator in {"not_null", "unique"}:
            return f"{target} {operator}"
        if hints.assertion_value:
            return f"{target} {operator} {hints.assertion_value}"
        return f"{target} 满足组合条件"
    if rule_type == "dual_composite_compare":
        fields = ", ".join(compare_fields) if compare_fields else "需要用户确认：比较字段"
        key = key_field or "需要用户确认：Key 字段"
        return f"左右两组按 {key} 对齐后，比较字段 {fields} 必须相等"
    if rule_type in {"multi_composite_pipeline_check", "multi_composite_mapping_check"}:
        return "按多组组合变量节点执行筛选和映射校验"

    natural_rule = _extract_natural_rule_from_text(raw_description)
    if natural_rule:
        return natural_rule
    cleaned_fallback = _clean_natural_sentence(fallback)
    if cleaned_fallback and "规则类型：" not in cleaned_fallback:
        return cleaned_fallback
    return "需要用户确认：请补充最终判断关系"


def _format_natural_extra_sentence(
    hints: AiRuleWorkflowHints,
    *,
    reference_text: str = "无",
    compare_text: str = "无",
    rule_params: str = "",
) -> str:
    items: list[str] = []
    if not _is_empty_natural_value(reference_text):
        items.append(f"引用对象 {reference_text}")
    if (
        not _is_empty_natural_value(compare_text)
        and hints.rule_type_hint == "dual_composite_compare"
    ):
        items.append(f"比较字段 {compare_text}")
    params = _clean_natural_sentence(rule_params)
    if not _is_empty_natural_value(params):
        items.append(params)
    if hints.regex_pattern and not any("正则" in item for item in items):
        items.append(f"正则 {hints.regex_pattern}")
    if hints.sequence_direction and not any("方向" in item for item in items):
        direction = "升序" if hints.sequence_direction == "asc" else "降序"
        items.append(f"排序方向 {direction}")
    if hints.expected_value and not any("期望值" in item or hints.expected_value in item for item in items):
        items.append(f"期望值 {hints.expected_value}")
    return "；".join(items) if items else "无"


def _extract_natural_rule_from_text(text: str) -> str | None:
    match = re.search(r"规则是\s*[：:=]?\s*([^。；;\n\r]+)", text, re.IGNORECASE)
    if not match:
        return None
    value = _clean_natural_sentence(match.group(1))
    if not value or "【" in value or "】" in value:
        return None
    return value


def _parse_prompt_template_sections(text: str) -> dict[str, str]:
    labels = (
        "数据源",
        "sheet分页",
        "变量选择",
        "我想检查",
        "只检查",
        "规则类型",
        "rule_type",
        "目标字段",
        "目标",
        "目标列名",
        "校验字段",
        "筛选条件",
        "Key字段",
        "Key 字段",
        "关联Key",
        "引用对象",
        "比较字段",
        "筛选规则1",
        "筛选规则2",
        "校验规则",
        "规则是",
        "补充说明",
        "规则参数",
    )
    label_pattern = "|".join(re.escape(label) for label in labels)
    sections: dict[str, list[str]] = {}
    current_label: str | None = None
    for line in text.replace("\r", "\n").split("\n"):
        stripped = line.strip()
        match = re.match(rf"^({label_pattern})\s*[：:]\s*(.*)$", stripped)
        if match:
            current_label = match.group(1)
            sections.setdefault(current_label, []).append(match.group(2).strip())
        elif current_label and stripped:
            sections[current_label].append(stripped)
    return {
        label: "\n".join(item for item in values if item).strip()
        for label, values in sections.items()
    }


def _prefer_model_or_fallback_template_value(
    model_value: str | None,
    fallback_value: str | None,
    *,
    default: str,
) -> str:
    normalized_model = _normalize_optional_template_value(model_value or "")
    normalized_fallback = _normalize_optional_template_value(fallback_value or "")
    if normalized_model and normalized_model != "无" and not normalized_model.startswith("需要用户确认"):
        return normalized_model
    if normalized_fallback and normalized_fallback != "无":
        return normalized_fallback
    if normalized_model and normalized_model != "无":
        return normalized_model
    return default


def _normalize_optional_template_value(value: str) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else "无"


def _build_prompt_template_from_sections(sections: dict[str, str]) -> str:
    section_text = "\n".join(f"{key}：{value}" for key, value in sections.items() if value)
    section_hints = extract_workflow_hints_from_text(section_text)
    legacy_filter_values = [
        sections.get("筛选规则1"),
        sections.get("筛选规则2"),
    ]
    legacy_filter = "；".join(item for item in legacy_filter_values if item and item != "无")
    filter_conditions = sections.get("筛选条件") or legacy_filter or "无"
    raw_rule_text = sections.get("规则是") or sections.get("校验规则") or "请填写校验条件"
    if "规则类型：" in raw_rule_text or "断言：" in raw_rule_text:
        raw_rule_text = _format_natural_rule_sentence(
            section_text,
            hints=section_hints,
            rule_type_hint=section_hints.rule_type_hint or sections.get("规则类型") or sections.get("rule_type"),
            key_field=section_hints.key_column,
            compare_fields=section_hints.compare_fields,
            fallback=raw_rule_text,
        )
    extra_items = [
        sections.get("补充说明"),
        f"引用对象 {sections.get('引用对象')}" if sections.get("引用对象") and sections.get("引用对象") != "无" else "",
        f"比较字段 {sections.get('比较字段')}"
        if (
            sections.get("比较字段")
            and sections.get("比较字段") != "无"
            and section_hints.rule_type_hint == "dual_composite_compare"
        )
        else "",
        sections.get("规则参数") if sections.get("规则参数") and sections.get("规则参数") != "无" else "",
    ]
    return _build_natural_prompt_description(
        target_text=sections.get("我想检查")
        or sections.get("目标字段")
        or sections.get("目标列名")
        or sections.get("校验字段")
        or section_hints.assertion_field
        or section_hints.target_field
        or "需要用户确认：字段或内容",
        filter_text=sections.get("只检查") or filter_conditions,
        key_text=sections.get("Key字段") or sections.get("Key 字段") or sections.get("关联Key") or "无",
        rule_text=raw_rule_text,
        extra_text="；".join(item for item in extra_items if item) or "无",
    )


def _format_template_filter_line(hints: AiRuleWorkflowHints, *, side: str = "global") -> str | None:
    if side == "right":
        if hints.right_filter_field and hints.right_filter_value:
            return f"right：{hints.right_filter_field} {hints.right_filter_operator or 'eq'} {hints.right_filter_value}"
        return None
    if hints.left_filter_field and hints.left_filter_value:
        return f"left：{hints.left_filter_field} {hints.left_filter_operator or 'eq'} {hints.left_filter_value}"
    if hints.filter_field and hints.filter_value:
        return f"{hints.filter_field} {hints.filter_operator or 'eq'} {hints.filter_value}"
    return None


def _dedupe_prompt_values(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = (value or "").strip()
        if normalized and normalized not in result and not _is_placeholder_key_column(normalized):
            result.append(normalized)
    return result


def _format_prompt_variable_line(variable: VariableTag) -> str:
    if (variable.variable_kind or "single") == "composite":
        columns = ", ".join(variable.columns or [])
        return f"- {variable.tag}：组合变量，Sheet={variable.sheet}，Key={variable.key_column or '未配置'}，字段={columns or '未配置'}"
    return f"- {variable.tag}：单变量，Sheet={variable.sheet}，字段={variable.column or '未配置'}"


def _prompt_optimize_failure_message(exc: Exception) -> str:
    if isinstance(exc, AiProviderNotConfigured):
        return "AI 模型未配置，已生成本地兜底优化结果。"
    if isinstance(exc, AiProviderInvalid):
        return "AI 凭据不可用，请重新配置模型；已生成本地兜底优化结果。"
    if isinstance(exc, ProviderConnectionError):
        return f"模型调用失败：{exc.message}；已生成本地兜底优化结果。"
    if isinstance(exc, ValidationError):
        return "模型返回格式不符合协议，已生成本地兜底优化结果。"
    return "优化失败，已生成本地兜底优化结果。"


def _validate_list(raw_items: Any, model_type: type) -> list[Any]:
    if not isinstance(raw_items, list):
        return []
    validated: list[Any] = []
    for item in raw_items:
        try:
            validated.append(model_type.model_validate(item))
        except ValidationError:
            continue
    return validated


def _read_safe_source_metadata(sources: list[DataSource]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for source in sources:
        if source.type not in {"local_excel", "svn"}:
            metadata[source.id] = {"sheets": [], "error": "当前数据源类型暂不支持元数据读取。"}
            continue
        try:
            metadata[source.id] = read_source_metadata(source)
        except Exception as exc:  # noqa: BLE001 - 只作为 AI 上下文降级提示，不阻断页面。
            metadata[source.id] = {"sheets": [], "error": str(exc)}
    return metadata


def _context_with_temporary_hint_metadata(
    context: dict[str, Any],
    *,
    workflow_hints: AiRuleWorkflowHints,
    intent: RuleIntent,
) -> dict[str, Any]:
    """读取本次输入中的未保存数据源元数据，只用于当前 AI 草稿编译。"""
    workflow_hints = _sanitize_workflow_hints(workflow_hints)
    source_url = _first_text(
        workflow_hints.source_url,
        intent.target.path_or_url if intent.target else None,
    )
    if not source_url:
        return context

    source_id = _first_text(
        workflow_hints.source_id,
        intent.target.source_id if intent.target else None,
        _derive_source_id(source_url),
    )
    if not source_id:
        return context

    source_metadata = context.get("source_metadata", {})
    if isinstance(source_metadata, dict):
        current_metadata = source_metadata.get(source_id)
        current_sheets = current_metadata.get("sheets") if isinstance(current_metadata, dict) else None
        if isinstance(current_sheets, list) and current_sheets:
            return context
    else:
        source_metadata = {}

    source_type = _first_text(
        workflow_hints.source_type,
        intent.target.source_type if intent.target else None,
        _guess_source_type(source_url),
    )
    if source_type not in {"local_excel", "svn"}:
        return context

    source = DataSource(
        id=source_id,
        type=source_type,  # type: ignore[arg-type]
        pathOrUrl=source_url,
    )
    next_metadata = dict(source_metadata)
    try:
        next_metadata[source_id] = read_source_metadata(source)
    except Exception as exc:  # noqa: BLE001 - 草稿补齐阶段只降级为缺口提示。
        next_metadata[source_id] = {"sheets": [], "error": str(exc)}
    return {**context, "source_metadata": next_metadata}


def _compile_intent(
    intent: RuleIntent,
    *,
    context: dict[str, Any],
    description: str,
) -> RuleDraftResponse:
    if intent.verdict == "rejected":
        return RuleDraftResponse(
            verdict="rejected",
            rule_type=intent.rule_type,
            confidence=intent.confidence,
            reasoning_summary=intent.reasoning_summary,
            missing=intent.missing,
            rejection_reason=intent.rejection_reason or "当前规则无法用现有能力表达。",
        )

    if intent.rule_type is None:
        return _needs_input(
            intent,
            MissingItem(
                kind="rule",
                message="缺少可用规则类型，请补充要检查的规则口径。",
                suggested_action="edit_description",
            ),
        )

    if intent.target is None and intent.rule_type not in {
        "multi_composite_pipeline_check",
        "multi_composite_mapping_check",
    }:
        return _needs_input(
            intent,
            MissingItem(
                kind="variable",
                message="缺少目标变量，请说明 Sheet 和列名。",
                suggested_action="edit_description",
            ),
        )

    sources_to_add: list[DataSource] = []
    variables_to_add: list[VariableTag] = []
    reuse_tags: list[str] = []

    target_variable: VariableTag | None = None
    if intent.target is not None:
        target_variable, target_missing, target_source = _resolve_variable(intent.target, context)
        if target_missing:
            return _needs_input(intent, *target_missing)
        if target_source is not None:
            sources_to_add.append(target_source)
        if target_variable is not None and not _variable_exists(target_variable.tag, context):
            variables_to_add.append(target_variable)
        if target_variable is not None and _variable_exists(target_variable.tag, context):
            reuse_tags.append(target_variable.tag)
        if target_variable is not None and intent.rule_type == "composite_condition_check":
            intent = intent.model_copy(
                update={
                    "display_field": _canonical_variable_field(target_variable, intent.display_field),
                    "composite_config": _canonicalize_composite_config_fields(
                        intent.composite_config,
                        target_variable,
                    ),
                }
            )

    reference_variable: VariableTag | None = None
    if intent.rule_type in {"cross_table_mapping", "dual_composite_compare"}:
        if intent.reference is None:
            return _needs_input(
                intent,
                MissingItem(
                    kind="variable",
                    message="该规则需要引用变量，请补充被引用的 Sheet 和列名。",
                    suggested_action="edit_description",
                ),
            )
        reference_variable, reference_missing, reference_source = _resolve_variable(
            intent.reference,
            context,
        )
        if reference_missing:
            return _needs_input(intent, *reference_missing)
        if reference_source is not None:
            sources_to_add.append(reference_source)
        if reference_variable is not None and not _variable_exists(reference_variable.tag, context):
            variables_to_add.append(reference_variable)
        if reference_variable is not None and _variable_exists(reference_variable.tag, context):
            reuse_tags.append(reference_variable.tag)

    rule, missing = _build_rule_definition(
        intent,
        target_variable=target_variable,
        reference_variable=reference_variable,
        description=description,
    )
    if missing:
        return _needs_input(intent, *missing)
    if rule is None:
        return RuleDraftResponse(
            verdict="rejected",
            rule_type=intent.rule_type,
            confidence=intent.confidence,
            reasoning_summary=intent.reasoning_summary,
            rejection_reason="当前规则意图无法编译为 Excel Check 规则。",
        )

    return RuleDraftResponse(
        verdict="ready",
        rule_type=intent.rule_type,
        confidence=intent.confidence,
        reasoning_summary=intent.reasoning_summary or "已生成可添加的规则草稿。",
        draft=RuleDraftPayload(
            sources_to_add=_unique_sources(sources_to_add),
            variables_to_add=_unique_variables(variables_to_add),
            rules_to_add=[rule],
            reuse_variable_tags=sorted(set(reuse_tags)),
        ),
        missing=[],
        rejection_reason=None,
    )


def _compile_with_workflow_hints(
    intent: RuleIntent,
    *,
    workflow_hints: AiRuleWorkflowHints,
    context: dict[str, Any],
    description: str,
    selected_variable_tags: list[str] | None = None,
    allow_auto_complete: bool = True,
) -> RuleDraftResponse | None:
    compile_context = (
        _context_with_temporary_hint_metadata(
            context,
            workflow_hints=workflow_hints,
            intent=intent,
        )
        if allow_auto_complete
        else context
    )
    hinted_intent, missing = _build_intent_from_workflow_hints(
        intent,
        workflow_hints=workflow_hints,
        description=description,
        context=compile_context,
        selected_variable_tags=selected_variable_tags or [],
        allow_auto_complete=allow_auto_complete,
    )
    if missing:
        summary = (
            "自动补齐缺少数据源路径、Sheet 或字段线索；请补充完整描述后重新校验，"
            "或关闭自动补齐并选择已有变量池变量；也可以修改上方规则描述后重试。"
            if allow_auto_complete
            else "无法基于已选择变量生成可执行草稿，请补充变量、字段或规则参数后重新校验。"
        )
        return RuleDraftResponse(
            verdict="needs_input",
            rule_type=intent.rule_type,
            confidence=intent.confidence,
            reasoning_summary=summary,
            missing=missing,
            rejection_reason=None,
        )
    if hinted_intent is None:
        return None
    return _compile_intent(hinted_intent, context=compile_context, description=description)


def _build_intent_from_workflow_hints(
    intent: RuleIntent,
    *,
    workflow_hints: AiRuleWorkflowHints,
    description: str,
    context: dict[str, Any] | None = None,
    selected_variable_tags: list[str] | None = None,
    allow_auto_complete: bool = True,
) -> tuple[RuleIntent | None, list[MissingItem]]:
    selected_tags = set(selected_variable_tags or [])
    workflow_hints = _sanitize_workflow_hints(workflow_hints)
    rule_type = _infer_hint_rule_type(intent, workflow_hints, description)
    source_url_hint = _first_text(workflow_hints.source_url, intent.target.path_or_url if intent.target else None)
    source_id_hint = _first_text(
        workflow_hints.source_id,
        intent.target.source_id if intent.target else None,
        _derive_source_id(source_url_hint),
    )
    sheet_hint = _first_text(workflow_hints.sheet, intent.target.sheet if intent.target else None)
    target_variable = _get_context_variable(
        context,
        _first_text(
            workflow_hints.target_variable_tag,
            workflow_hints.left_variable_tag,
            intent.target.tag if intent.target else None,
            (selected_variable_tags or [None])[0],
        ),
    )
    reference_variable = _get_context_variable(
        context,
        _first_text(
            workflow_hints.reference_variable_tag,
            workflow_hints.right_variable_tag,
            intent.reference.tag if intent.reference else None,
            (selected_variable_tags or [None, None])[1] if len(selected_variable_tags or []) > 1 else None,
        ),
    )
    if target_variable and selected_tags and target_variable.tag not in selected_tags:
        target_variable = None
    if reference_variable and selected_tags and reference_variable.tag not in selected_tags:
        reference_variable = None
    if allow_auto_complete:
        if target_variable and not _variable_matches_source_sheet(target_variable, source_id_hint, sheet_hint):
            target_variable = None
        if reference_variable and not _variable_matches_source_sheet(reference_variable, source_id_hint, sheet_hint):
            reference_variable = None

    if target_variable is None and allow_auto_complete:
        workflow_hints, metadata_warnings, metadata_unresolved_fields = _canonicalize_workflow_hints_fields_from_metadata(
            workflow_hints,
            context,
            source_id=source_id_hint,
            sheet=sheet_hint,
        )
    else:
        metadata_warnings = []
        metadata_unresolved_fields = []

    if target_variable is None and rule_type in {
        "composite_condition_check",
        "dual_composite_compare",
        "multi_composite_pipeline_check",
        "multi_composite_mapping_check",
    }:
        required_fields = _unique_texts(
            [
                workflow_hints.filter_field,
                *(
                    item.field
                    for item in (_coerce_filter_hint(raw_item) for raw_item in workflow_hints.filters)
                    if item is not None
                ),
                workflow_hints.assertion_field,
                workflow_hints.target_field,
                intent.target.column if intent.target else None,
                workflow_hints.key_column,
                workflow_hints.left_key_field,
                workflow_hints.right_key_field,
                workflow_hints.left_filter_field,
                workflow_hints.right_filter_field,
                *workflow_hints.composite_columns,
                *workflow_hints.compare_fields,
            ]
        )
        target_variable = _find_existing_composite_variable_for_hints(
            context,
            source_id=source_id_hint,
            sheet=sheet_hint,
            required_fields=required_fields,
        )
        if target_variable and selected_tags and target_variable.tag not in selected_tags:
            target_variable = None
    workflow_hints, field_correction_warnings, unresolved_hint_fields = _canonicalize_workflow_hints_fields(
        workflow_hints,
        target_variable or reference_variable,
    )
    field_correction_warnings = _unique_texts([*metadata_warnings, *field_correction_warnings])
    unresolved_hint_fields = _unique_texts(
        unresolved_hint_fields
        if target_variable or reference_variable
        else [*metadata_unresolved_fields, *unresolved_hint_fields]
    )

    target_field = _first_text(
        workflow_hints.target_field,
        intent.target.column if intent.target else None,
        _default_target_field_from_variable(target_variable),
    )
    sheet = _first_text(
        workflow_hints.sheet,
        intent.target.sheet if intent.target else None,
        target_variable.sheet if target_variable else None,
    )
    source_url = _first_text(workflow_hints.source_url, intent.target.path_or_url if intent.target else None)
    source_id = _first_text(
        workflow_hints.source_id,
        intent.target.source_id if intent.target else None,
        target_variable.source_id if target_variable else None,
        _derive_source_id(source_url),
    )
    source_type = _first_text(
        workflow_hints.source_type,
        intent.target.source_type if intent.target else None,
        _guess_source_type(source_url),
    )
    regex_pattern = _first_text(
        workflow_hints.regex_pattern,
        intent.regex_pattern,
        intent.expected_value if intent.rule_type == "regex_check" else None,
    )
    display_field = _first_text(workflow_hints.display_field, intent.display_field)
    filter_field = _first_text(workflow_hints.filter_field)
    filter_value = _first_text(workflow_hints.filter_value)
    filter_operator = (
        workflow_hints.filter_operator
        or _infer_filter_operator_from_description(description, filter_field=filter_field, filter_value=filter_value)
        or "eq"
    )
    filter_hints = _workflow_global_filters(
        workflow_hints,
        fallback_field=filter_field,
        fallback_operator=filter_operator,
        fallback_value=filter_value,
    )

    missing: list[MissingItem] = []
    if not rule_type:
        missing.append(
            MissingItem(
                kind="rule",
                message="缺少可自动识别的规则类型，请在描述中说明非空、唯一、正则格式或固定值比较等规则口径。",
                suggested_action="none",
            )
        )
    if not source_id and not source_url:
        missing.append(
            MissingItem(
                kind="source",
                message="缺少可自动添加的数据源标识或配置表链接；请补充配置表路径，或关闭自动补齐后选择已有变量池变量。",
                suggested_action="none",
            )
        )
    if not sheet:
        missing.append(
            MissingItem(
                kind="variable",
                message="缺少目标 Sheet，无法自动添加变量；请补充分页名称，或关闭自动补齐后选择已有变量池变量。",
                suggested_action="none",
            )
        )
    single_target_rule_types = {
        "not_null",
        "unique",
        "fixed_value_compare",
        "regex_check",
        "sequence_order_check",
        "cross_table_mapping",
    }
    if rule_type in single_target_rule_types and not target_field:
        missing.append(
            MissingItem(
                kind="variable",
                message="缺少目标字段，无法自动生成变量和规则；请补充字段名，或关闭自动补齐后选择已有变量池变量。",
                suggested_action="none",
            )
        )
    if rule_type == "composite_condition_check":
        if not (workflow_hints.assertion_field or target_field or regex_pattern):
            missing.append(
                MissingItem(
                    kind="variable",
                    message="缺少组合分支校验的断言字段；请补充被校验字段，或关闭自动补齐后选择已有变量池变量。",
                    suggested_action="none",
                )
            )
        if not filter_hints:
            missing.append(
                MissingItem(
                    kind="parameter",
                    message="缺少组合分支校验的筛选字段或筛选值；请补充筛选条件，或关闭自动补齐后选择已有变量池变量。",
                    suggested_action="none",
                )
            )
    if unresolved_hint_fields:
        missing.append(
            MissingItem(
                kind="variable",
                message=f"目标变量或 Sheet 中不存在或无法唯一匹配字段：{', '.join(_unique_texts(unresolved_hint_fields))}，请改成真实字段后重试。",
                suggested_action="none",
            )
        )
    if missing:
        return None, missing

    common_variable_kwargs = {
        "source_id": source_id,
        "source_type": source_type,
        "path_or_url": source_url,
        "sheet": sheet,
    }

    if rule_type in {"not_null", "unique", "fixed_value_compare", "regex_check", "sequence_order_check"}:
        if target_variable is not None and (target_variable.variable_kind or "single") != "single":
            return None, [
                MissingItem(
                    kind="variable",
                    message="该规则需要选择单变量，当前目标变量是组合变量。",
                    suggested_action="none",
                )
            ]
        if not target_field:
            return None, [
                MissingItem(
                    kind="variable",
                    message="单变量规则需要目标字段。",
                    suggested_action="none",
                )
            ]
        if rule_type == "fixed_value_compare" and not (
            (workflow_hints.operator or intent.operator)
            and _first_text(workflow_hints.expected_value, intent.expected_value)
        ):
            return None, [
                MissingItem(
                    kind="parameter",
                    message="固定值比较需要操作符和比较值。",
                    suggested_action="none",
                )
            ]
        if rule_type == "regex_check" and not regex_pattern:
            return None, [
                MissingItem(
                    kind="parameter",
                    message="正则校验需要正则表达式。",
                    suggested_action="none",
                )
            ]
        target = _variable_intent_from_existing(target_variable) or VariableIntent(
            **common_variable_kwargs,
            variable_kind="single",
            column=target_field,
            expected_type=intent.target.expected_type if intent.target else "str",
        )
        return RuleIntent(
            verdict="ready",
            rule_type=rule_type,
            confidence=max(intent.confidence, 0.7),
            reasoning_summary=_append_field_correction_summary(
                intent.reasoning_summary or "已根据结构化线索自动补齐数据源、变量和规则。",
                field_correction_warnings,
            ),
            rule_name=intent.rule_name,
            display_field=display_field,
            target=target,
            operator=workflow_hints.operator or intent.operator,
            expected_value=_first_text(workflow_hints.expected_value, intent.expected_value),
            expected_value_mode=workflow_hints.expected_value_mode or intent.expected_value_mode,
            regex_pattern=regex_pattern,
            sequence_direction=workflow_hints.sequence_direction or intent.sequence_direction,
            sequence_step=_first_text(workflow_hints.sequence_step, intent.sequence_step, "1"),
            sequence_start_mode=workflow_hints.sequence_start_mode or intent.sequence_start_mode or "auto",
            sequence_start_value=_first_text(
                workflow_hints.sequence_start_value,
                intent.sequence_start_value,
            ),
        ), []

    if rule_type == "cross_table_mapping":
        if target_variable is not None and (target_variable.variable_kind or "single") != "single":
            return None, [
                MissingItem(kind="variable", message="包含(in) 目标变量必须是单变量。", suggested_action="none")
            ]
        if reference_variable is not None and (reference_variable.variable_kind or "single") != "single":
            return None, [
                MissingItem(kind="variable", message="包含(in) 引用变量必须是单变量。", suggested_action="none")
            ]
        reference_field = _first_text(
            workflow_hints.reference_field,
            intent.reference.column if intent.reference else None,
            reference_variable.column if reference_variable else None,
        )
        reference_sheet = _first_text(
            workflow_hints.reference_sheet,
            intent.reference.sheet if intent.reference else None,
            reference_variable.sheet if reference_variable else None,
        )
        reference_source_url = _first_text(
            workflow_hints.reference_source_url,
            intent.reference.path_or_url if intent.reference else None,
            source_url,
        )
        reference_source_id = _first_text(
            workflow_hints.reference_source_id,
            intent.reference.source_id if intent.reference else None,
            reference_variable.source_id if reference_variable else None,
            _derive_source_id(reference_source_url),
            source_id,
        )
        if not reference_field or not reference_sheet:
            return None, [
                MissingItem(
                    kind="variable",
                    message="跨表映射需要引用 Sheet 和引用字段。",
                    suggested_action="none",
                )
            ]
        target = _variable_intent_from_existing(target_variable) or VariableIntent(
            **common_variable_kwargs,
            variable_kind="single",
            column=target_field,
            expected_type="str",
        )
        reference = _variable_intent_from_existing(reference_variable) or VariableIntent(
            source_id=reference_source_id,
            source_type=workflow_hints.reference_source_type or source_type,
            path_or_url=reference_source_url,
            sheet=reference_sheet,
            variable_kind="single",
            column=reference_field,
            expected_type="str",
        )
        return RuleIntent(
            verdict="ready",
            rule_type=rule_type,
            confidence=max(intent.confidence, 0.7),
            reasoning_summary=_append_field_correction_summary(
                intent.reasoning_summary or "已根据结构化线索自动补齐跨表映射规则。",
                field_correction_warnings,
            ),
            rule_name=intent.rule_name,
            display_field=display_field,
            target=target,
            reference=reference,
        ), []

    if rule_type == "composite_condition_check":
        if target_variable is not None and (target_variable.variable_kind or "single") != "composite":
            return None, [
                MissingItem(
                    kind="variable",
                    message="组合分支校验需要选择组合变量。",
                    suggested_action="none",
                )
            ]
        key_column, composite_columns = _resolve_hint_composite_columns(
            workflow_hints,
            variable=target_variable,
            target_field=target_field,
            display_field=display_field,
            filter_field=filter_field,
        )
        if not key_column:
            key_column = _infer_metadata_key_column(
                context,
                source_id=source_id,
                sheet=sheet,
            )
            if key_column and key_column not in composite_columns:
                composite_columns.insert(0, key_column)
        target_field = _canonical_variable_field(target_variable, target_field)
        filter_field = _canonical_variable_field(target_variable, filter_field)
        filter_hints = _canonicalize_filter_hints(target_variable, filter_hints)
        display_field = _canonical_variable_field(target_variable, display_field)
        key_column = _canonical_variable_field(target_variable, key_column)
        assertion_field = _canonical_variable_field(
            target_variable,
            workflow_hints.assertion_field or target_field,
        )
        assertion_expected_field = _canonical_variable_field(
            target_variable,
            workflow_hints.assertion_expected_field,
        )
        if not key_column or len(composite_columns) < 2:
            return None, [
                MissingItem(
                    kind="variable",
                    message="组合分支校验需要组合变量列和 Key 列，请补充 Key 字段与组合变量列。",
                    suggested_action="none",
                    prefill={
                        "source_id": source_id or "",
                        "source_type": source_type or "local_excel",
                        "pathOrUrl": source_url or "",
                        "sheet": sheet or "",
                        "columns": composite_columns,
                        "key_column": key_column or "",
                    },
                )
            ]
        composite_config = _build_hint_composite_config(
            target_field=target_field,
            regex_pattern=regex_pattern,
            filter_field=filter_field,
            filter_operator=filter_operator,
            filter_value=filter_value,
            filters=filter_hints,
            assertion_field=assertion_field,
            assertion_operator=workflow_hints.assertion_operator,
            assertion_value=workflow_hints.assertion_value,
            assertion_value_source=workflow_hints.assertion_value_source,
            assertion_expected_field=assertion_expected_field,
        ) or _canonicalize_composite_config_fields(intent.composite_config, target_variable)
        if composite_config is None:
            return None, [
                MissingItem(
                    kind="parameter",
                    message="组合分支校验需要可执行的筛选或正则断言，请补充正则表达式或规则细节。",
                    suggested_action="none",
                )
            ]
        target = _variable_intent_from_existing(target_variable) or VariableIntent(
            **common_variable_kwargs,
            variable_kind="composite",
            columns=composite_columns,
            key_column=key_column,
            append_index_to_key=True,
            expected_type="json",
        )
        return RuleIntent(
            verdict="ready",
            rule_type=rule_type,
            confidence=max(intent.confidence, 0.7),
            reasoning_summary=_append_field_correction_summary(
                intent.reasoning_summary
                or "已根据结构化线索自动补齐数据源、组合变量和组合分支规则。",
                field_correction_warnings,
            ),
            rule_name=intent.rule_name or f"{sheet}-{target_field}-格式校验",
            display_field=display_field,
            target=target,
            composite_config=composite_config,
        ), []

    if rule_type == "dual_composite_compare":
        if target_variable is not None and (target_variable.variable_kind or "single") != "composite":
            return None, [
                MissingItem(kind="variable", message="跨组变量校验的左侧变量必须是组合变量。", suggested_action="none")
            ]
        if reference_variable is not None and (reference_variable.variable_kind or "single") != "composite":
            return None, [
                MissingItem(kind="variable", message="跨组变量校验的右侧变量必须是组合变量。", suggested_action="none")
            ]
        key_column = _first_text(
            workflow_hints.key_column,
            workflow_hints.left_key_field,
            workflow_hints.right_key_field,
            target_variable.key_column if target_variable else None,
        )
        compare_fields = _unique_texts(workflow_hints.compare_fields)
        left_filter_field = _first_text(workflow_hints.left_filter_field)
        left_filter_value = _first_text(workflow_hints.left_filter_value)
        right_filter_field = _first_text(workflow_hints.right_filter_field)
        right_filter_value = _first_text(workflow_hints.right_filter_value)
        missing_dual: list[MissingItem] = []
        if not key_column:
            missing_dual.append(
                MissingItem(kind="variable", message="跨组变量校验需要左右关联 Key 字段。", suggested_action="none")
            )
        if not compare_fields:
            missing_dual.append(
                MissingItem(kind="parameter", message="跨组变量校验需要至少一个比较字段。", suggested_action="none")
            )
        if not (left_filter_field and left_filter_value and right_filter_field and right_filter_value):
            missing_dual.append(
                MissingItem(kind="parameter", message="同一组合变量拆分左右两组时需要左右筛选条件。", suggested_action="none")
            )
        if missing_dual:
            return None, missing_dual

        key_column = key_column or "__key__"
        columns = _unique_texts(
            [
                *workflow_hints.composite_columns,
                key_column,
                left_filter_field,
                right_filter_field,
                *compare_fields,
            ]
        )
        target = _variable_intent_from_existing(target_variable) or VariableIntent(
            **common_variable_kwargs,
            variable_kind="composite",
            columns=columns,
            key_column=key_column,
            append_index_to_key=True,
            expected_type="json",
        )
        reference = _variable_intent_from_existing(reference_variable) or target
        compare_operator = workflow_hints.compare_operator or intent.operator or "eq"
        comparisons = [
            {
                "comparison_id": f"ai-compare-{uuid4().hex[:8]}",
                "left_field": field,
                "operator": compare_operator,
                "right_field": field,
            }
            for field in compare_fields
        ]
        return RuleIntent(
            verdict="ready",
            rule_type=rule_type,
            confidence=max(intent.confidence, 0.75),
            reasoning_summary=_append_field_correction_summary(
                intent.reasoning_summary or "已根据结构化线索自动生成跨组变量对比规则。",
                field_correction_warnings,
            ),
            rule_name=intent.rule_name or f"{sheet}-{key_column}-两组配置比对",
            display_field=display_field,
            target=target,
            reference=reference,
            key_check_mode=workflow_hints.key_check_mode or intent.key_check_mode or "baseline_only",
            left_key_field=workflow_hints.left_key_field or key_column,
            right_key_field=workflow_hints.right_key_field or key_column,
            comparisons=comparisons,  # type: ignore[arg-type]
            left_filters=[
                _condition(
                    field=left_filter_field or "",
                    operator=workflow_hints.left_filter_operator or "eq",
                    expected_value=left_filter_value,
                )
            ],
            right_filters=[
                _condition(
                    field=right_filter_field or "",
                    operator=workflow_hints.right_filter_operator or "eq",
                    expected_value=right_filter_value,
                )
            ],
        ), []

    if rule_type in {"multi_composite_pipeline_check", "multi_composite_mapping_check"}:
        if target_variable is not None and (target_variable.variable_kind or "single") != "composite":
            return None, [
                MissingItem(kind="variable", message="多组规则需要选择组合变量。", suggested_action="none")
            ]
        key_column, composite_columns = _resolve_hint_composite_columns(
            workflow_hints,
            variable=target_variable,
            target_field=target_field,
            display_field=display_field,
            filter_field=filter_field,
        )
        if not key_column or len(composite_columns) < 2:
            return None, [
                MissingItem(
                    kind="variable",
                    message="多组规则至少需要组合变量 Key 和组合变量列。",
                    suggested_action="none",
                )
            ]
        target = _variable_intent_from_existing(target_variable) or VariableIntent(
            **common_variable_kwargs,
            variable_kind="composite",
            columns=composite_columns,
            key_column=key_column,
            append_index_to_key=True,
            expected_type="json",
        )
        variable_tag = target_variable.tag if target_variable else _build_composite_tag(
            source_id or "source",
            sheet or "sheet",
            key_column,
        )
        if rule_type == "multi_composite_pipeline_check" and workflow_hints.pipeline_nodes:
            pipeline_config = {
                "nodes": _build_multi_nodes_from_hints(
                    workflow_hints.pipeline_nodes,
                    fallback_variable_tag=variable_tag,
                    display_field=display_field,
                    mapping=False,
                )
            }
            return RuleIntent(
                verdict="ready",
                rule_type=rule_type,
                confidence=max(intent.confidence, 0.7),
                reasoning_summary=_append_field_correction_summary(
                    intent.reasoning_summary or "已根据结构化线索自动生成多组串行规则。",
                    field_correction_warnings,
                ),
                rule_name=intent.rule_name or f"{sheet}-{key_column}-多组串行校验",
                display_field=display_field,
                target=target,
                pipeline_config=pipeline_config,  # type: ignore[arg-type]
            ), []
        if rule_type == "multi_composite_mapping_check" and workflow_hints.mapping_nodes:
            mapping_config = {
                "nodes": _build_multi_nodes_from_hints(
                    workflow_hints.mapping_nodes,
                    fallback_variable_tag=variable_tag,
                    display_field=display_field,
                    mapping=True,
                )
            }
            return RuleIntent(
                verdict="ready",
                rule_type=rule_type,
                confidence=max(intent.confidence, 0.7),
                reasoning_summary=_append_field_correction_summary(
                    intent.reasoning_summary or "已根据结构化线索自动生成多组映射规则。",
                    field_correction_warnings,
                ),
                rule_name=intent.rule_name or f"{sheet}-{key_column}-多组映射校验",
                display_field=display_field,
                target=target,
                mapping_config=mapping_config,  # type: ignore[arg-type]
            ), []
        filters = []
        if filter_field and filter_value:
            filters.append(
                _condition(
                    field=filter_field,
                    operator=filter_operator,
                    expected_value=filter_value,
                )
            )
        assertions = []
        assertion_field = _first_text(workflow_hints.assertion_field, target_field)
        assertion_operator = workflow_hints.assertion_operator or ("regex" if regex_pattern else None)
        assertion_value = _first_text(workflow_hints.assertion_value, regex_pattern, workflow_hints.expected_value)
        if assertion_field and assertion_operator:
            assertions.append(
                _condition(
                    field=assertion_field,
                    operator=assertion_operator,
                    expected_value=assertion_value,
                )
            )
        if rule_type == "multi_composite_pipeline_check":
            pipeline_config = {
                "nodes": [
                    {
                        "node_id": f"ai-node-{uuid4().hex[:8]}",
                        "variable_tag": variable_tag,
                        "display_field": display_field,
                        "filters": filters,
                        "assertions": assertions,
                    }
                ]
            }
            return RuleIntent(
                verdict="ready",
                rule_type=rule_type,
                confidence=max(intent.confidence, 0.7),
                reasoning_summary=_append_field_correction_summary(
                    intent.reasoning_summary or "已根据结构化线索自动生成多组串行规则。",
                    field_correction_warnings,
                ),
                rule_name=intent.rule_name or f"{sheet}-{key_column}-多组串行校验",
                display_field=display_field,
                target=target,
                pipeline_config=pipeline_config,  # type: ignore[arg-type]
            ), []
        mapping_config = {
            "nodes": [
                {
                    "node_id": f"ai-node-{uuid4().hex[:8]}",
                    "variable_tag": variable_tag,
                    "display_field": display_field,
                    "filters": [
                        {
                            **item,
                            "exclusion_ranges": [],
                        }
                        for item in filters
                    ],
                }
            ]
        }
        return RuleIntent(
            verdict="ready",
            rule_type=rule_type,
            confidence=max(intent.confidence, 0.7),
            reasoning_summary=_append_field_correction_summary(
                intent.reasoning_summary or "已根据结构化线索自动生成多组映射规则。",
                field_correction_warnings,
            ),
            rule_name=intent.rule_name or f"{sheet}-{key_column}-多组映射校验",
            display_field=display_field,
            target=target,
            mapping_config=mapping_config,  # type: ignore[arg-type]
        ), []

    return None, [
        MissingItem(
            kind="ability",
            message="当前自然语言线索无法稳定映射到现有规则。",
            suggested_action="none",
        )
    ]


def _build_multi_nodes_from_hints(
    nodes: list[dict[str, Any]],
    *,
    fallback_variable_tag: str,
    display_field: str | None,
    mapping: bool,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, raw_node in enumerate(nodes, start=1):
        if not isinstance(raw_node, dict):
            continue
        variable_tag = _first_text(str(raw_node.get("variable_tag") or ""), fallback_variable_tag)
        filters = [
            _condition_from_hint_dict(item, for_filter=True)
            for item in raw_node.get("filters", [])
            if isinstance(item, dict)
        ]
        filters = [item for item in filters if item is not None]
        assertions = [
            _condition_from_hint_dict(item, for_filter=False)
            for item in raw_node.get("assertions", [])
            if isinstance(item, dict)
        ]
        assertions = [item for item in assertions if item is not None]
        node: dict[str, Any] = {
            "node_id": str(raw_node.get("node_id") or f"ai-node-{index}"),
            "variable_tag": variable_tag,
            "display_field": _first_text(str(raw_node.get("display_field") or ""), display_field),
            "filters": filters,
        }
        if mapping:
            node["filters"] = [{**item, "exclusion_ranges": []} for item in filters]
        else:
            node["assertions"] = assertions
        result.append(node)
    return result


def _condition_from_hint_dict(item: dict[str, Any], *, for_filter: bool) -> dict[str, Any] | None:
    field = _first_text(str(item.get("field") or ""))
    operator = _first_text(str(item.get("operator") or ""))
    if not field or not operator:
        return None
    if for_filter and operator not in {"eq", "ne", "gt", "lt", "not_null", "contains", "not_contains"}:
        return None
    if not for_filter and operator not in {"eq", "ne", "gt", "lt", "not_null", "regex", "unique", "duplicate_required"}:
        return None
    expected_value = _first_text(str(item.get("expected_value") or ""), str(item.get("value") or ""))
    return _condition(
        field=field,
        operator=operator,
        expected_value=expected_value,
        value_source=str(item.get("value_source") or "literal"),
        expected_field=_first_text(str(item.get("expected_field") or "")),
    )


def _infer_hint_rule_type(
    intent: RuleIntent,
    workflow_hints: AiRuleWorkflowHints,
    description: str,
) -> str | None:
    has_filter_assertion_pair = bool(
        (
            workflow_hints.filters
            or (
                workflow_hints.filter_field
                and (workflow_hints.filter_value or workflow_hints.filter_operator == "not_null")
            )
        )
        and workflow_hints.assertion_field
        and (
            workflow_hints.assertion_value
            or workflow_hints.assertion_expected_field
            or workflow_hints.assertion_operator
        )
    )
    has_composite_signals = bool(
        workflow_hints.filters
        or workflow_hints.filter_field
        or workflow_hints.display_field
        or workflow_hints.key_column
        or workflow_hints.composite_columns
    )
    if has_filter_assertion_pair and workflow_hints.rule_type_hint not in {
        "dual_composite_compare",
        "multi_composite_pipeline_check",
        "multi_composite_mapping_check",
        "cross_table_mapping",
    }:
        return "composite_condition_check"
    if workflow_hints.rule_type_hint == "regex_check" and has_composite_signals:
        return "composite_condition_check"
    if workflow_hints.rule_type_hint:
        return workflow_hints.rule_type_hint
    if (
        workflow_hints.left_filter_field
        and workflow_hints.left_filter_value
        and workflow_hints.right_filter_field
        and workflow_hints.right_filter_value
        and workflow_hints.compare_fields
    ):
        return "dual_composite_compare"
    if workflow_hints.pipeline_nodes:
        return "multi_composite_pipeline_check"
    if workflow_hints.mapping_nodes:
        return "multi_composite_mapping_check"
    if workflow_hints.regex_pattern:
        return (
            "composite_condition_check"
            if workflow_hints.filters
            or workflow_hints.filter_field
            or workflow_hints.display_field
            or workflow_hints.key_column
            or workflow_hints.composite_columns
            else "regex_check"
        )
    if intent.rule_type:
        return intent.rule_type
    text = description.lower()
    if any(keyword in description for keyword in ("两组", "两个配置", "两份配置", "是不是相等", "是否相等")):
        return "dual_composite_compare"
    if any(keyword in description for keyword in ("多组串行", "多节点串行", "多级链路", "链路")):
        return "multi_composite_pipeline_check"
    if any(keyword in description for keyword in ("多组映射", "多节点映射", "映射校验")):
        return "multi_composite_mapping_check"
    if any(keyword in description for keyword in ("存在于", "字典表", "字典变量", "包含(in)")):
        return "cross_table_mapping"
    if any(keyword in text for keyword in ("不能为空", "非空", "not null", "not_null")):
        return "not_null"
    if any(keyword in text for keyword in ("唯一", "unique")):
        return "unique"
    if any(keyword in description for keyword in ("升序", "降序", "递增", "递减", "连续", "步长", "顺序")):
        return "sequence_order_check"
    if any(keyword in text for keyword in ("格式", "正则", "regex")):
        return "composite_condition_check" if workflow_hints.filter_field else "regex_check"
    if any(keyword in description for keyword in ("等于", "不等于", "大于", "小于", "只能是", "必须是")):
        return "fixed_value_compare"
    return None


def _workflow_global_filters(
    workflow_hints: AiRuleWorkflowHints,
    *,
    fallback_field: str | None,
    fallback_operator: str | None,
    fallback_value: str | None,
) -> list[AiRuleFilterHint]:
    filters: list[AiRuleFilterHint] = []
    for raw_item in workflow_hints.filters:
        item = _coerce_filter_hint(raw_item)
        if item is None:
            continue
        if item.field and (item.value or item.operator == "not_null") and item not in filters:
            filters.append(item)
    if fallback_field and (fallback_value or fallback_operator == "not_null"):
        fallback = AiRuleFilterHint(
            field=fallback_field,
            operator=fallback_operator or "eq",
            value=fallback_value or "",
        )
        if fallback not in filters:
            filters.append(fallback)
    return filters


def _canonicalize_filter_hints(
    variable: VariableTag | None,
    filters: list[AiRuleFilterHint],
) -> list[AiRuleFilterHint]:
    result: list[AiRuleFilterHint] = []
    for raw_item in filters:
        item = _coerce_filter_hint(raw_item)
        if item is None:
            continue
        resolved_field = _canonical_variable_field(variable, item.field)
        if not resolved_field:
            continue
        next_item = item.model_copy(update={"field": resolved_field})
        if next_item not in result:
            result.append(next_item)
    return result


def _build_hint_composite_config(
    *,
    target_field: str,
    regex_pattern: str | None,
    filter_field: str | None,
    filter_operator: str | None,
    filter_value: str | None,
    filters: list[AiRuleFilterHint] | None = None,
    assertion_field: str | None,
    assertion_operator: str | None,
    assertion_value: str | None,
    assertion_value_source: str | None = None,
    assertion_expected_field: str | None = None,
) -> Any | None:
    final_assertion_field = (
        assertion_field if isinstance(assertion_field, str) and assertion_field.strip() else target_field
    )
    final_assertion_operator = assertion_operator or ("regex" if regex_pattern else None)
    final_assertion_value = _first_text(assertion_value, regex_pattern)
    final_value_source = "field" if assertion_value_source == "field" and assertion_expected_field else "literal"
    if not final_assertion_field or not final_assertion_operator:
        return None
    no_value_assertion_operators = {"not_null", "unique", "duplicate_required"}
    if (
        final_value_source == "literal"
        and final_assertion_operator not in no_value_assertion_operators
        and not final_assertion_value
    ):
        return None
    config = {
        "global_filters": [],
        "branches": [
            {
                "branch_id": f"ai-branch-{uuid4().hex[:8]}",
                "filters": [],
                "assertions": [
                    _condition(
                        field=final_assertion_field,
                        operator=final_assertion_operator,
                        expected_value=final_assertion_value,
                        value_source=final_value_source,
                        expected_field=assertion_expected_field,
                    )
                ],
            }
        ],
    }
    for raw_item in filters or []:
        item = _coerce_filter_hint(raw_item)
        if item is None:
            continue
        config["global_filters"].append(
            _condition(
                field=item.field,
                operator=item.operator or "eq",
                expected_value=item.value,
            )
        )
    if filter_field and (filter_value or filter_operator == "not_null") and not any(
        condition.get("field") == filter_field and condition.get("expected_value") == filter_value
        for condition in config["global_filters"]
    ):
        config["global_filters"].append(
            _condition(
                field=filter_field,
                operator=filter_operator or "not_contains",
                expected_value=filter_value or "",
            )
        )
    return config


def _condition(
    *,
    field: str,
    operator: str,
    expected_value: str | None = None,
    value_source: str = "literal",
    expected_field: str | None = None,
) -> dict[str, Any]:
    normalized_expected_value = (expected_value or "").strip()
    normalized_value_source = "field" if value_source == "field" and expected_field else "literal"
    condition: dict[str, Any] = {
        "condition_id": f"ai-condition-{uuid4().hex[:8]}",
        "field": field,
        "operator": operator,
    }
    if operator in {"not_null", "unique", "duplicate_required"}:
        return condition
    if operator == "regex":
        condition["expected_value"] = normalized_expected_value
        return condition
    condition["value_source"] = normalized_value_source
    if normalized_value_source == "field":
        condition["expected_field"] = str(expected_field).strip()
    else:
        condition["expected_value"] = normalized_expected_value
    if (
        normalized_value_source == "literal"
        and operator in {"eq", "ne"}
        and _looks_like_expected_value_set(normalized_expected_value)
    ):
        condition["expected_value_mode"] = "set"
    return condition


def _canonicalize_composite_config_fields(
    config: Any | None,
    variable: VariableTag | None,
) -> Any | None:
    if config is None or variable is None:
        return config
    payload = config.model_dump() if hasattr(config, "model_dump") else dict(config)

    def map_condition(condition: dict[str, Any]) -> None:
        condition["field"] = _canonical_variable_field(variable, condition.get("field")) or ""
        if condition.get("expected_field"):
            condition["expected_field"] = _canonical_variable_field(
                variable,
                condition.get("expected_field"),
            )

    for condition in payload.get("global_filters", []):
        if isinstance(condition, dict):
            map_condition(condition)
    for branch in payload.get("branches", []):
        if not isinstance(branch, dict):
            continue
        for condition in branch.get("filters", []):
            if isinstance(condition, dict):
                map_condition(condition)
        for condition in branch.get("assertions", []):
            if isinstance(condition, dict):
                map_condition(condition)
    return config.__class__.model_validate(payload) if hasattr(config.__class__, "model_validate") else payload


def _looks_like_expected_value_set(value: str) -> bool:
    return "," in value


def _infer_filter_operator_from_description(
    description: str,
    *,
    filter_field: str | None,
    filter_value: str | None,
) -> str | None:
    if not filter_field or not filter_value:
        return None
    if "不包含" in description or "过滤掉" in description or "排除" in description:
        return "not_contains"
    if re.search(r"过滤[^。；;]*包含[^。；;]*(?:的行|记录|数据|字段)", description):
        return "not_contains"
    if "包含" in description or "含有" in description:
        return "contains"
    return None


def _canonicalize_workflow_hints_fields(
    workflow_hints: AiRuleWorkflowHints,
    variable: VariableTag | None,
) -> tuple[AiRuleWorkflowHints, list[str], list[str]]:
    if variable is None:
        return workflow_hints, [], []

    updates: dict[str, Any] = {}
    warnings: list[str] = []
    unresolved: list[str] = []

    def resolve(value: str | None) -> str | None:
        resolved, warning, missing = _resolve_variable_field_for_hint(variable, value)
        if warning and warning not in warnings:
            warnings.append(warning)
        if missing and missing not in unresolved:
            unresolved.append(missing)
        return resolved

    for attr in (
        "target_field",
        "display_field",
        "filter_field",
        "assertion_field",
        "assertion_expected_field",
        "key_column",
        "left_filter_field",
        "right_filter_field",
        "left_key_field",
        "right_key_field",
    ):
        value = getattr(workflow_hints, attr)
        resolved = resolve(value)
        if resolved != value:
            updates[attr] = resolved

    compare_fields: list[str] = []
    for field in workflow_hints.compare_fields:
        resolved = resolve(field)
        if resolved and resolved not in compare_fields:
            compare_fields.append(resolved)
    if compare_fields != workflow_hints.compare_fields:
        updates["compare_fields"] = compare_fields

    composite_columns: list[str] = []
    for field in workflow_hints.composite_columns:
        resolved = resolve(field)
        if resolved and resolved not in composite_columns:
            composite_columns.append(resolved)
    if composite_columns != workflow_hints.composite_columns:
        updates["composite_columns"] = composite_columns

    filters: list[AiRuleFilterHint] = []
    for raw_item in workflow_hints.filters:
        item = _coerce_filter_hint(raw_item)
        if item is None:
            continue
        resolved = resolve(item.field)
        if resolved:
            filters.append(item.model_copy(update={"field": resolved}))
    if filters != workflow_hints.filters:
        updates["filters"] = filters

    if not updates:
        return workflow_hints, warnings, unresolved
    return workflow_hints.model_copy(update=updates), warnings, unresolved


def _canonicalize_workflow_hints_fields_from_metadata(
    workflow_hints: AiRuleWorkflowHints,
    context: dict[str, Any] | None,
    *,
    source_id: str | None,
    sheet: str | None,
) -> tuple[AiRuleWorkflowHints, list[str], list[str]]:
    columns = _metadata_sheet_columns(context, source_id=source_id, sheet=sheet)
    if not columns:
        return workflow_hints, [], []

    updates: dict[str, Any] = {}
    warnings: list[str] = []
    unresolved: list[str] = []

    def resolve(value: str | None) -> str | None:
        resolved, warning, missing = _resolve_metadata_field_for_hint(value, columns)
        if warning and warning not in warnings:
            warnings.append(warning)
        if missing and missing not in unresolved:
            unresolved.append(missing)
        return resolved

    for attr in (
        "target_field",
        "display_field",
        "filter_field",
        "assertion_field",
        "assertion_expected_field",
        "key_column",
        "left_filter_field",
        "right_filter_field",
        "left_key_field",
        "right_key_field",
    ):
        value = getattr(workflow_hints, attr)
        resolved = resolve(value)
        if resolved != value:
            updates[attr] = resolved

    compare_fields: list[str] = []
    for field in workflow_hints.compare_fields:
        resolved = resolve(field)
        if resolved and resolved not in compare_fields:
            compare_fields.append(resolved)
    if compare_fields != workflow_hints.compare_fields:
        updates["compare_fields"] = compare_fields

    composite_columns: list[str] = []
    for field in workflow_hints.composite_columns:
        resolved = resolve(field)
        if resolved and resolved not in composite_columns:
            composite_columns.append(resolved)
    if composite_columns != workflow_hints.composite_columns:
        updates["composite_columns"] = composite_columns

    filters: list[AiRuleFilterHint] = []
    for raw_item in workflow_hints.filters:
        item = _coerce_filter_hint(raw_item)
        if item is None:
            continue
        resolved = resolve(item.field)
        if resolved:
            filters.append(item.model_copy(update={"field": resolved}))
    if filters != workflow_hints.filters:
        updates["filters"] = filters

    if not updates:
        return workflow_hints, warnings, unresolved
    return workflow_hints.model_copy(update=updates), warnings, unresolved


def _metadata_sheet_columns(
    context: dict[str, Any] | None,
    *,
    source_id: str | None,
    sheet: str | None,
) -> list[str]:
    if not context or not source_id or not sheet:
        return []
    metadata_by_source = context.get("source_metadata", {})
    source_metadata = metadata_by_source.get(source_id, {}) if isinstance(metadata_by_source, dict) else {}
    raw_sheets = source_metadata.get("sheets") if isinstance(source_metadata, dict) else None
    if not isinstance(raw_sheets, list):
        return []

    sheet_candidates = [
        str(raw_sheet.get("name", ""))
        for raw_sheet in raw_sheets
        if isinstance(raw_sheet, dict)
    ]
    resolved_sheet, _issue = _resolve_identifier_exact_or_trim(sheet, sheet_candidates)
    if resolved_sheet is None:
        return []
    matched_sheet = next(
        (
            raw_sheet
            for raw_sheet in raw_sheets
            if isinstance(raw_sheet, dict) and str(raw_sheet.get("name", "")) == resolved_sheet
        ),
        None,
    )
    raw_columns = matched_sheet.get("columns") if isinstance(matched_sheet, dict) else None
    if not isinstance(raw_columns, list):
        return []
    return [str(column) for column in raw_columns]


def _resolve_metadata_field_for_hint(
    field: str | None,
    columns: list[str],
) -> tuple[str | None, str | None, str | None]:
    if not field:
        return field, None, None
    normalized = field.strip()
    if not normalized or normalized == "__key__":
        return normalized, None, None
    if _is_placeholder_key_column(normalized):
        return None, None, None

    exact_or_trim, issue = _resolve_identifier_exact_or_trim(normalized, columns)
    if exact_or_trim:
        return exact_or_trim, None, None
    if issue == "ambiguous":
        return normalized, None, f"{normalized}(不唯一)"

    fuzzy_match = _unique_fuzzy_field_match(normalized, columns)
    if fuzzy_match:
        return (
            fuzzy_match,
            f"已根据目标 Sheet 表头将 {normalized} 修正为 {fuzzy_match}，请确认。",
            None,
        )
    return normalized, None, normalized


def _resolve_variable_field_for_hint(
    variable: VariableTag,
    field: str | None,
) -> tuple[str | None, str | None, str | None]:
    if not field:
        return field, None, None
    normalized = field.strip()
    if not normalized or normalized == "__key__":
        return normalized, None, None
    if _is_placeholder_key_column(normalized):
        return None, None, None

    candidates = _variable_field_candidates(variable)
    for candidate in candidates:
        if candidate.strip() == normalized:
            return candidate, None, None

    fuzzy_match = _unique_fuzzy_field_match(normalized, candidates)
    if fuzzy_match:
        return (
            fuzzy_match,
            f"已根据变量池字段将 {normalized} 修正为 {fuzzy_match}，请确认。",
            None,
        )
    return normalized, None, normalized


def _variable_field_candidates(variable: VariableTag) -> list[str]:
    result: list[str] = []
    for candidate in [variable.column, variable.key_column, *(variable.columns or [])]:
        if isinstance(candidate, str) and candidate.strip() and candidate not in result:
            result.append(candidate)
    return result


def _resolve_identifier_exact_or_trim(
    requested: str | None,
    candidates: list[str],
) -> tuple[str | None, str | None]:
    if not isinstance(requested, str) or not requested.strip():
        return None, "missing"
    normalized = requested.strip()
    exact_matches = [candidate for candidate in candidates if candidate == requested]
    if len(exact_matches) == 1:
        return exact_matches[0], None
    trim_matches = [candidate for candidate in candidates if candidate.strip() == normalized]
    if len(trim_matches) == 1:
        return trim_matches[0], None
    if len(trim_matches) > 1:
        return None, "ambiguous"
    return None, "missing"


def _unique_fuzzy_field_match(field: str, candidates: list[str]) -> str | None:
    if not candidates:
        return None
    normalized = field.lower()
    trailing_number = re.search(r"(\d+)$", field)
    candidate_pool = candidates
    if trailing_number:
        suffix = trailing_number.group(1)
        candidate_pool = [candidate for candidate in candidates if candidate.strip().endswith(suffix)]
        if not candidate_pool:
            return None

    scored = sorted(
        (
            (SequenceMatcher(None, normalized, candidate.strip().lower()).ratio(), candidate)
            for candidate in candidate_pool
        ),
        reverse=True,
    )
    if not scored:
        return None
    best_score, best_candidate = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0.0
    threshold = 0.80 if trailing_number else 0.92
    if best_score >= threshold and best_score - second_score >= 0.03:
        return best_candidate
    return None


def _append_field_correction_summary(summary: str, warnings: list[str]) -> str:
    if not warnings:
        return summary
    correction_text = "；".join(warnings)
    if correction_text in summary:
        return summary
    return f"{summary}；{correction_text}"


def _canonical_variable_field(variable: VariableTag | None, field: str | None) -> str | None:
    if not field:
        return field
    normalized = field.strip()
    if variable is None:
        return normalized
    candidates = [
        variable.column,
        variable.key_column,
        *(variable.columns or []),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip() == normalized:
            return candidate
    return normalized


def _infer_metadata_key_column(
    context: dict[str, Any] | None,
    *,
    source_id: str | None,
    sheet: str | None,
) -> str | None:
    if not context or not source_id or not sheet:
        return None
    metadata_by_source = context.get("source_metadata", {})
    source_metadata = metadata_by_source.get(source_id, {}) if isinstance(metadata_by_source, dict) else {}
    raw_sheets = source_metadata.get("sheets") if isinstance(source_metadata, dict) else None
    if not isinstance(raw_sheets, list):
        return None
    sheet_candidates = [
        str(raw_sheet.get("name", ""))
        for raw_sheet in raw_sheets
        if isinstance(raw_sheet, dict)
    ]
    resolved_sheet, _issue = _resolve_identifier_exact_or_trim(sheet, sheet_candidates)
    if resolved_sheet is None:
        return None
    matched_sheet = next(
        (
            raw_sheet
            for raw_sheet in raw_sheets
            if isinstance(raw_sheet, dict) and str(raw_sheet.get("name", "")) == resolved_sheet
        ),
        None,
    )
    raw_columns = matched_sheet.get("columns") if isinstance(matched_sheet, dict) else None
    if not isinstance(raw_columns, list):
        return None
    columns = [str(column) for column in raw_columns]
    for key_candidate in ("INT_ID", "INT_Id", "ID"):
        resolved_key, _issue = _resolve_identifier_exact_or_trim(key_candidate, columns)
        if resolved_key:
            return resolved_key
    return None


def _resolve_hint_composite_columns(
    workflow_hints: AiRuleWorkflowHints,
    *,
    variable: VariableTag | None = None,
    target_field: str,
    display_field: str | None,
    filter_field: str | None,
) -> tuple[str | None, list[str]]:
    columns = _unique_texts(
        [
            *(variable.columns if variable is not None else []),
            *(column for column in workflow_hints.composite_columns if not _is_placeholder_key_column(column)),
            _clean_key_column(workflow_hints.key_column),
            variable.key_column if variable is not None else None,
            display_field,
            target_field,
            filter_field,
            *(
                item.field
                for item in (_coerce_filter_hint(raw_item) for raw_item in workflow_hints.filters)
                if item is not None
            ),
        ]
    )
    key_column = _first_text(_clean_key_column(workflow_hints.key_column), variable.key_column if variable is not None else None)
    if not key_column and columns:
        key_column = next(
            (
                column
                for column in columns
                if column.strip().lower() in {"int_id", "id"}
            ),
            None,
        )
    return key_column, columns


def _is_placeholder_key_column(value: Any) -> bool:
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


def _clean_key_column(value: str | None) -> str | None:
    return None if _is_placeholder_key_column(value) else _first_text(value)


def _first_text(*values: str | None) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _unique_texts(values: list[str | None]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = value.strip() if isinstance(value, str) else ""
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _derive_source_id(source_url: str | None) -> str | None:
    if not source_url:
        return None
    raw_name = source_url.rstrip("/").split("/")[-1].split("?")[0].split("#")[0]
    stem = raw_name.rsplit(".", 1)[0] if "." in raw_name else raw_name
    source_id = re.sub(r"[^A-Za-z0-9_]+", "_", stem).strip("_")
    return source_id or None


def _guess_source_type(source_url: str | None) -> str:
    if not source_url:
        return "local_excel"
    lowered = source_url.lower()
    if lowered.startswith(("http://", "https://", "svn://")):
        return "svn"
    return "local_excel"


def _needs_input(intent: RuleIntent, *missing: MissingItem) -> RuleDraftResponse:
    return RuleDraftResponse(
        verdict="needs_input",
        rule_type=intent.rule_type,
        confidence=intent.confidence,
        reasoning_summary=intent.reasoning_summary or "规则类型可支持，但需要先补齐配置。",
        missing=[*intent.missing, *missing],
        rejection_reason=None,
    )


def _resolve_variable(
    variable_intent: VariableIntent,
    context: dict[str, Any],
) -> tuple[VariableTag | None, list[MissingItem], DataSource | None]:
    variables: list[VariableTag] = context["variables"]
    sources: list[DataSource] = context["sources"]
    existing_by_tag = {variable.tag: variable for variable in variables}
    if variable_intent.tag and variable_intent.tag in existing_by_tag:
        return existing_by_tag[variable_intent.tag], [], None

    matched = _find_existing_variable(variable_intent, variables)
    if matched is not None:
        return matched, [], None

    source, source_to_add, source_missing = _resolve_source(variable_intent, sources)
    if source_missing:
        return None, source_missing, None

    if not (variable_intent.sheet or "").strip():
        return None, [
            MissingItem(
                kind="variable",
                message="缺少 Sheet 名称，无法添加变量。",
                suggested_action="open_single_variable_dialog",
                prefill=_variable_prefill(variable_intent, source),
            )
        ], source_to_add

    metadata_missing = _validate_variable_metadata(variable_intent, source, context)
    if metadata_missing:
        return None, [metadata_missing], source_to_add

    if variable_intent.variable_kind == "composite":
        columns = [column for column in variable_intent.columns if column.strip()]
        key_column = (variable_intent.key_column or "").strip()
        if len(columns) < 2 or not key_column:
            return None, [
                MissingItem(
                    kind="variable",
                    message="组合变量至少需要 2 个列名和 1 个 Key 列。",
                    suggested_action="open_composite_variable_dialog",
                    prefill=_variable_prefill(variable_intent, source),
                )
            ], source_to_add
        tag = variable_intent.tag or _build_composite_tag(source.id, variable_intent.sheet or "", key_column)
        return VariableTag(
            tag=tag,
            source_id=source.id,
            sheet=variable_intent.sheet or "",
            variable_kind="composite",
            columns=columns,
            key_column=key_column,
            append_index_to_key=variable_intent.append_index_to_key,
            expected_type="json",
        ), [], source_to_add

    column = (variable_intent.column or "").strip()
    if not column:
        return None, [
            MissingItem(
                kind="variable",
                message="缺少列名，无法添加单变量。",
                suggested_action="open_single_variable_dialog",
                prefill=_variable_prefill(variable_intent, source),
            )
        ], source_to_add
    tag = variable_intent.tag or _build_single_tag(source.id, variable_intent.sheet or "", column)
    return VariableTag(
        tag=tag,
        source_id=source.id,
        sheet=variable_intent.sheet or "",
        variable_kind="single",
        column=column,
        expected_type=variable_intent.expected_type or "str",
    ), [], source_to_add


def _resolve_source(
    variable_intent: VariableIntent,
    sources: list[DataSource],
) -> tuple[DataSource, DataSource | None, list[MissingItem]]:
    source_id = (variable_intent.source_id or "").strip()
    if source_id:
        existing = next((source for source in sources if source.id == source_id), None)
        if existing is not None:
            return existing, None, []
    elif sources:
        return sources[0], None, []

    path_or_url = (variable_intent.path_or_url or "").strip()
    if source_id and path_or_url:
        source = DataSource(
            id=source_id,
            type=variable_intent.source_type if variable_intent.source_type in {"local_excel", "svn"} else "local_excel",  # type: ignore[arg-type]
            pathOrUrl=path_or_url,
        )
        return source, source, []

    return DataSource(id=source_id or "source", type="local_excel", pathOrUrl=""), None, [
        MissingItem(
            kind="source",
            message="缺少可用数据源，无法自动添加变量和规则。",
            suggested_action="open_source_dialog",
            prefill={
                "id": source_id,
                "type": variable_intent.source_type or "local_excel",
                "pathOrUrl": path_or_url,
            },
        )
    ]


def _find_existing_variable(
    intent: VariableIntent,
    variables: list[VariableTag],
) -> VariableTag | None:
    source_id = (intent.source_id or "").strip()
    sheet = (intent.sheet or "").strip()
    column = (intent.column or "").strip()
    columns = [
        item.strip()
        for item in intent.columns
        if item.strip() and not _is_placeholder_key_column(item)
    ]
    key_column = _clean_key_column(intent.key_column)

    for variable in variables:
        if source_id and variable.source_id != source_id:
            continue
        if sheet and variable.sheet.strip() != sheet:
            continue
        if intent.variable_kind == "composite":
            if (variable.variable_kind or "single") != "composite":
                continue
            available_fields = _variable_field_candidates(variable)
            if key_column and not _resolve_identifier_exact_or_trim(key_column, available_fields)[0]:
                continue
            if columns and not all(_resolve_identifier_exact_or_trim(item, available_fields)[0] for item in columns):
                continue
            return variable
        if (
            (variable.variable_kind or "single") == "single"
            and column
            and _resolve_identifier_exact_or_trim(column, [variable.column or ""])[0]
        ):
            return variable
    return None


def _validate_variable_metadata(
    intent: VariableIntent,
    source: DataSource,
    context: dict[str, Any],
) -> MissingItem | None:
    """用已读取的元数据校验 Sheet/列是否存在；没有元数据时降级放行。"""
    metadata_by_source = context.get("source_metadata", {})
    source_metadata = metadata_by_source.get(source.id, {}) if isinstance(metadata_by_source, dict) else {}
    raw_sheets = source_metadata.get("sheets") if isinstance(source_metadata, dict) else None
    if not isinstance(raw_sheets, list) or not raw_sheets:
        return None

    sheet_name = (intent.sheet or "").strip()
    matched_sheet = None
    sheet_candidates = [
        str(sheet.get("name", ""))
        for sheet in raw_sheets
        if isinstance(sheet, dict)
    ]
    resolved_sheet_name, _sheet_issue = _resolve_identifier_exact_or_trim(sheet_name, sheet_candidates)
    if resolved_sheet_name:
        matched_sheet = next(
            (
                sheet
                for sheet in raw_sheets
                if isinstance(sheet, dict) and str(sheet.get("name", "")) == resolved_sheet_name
            ),
            None,
        )
        intent.sheet = resolved_sheet_name
    suggested_action = (
        "open_composite_variable_dialog"
        if intent.variable_kind == "composite"
        else "open_single_variable_dialog"
    )
    if matched_sheet is None:
        return MissingItem(
            kind="variable",
            message=f"数据源 {source.id} 未读取到 Sheet：{sheet_name}。",
            suggested_action=suggested_action,
            prefill=_variable_prefill(intent, source),
        )

    raw_columns = matched_sheet.get("columns") if isinstance(matched_sheet, dict) else None
    if not isinstance(raw_columns, list) or not raw_columns:
        return None
    columns = [str(column) for column in raw_columns]
    if intent.variable_kind == "composite":
        resolved_columns: list[str] = []
        missing_columns: list[str] = []
        for column in intent.columns:
            requested_column = column.strip()
            if not requested_column or _is_placeholder_key_column(requested_column):
                continue
            resolved_column, _warning, missing_column = _resolve_metadata_field_for_hint(requested_column, columns)
            if missing_column:
                missing_columns.append(missing_column)
            elif resolved_column not in resolved_columns:
                resolved_columns.append(resolved_column)

        key_column = _clean_key_column(intent.key_column)
        if key_column:
            resolved_key_column, _warning, missing_key_column = _resolve_metadata_field_for_hint(key_column, columns)
            if missing_key_column:
                missing_columns.append(missing_key_column)
            else:
                intent.key_column = resolved_key_column
        else:
            intent.key_column = None
        if missing_columns:
            return MissingItem(
                kind="variable",
                message=f"Sheet {sheet_name} 缺少列：{', '.join(missing_columns)}。",
                suggested_action="open_composite_variable_dialog",
                prefill=_variable_prefill(intent, source),
            )
        intent.columns = resolved_columns
        return None

    column = (intent.column or "").strip()
    resolved_column, _warning, missing_column = _resolve_metadata_field_for_hint(column, columns)
    if column and missing_column:
        missing_text = missing_column
        return MissingItem(
            kind="variable",
            message=f"Sheet {sheet_name} 缺少列：{missing_text}。",
            suggested_action="open_single_variable_dialog",
            prefill=_variable_prefill(intent, source),
        )
    if resolved_column:
        intent.column = resolved_column
    return None


def _build_rule_definition(
    intent: RuleIntent,
    *,
    target_variable: VariableTag | None,
    reference_variable: VariableTag | None,
    description: str,
) -> tuple[FixedRuleDefinition | None, list[MissingItem]]:
    rule_type = intent.rule_type
    if rule_type is None:
        return None, []
    target_tag = target_variable.tag if target_variable is not None else ""
    rule_name = (intent.rule_name or "").strip() or _default_rule_name(
        rule_type,
        target_variable,
        intent,
        description,
    )
    base = {
        "rule_id": f"ai-rule-{uuid4().hex[:12]}",
        "group_id": DEFAULT_GROUP_ID,
        "rule_name": rule_name,
        "target_variable_tag": target_tag,
        "display_field": (intent.display_field or "").strip() or None,
        "rule_type": rule_type,
    }

    if rule_type == "fixed_value_compare":
        if not intent.operator or not (intent.expected_value or "").strip():
            return None, [
                MissingItem(
                    kind="parameter",
                    message="固定值比较需要操作符和比较值。",
                    suggested_action="edit_description",
                )
            ]
        return FixedRuleDefinition(
            **base,
            operator=intent.operator,
            expected_value=(intent.expected_value or "").strip(),
            expected_value_mode=intent.expected_value_mode,
        ), []

    if rule_type == "regex_check":
        pattern = (intent.regex_pattern or intent.expected_value or "").strip()
        if not pattern:
            return None, [
                MissingItem(
                    kind="parameter",
                    message="正则校验需要正则表达式。",
                    suggested_action="edit_description",
                )
            ]
        return FixedRuleDefinition(**base, expected_value=pattern), []

    if rule_type == "sequence_order_check":
        return FixedRuleDefinition(
            **base,
            sequence_direction=intent.sequence_direction or "asc",
            sequence_step=(intent.sequence_step or "1").strip(),
            sequence_start_mode=intent.sequence_start_mode or "auto",
            sequence_start_value=(intent.sequence_start_value or "").strip() or None,
        ), []

    if rule_type == "cross_table_mapping":
        if reference_variable is None:
            return None, [
                MissingItem(
                    kind="variable",
                    message="包含(in) 规则需要基础字典变量。",
                    suggested_action="edit_description",
                )
            ]
        return FixedRuleDefinition(
            **base,
            reference_variable_tag=reference_variable.tag,
        ), []

    if rule_type == "composite_condition_check":
        if intent.composite_config is None:
            return None, [
                MissingItem(
                    kind="parameter",
                    message="组合分支校验需要全局筛选、分支筛选或分支断言配置。",
                    suggested_action="edit_description",
                )
            ]
        return FixedRuleDefinition(**base, composite_config=intent.composite_config), []

    if rule_type == "dual_composite_compare":
        if reference_variable is None or not intent.comparisons:
            return None, [
                MissingItem(
                    kind="parameter",
                    message="跨组变量校验需要目标变量和至少一条字段比对。",
                    suggested_action="edit_description",
                )
            ]
        return FixedRuleDefinition(
            **base,
            reference_variable_tag=reference_variable.tag,
            key_check_mode=intent.key_check_mode or "baseline_only",
            left_key_field=intent.left_key_field or "__key__",
            right_key_field=intent.right_key_field or "__key__",
            comparisons=intent.comparisons,
            left_filters=intent.left_filters,  # type: ignore[arg-type]
            right_filters=intent.right_filters,  # type: ignore[arg-type]
        ), []

    if rule_type == "multi_composite_pipeline_check":
        if intent.pipeline_config is None or not intent.pipeline_config.nodes:
            return None, [
                MissingItem(
                    kind="parameter",
                    message="多组串行校验需要至少一个节点配置。",
                    suggested_action="edit_description",
                )
            ]
        first_tag = intent.pipeline_config.nodes[0].variable_tag
        return FixedRuleDefinition(
            **{**base, "target_variable_tag": first_tag},
            pipeline_config=intent.pipeline_config,
        ), []

    if rule_type == "multi_composite_mapping_check":
        if intent.mapping_config is None or not intent.mapping_config.nodes:
            return None, [
                MissingItem(
                    kind="parameter",
                    message="多组映射校验需要至少一个节点配置。",
                    suggested_action="edit_description",
                )
            ]
        first_tag = intent.mapping_config.nodes[0].variable_tag
        return FixedRuleDefinition(
            **{**base, "target_variable_tag": first_tag},
            mapping_config=intent.mapping_config,
        ), []

    return FixedRuleDefinition(**base), []


def _default_rule_name(
    rule_type: str,
    variable: VariableTag | None,
    intent: RuleIntent,
    description: str,
) -> str:
    column = variable.column if variable is not None else None
    if variable is not None and (variable.variable_kind or "single") == "composite":
        column = variable.key_column
    target_text = column or variable.tag if variable is not None else description[:20]
    if rule_type == "not_null":
        return f"{target_text}-非空校验"
    if rule_type == "unique":
        return f"{target_text}-唯一校验"
    if rule_type == "regex_check":
        return f"{target_text}-正则校验"
    if rule_type == "fixed_value_compare":
        return f"{target_text}-{intent.operator or '比较'}-{intent.expected_value or ''}".strip("-")
    return f"{target_text}-{rule_type}"


def _variable_prefill(intent: VariableIntent, source: DataSource) -> dict[str, Any]:
    return {
        "source_id": source.id,
        "sheet": intent.sheet or "",
        "column": intent.column or "",
        "columns": intent.columns,
        "key_column": intent.key_column or "",
        "tag": intent.tag or "",
        "expected_type": intent.expected_type,
    }


def _variable_exists(tag: str, context: dict[str, Any]) -> bool:
    return any(variable.tag == tag for variable in context["variables"])


def _build_single_tag(source_id: str, sheet: str, column: str) -> str:
    return f"[{source_id or 'source'}-{sheet or 'sheet'}-{column or 'column'}]"


def _build_composite_tag(source_id: str, sheet: str, key_column: str) -> str:
    return f"[{source_id or 'source'}-{sheet or 'sheet'}-{key_column or 'key'}-mapping]"


def _unique_sources(sources: list[DataSource]) -> list[DataSource]:
    return list({source.id: source for source in sources if source.id and source.pathOrUrl}.values())


def _unique_variables(variables: list[VariableTag]) -> list[VariableTag]:
    return list({variable.tag: variable for variable in variables if variable.tag}.values())


def _get_context_variable(context: dict[str, Any] | None, tag: str | None) -> VariableTag | None:
    if not context or not tag:
        return None
    for variable in context.get("variables", []):
        if isinstance(variable, VariableTag) and variable.tag == tag:
            return variable
    return None


def _variable_matches_source_sheet(
    variable: VariableTag,
    source_id: str | None,
    sheet: str | None,
) -> bool:
    if source_id and variable.source_id != source_id:
        return False
    if sheet and variable.sheet.strip() != sheet.strip():
        return False
    return True


def _find_existing_composite_variable_for_hints(
    context: dict[str, Any] | None,
    *,
    source_id: str | None,
    sheet: str | None,
    required_fields: list[str],
) -> VariableTag | None:
    if not context or not source_id or not sheet:
        return None
    cleaned_required_fields = [
        field.strip()
        for field in required_fields
        if isinstance(field, str) and field.strip() and not _is_placeholder_key_column(field)
    ]
    if not cleaned_required_fields:
        return None

    matches: list[VariableTag] = []
    for variable in context.get("variables", []):
        if not isinstance(variable, VariableTag):
            continue
        if (variable.variable_kind or "single") != "composite":
            continue
        if variable.source_id != source_id:
            continue
        if variable.sheet.strip() != sheet.strip():
            continue
        if all(_resolve_variable_field_for_hint(variable, field)[2] is None for field in cleaned_required_fields):
            matches.append(variable)

    if len(matches) != 1:
        return None
    return matches[0]


def _default_target_field_from_variable(variable: VariableTag | None) -> str | None:
    if variable is None:
        return None
    if (variable.variable_kind or "single") == "composite":
        return variable.key_column or (variable.columns or [None])[0]
    return variable.column


def _variable_intent_from_existing(variable: VariableTag | None) -> VariableIntent | None:
    if variable is None:
        return None
    return VariableIntent(
        tag=variable.tag,
        source_id=variable.source_id,
        sheet=variable.sheet,
        variable_kind=variable.variable_kind or "single",
        column=variable.column,
        columns=variable.columns or [],
        key_column=variable.key_column,
        append_index_to_key=variable.append_index_to_key,
        expected_type=variable.expected_type,
    )


def _collect_rule_dependency_tags(rule: FixedRuleDefinition) -> set[str]:
    tags = {
        (rule.target_variable_tag or "").strip(),
        (rule.reference_variable_tag or "").strip(),
    }
    if rule.pipeline_config is not None:
        tags.update(node.variable_tag.strip() for node in rule.pipeline_config.nodes)
    if rule.mapping_config is not None:
        tags.update(node.variable_tag.strip() for node in rule.mapping_config.nodes)
    return {tag for tag in tags if tag}


def _enforce_variable_scope(
    response: RuleDraftResponse,
    *,
    context: dict[str, Any],
    selected_variable_tags: list[str],
    allow_auto_complete: bool,
) -> RuleDraftResponse:
    if allow_auto_complete:
        return response

    selected_tags = {tag.strip() for tag in selected_variable_tags if tag.strip()}
    if response.verdict != "ready":
        return response

    if not selected_tags:
        return RuleDraftResponse(
            verdict="needs_input",
            rule_type=response.rule_type,
            confidence=response.confidence,
            reasoning_summary="请先在智能规则页签选择变量池变量；当前模式不会自动新增数据源或变量。",
            missing=[
                MissingItem(
                    kind="variable",
                    message="未选择变量池变量，无法生成只复用现有变量的规则。",
                    suggested_action="none",
                )
            ],
        )

    existing_tags = {variable.tag for variable in context.get("variables", []) if isinstance(variable, VariableTag)}
    unknown_selected = sorted(tag for tag in selected_tags if tag not in existing_tags)
    if unknown_selected:
        return RuleDraftResponse(
            verdict="needs_input",
            rule_type=response.rule_type,
            confidence=response.confidence,
            reasoning_summary="已选择的变量不在当前变量池中，请重新选择变量后再校验。",
            missing=[
                MissingItem(
                    kind="variable",
                    message=f"变量池中不存在：{', '.join(unknown_selected)}。",
                    suggested_action="none",
                )
            ],
        )

    dependency_tags: set[str] = set()
    for rule in response.draft.rules_to_add:
        dependency_tags.update(_collect_rule_dependency_tags(rule))
    if not dependency_tags:
        return RuleDraftResponse(
            verdict="needs_input",
            rule_type=response.rule_type,
            confidence=response.confidence,
            reasoning_summary="规则草稿没有明确引用变量，无法在只复用变量模式下添加。",
            missing=[
                MissingItem(
                    kind="variable",
                    message="请在结构化表单中选择目标变量，必要时选择引用变量或左右变量。",
                    suggested_action="none",
                )
            ],
        )

    out_of_scope = sorted(tag for tag in dependency_tags if tag not in selected_tags)
    if out_of_scope:
        return RuleDraftResponse(
            verdict="needs_input",
            rule_type=response.rule_type,
            confidence=response.confidence,
            reasoning_summary="当前草稿引用了未选择的变量；请调整变量选择后重新校验。",
            missing=[
                MissingItem(
                    kind="variable",
                    message=f"未选择但被规则引用的变量：{', '.join(out_of_scope)}。",
                    suggested_action="none",
                )
            ],
        )

    response.draft.sources_to_add = []
    response.draft.variables_to_add = []
    response.draft.reuse_variable_tags = sorted(
        set(response.draft.reuse_variable_tags).union(dependency_tags)
    )
    return response


def _attach_extension_suggestions(
    response: RuleDraftResponse,
    *,
    description: str,
) -> RuleDraftResponse:
    if response.verdict != "rejected" or response.extension_suggestions:
        return response
    response.extension_suggestions = _build_extension_suggestions(description, response.rejection_reason)
    return response


def _build_extension_suggestions(description: str, reason: str | None) -> list[str]:
    text = f"{description} {reason or ''}"
    suggestions: list[str] = []
    if any(keyword in text for keyword in ("公式", "计算后", "求和", "平均", "聚合")):
        suggestions.append("新增公式/表达式校验规则，支持对字段计算结果再做比较。")
    if any(keyword in text for keyword in ("跨行", "统计", "分组", "汇总")):
        suggestions.append("新增分组聚合或跨行统计规则，支持按 Key 汇总后校验数量、求和或唯一性。")
    if any(keyword in text for keyword in ("脚本", "自定义", "复杂逻辑")):
        suggestions.append("新增受控脚本或自定义校验插件能力，用白名单方式承载复杂业务逻辑。")
    if not suggestions:
        suggestions.append("扩展规则库时优先新增一个明确的 rule_type，并补齐前端配置表单、后端执行器和测试快照。")
    suggestions.append("如果能拆成非空、唯一、固定值、正则、组合分支或跨组变量比对，可先用现有规则临时覆盖部分场景。")
    return suggestions


async def _persist_draft_history(
    db: AsyncSession,
    *,
    project_id: int,
    user_id: int,
    description: str,
    response: RuleDraftResponse,
) -> AiRuleDraftRecord:
    record = AiRuleDraftRecord(
        project_id=project_id,
        user_id=user_id,
        description=description,
        verdict=response.verdict,
        rule_type=response.rule_type,
        response_json=response.model_dump_json(exclude={"draft_id", "created_at"}),
        applied=response.applied,
    )
    db.add(record)
    await db.flush()
    await _trim_draft_history(db, project_id=project_id, user_id=user_id)
    await db.commit()
    await db.refresh(record)
    return record


async def _trim_draft_history(db: AsyncSession, *, project_id: int, user_id: int) -> None:
    result = await db.execute(
        select(AiRuleDraftRecord.id)
        .where(
            AiRuleDraftRecord.project_id == project_id,
            AiRuleDraftRecord.user_id == user_id,
        )
        .order_by(AiRuleDraftRecord.created_at.desc(), AiRuleDraftRecord.id.desc())
        .offset(DRAFT_HISTORY_LIMIT)
    )
    stale_ids = [row[0] for row in result.all()]
    if stale_ids:
        await db.execute(delete(AiRuleDraftRecord).where(AiRuleDraftRecord.id.in_(stale_ids)))


async def _get_owned_draft(
    db: AsyncSession,
    project_id: int,
    user_id: int,
    draft_id: int,
) -> AiRuleDraftRecord | None:
    result = await db.execute(
        select(AiRuleDraftRecord).where(
            AiRuleDraftRecord.id == draft_id,
            AiRuleDraftRecord.project_id == project_id,
            AiRuleDraftRecord.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


def _parse_extra_headers(raw_json: str) -> dict[str, str]:
    try:
        parsed = json.loads(raw_json or "{}")
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(value) for key, value in parsed.items()}


def _summarize_validation_error(error: ValidationError) -> str:
    first_error = error.errors()[0] if error.errors() else {}
    loc = ".".join(str(item) for item in first_error.get("loc", []))
    msg = first_error.get("msg", "字段校验失败")
    return f"{loc}: {msg}" if loc else str(msg)


def _format_dt(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None

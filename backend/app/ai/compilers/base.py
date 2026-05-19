"""Shared contracts for deterministic workflow-hint compilers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from backend.app.ai.schemas import RuleIntent, VariableIntent
from backend.app.ai.workflow_hints import AiRuleFilterHint, AiRuleWorkflowHints, MissingItem


@dataclass(frozen=True)
class WorkflowCompileState:
    intent: RuleIntent
    workflow_hints: AiRuleWorkflowHints
    rule_type: str
    description: str
    context: dict[str, Any] | None
    target_variable: Any | None
    reference_variable: Any | None
    source_id: str | None
    source_type: str | None
    source_url: str | None
    sheet: str | None
    target_field: str | None
    display_field: str | None
    filter_field: str | None
    filter_value: str | None
    filter_operator: str
    filter_hints: list[AiRuleFilterHint]
    regex_pattern: str | None
    common_variable_kwargs: dict[str, Any]
    field_correction_warnings: list[str]


@dataclass(frozen=True)
class WorkflowCompilerHelpers:
    first_text: Callable[..., str | None]
    derive_source_id: Callable[[str | None], str | None]
    unique_texts: Callable[[list[Any]], list[str]]
    variable_intent_from_existing: Callable[[Any | None], VariableIntent | None]
    append_field_correction_summary: Callable[[str, list[str]], str]
    resolve_hint_composite_columns: Callable[..., tuple[str | None, list[str]]]
    infer_metadata_key_column: Callable[..., str | None]
    canonical_variable_field: Callable[[Any | None, str | None], str | None]
    canonicalize_filter_hints: Callable[[Any | None, list[AiRuleFilterHint]], list[AiRuleFilterHint]]
    build_hint_composite_config: Callable[..., Any | None]
    canonicalize_composite_config_fields: Callable[[Any | None, Any | None], Any | None]
    condition: Callable[..., dict[str, Any]]
    build_composite_tag: Callable[[str, str, str], str]
    build_multi_nodes_from_hints: Callable[..., list[dict[str, Any]]]


class WorkflowHintCompiler(Protocol):
    """Compiler for one or more workflow-hint rule types."""

    rule_types: set[str]

    def compile(
        self,
        state: WorkflowCompileState,
        helpers: WorkflowCompilerHelpers,
    ) -> tuple[RuleIntent | None, list[MissingItem]]:
        """Compile normalized workflow hints into a standard RuleIntent."""

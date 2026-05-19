"""Compilers for multi-composite rule hints."""

from __future__ import annotations

from uuid import uuid4

from backend.app.ai.compilers.base import WorkflowCompileState, WorkflowCompilerHelpers
from backend.app.ai.schemas import RuleIntent, VariableIntent
from backend.app.ai.workflow_hints import MissingItem


class MultiCompositeCompiler:
    rule_types = {"multi_composite_pipeline_check", "multi_composite_mapping_check"}

    def compile(
        self,
        state: WorkflowCompileState,
        helpers: WorkflowCompilerHelpers,
    ) -> tuple[RuleIntent | None, list[MissingItem]]:
        hints = state.workflow_hints
        target_variable = state.target_variable
        if target_variable is not None and (target_variable.variable_kind or "single") != "composite":
            return None, [MissingItem(kind="variable", message="多组规则需要选择组合变量。", suggested_action="none")]

        key_column, composite_columns = helpers.resolve_hint_composite_columns(
            hints,
            variable=target_variable,
            target_field=state.target_field,
            display_field=state.display_field,
            filter_field=state.filter_field,
        )
        if not key_column or len(composite_columns) < 2:
            return None, [MissingItem(kind="variable", message="多组规则至少需要组合变量 Key 和组合变量列。", suggested_action="none")]

        target = helpers.variable_intent_from_existing(target_variable) or VariableIntent(
            **state.common_variable_kwargs,
            variable_kind="composite",
            columns=composite_columns,
            key_column=key_column,
            append_index_to_key=True,
            expected_type="json",
        )
        variable_tag = target_variable.tag if target_variable else helpers.build_composite_tag(
            state.source_id or "source",
            state.sheet or "sheet",
            key_column,
        )

        if state.rule_type == "multi_composite_pipeline_check" and hints.pipeline_nodes:
            pipeline_config = {
                "nodes": helpers.build_multi_nodes_from_hints(
                    hints.pipeline_nodes,
                    fallback_variable_tag=variable_tag,
                    display_field=state.display_field,
                    mapping=False,
                )
            }
            return self._pipeline_intent(state, target, pipeline_config, key_column, helpers), []
        if state.rule_type == "multi_composite_mapping_check" and hints.mapping_nodes:
            mapping_config = {
                "nodes": helpers.build_multi_nodes_from_hints(
                    hints.mapping_nodes,
                    fallback_variable_tag=variable_tag,
                    display_field=state.display_field,
                    mapping=True,
                )
            }
            return self._mapping_intent(state, target, mapping_config, key_column, helpers), []

        filters = []
        if state.filter_field and state.filter_value:
            filters.append(
                helpers.condition(
                    field=state.filter_field,
                    operator=state.filter_operator,
                    expected_value=state.filter_value,
                )
            )
        assertions = []
        assertion_field = helpers.first_text(hints.assertion_field, state.target_field)
        assertion_operator = hints.assertion_operator or ("regex" if state.regex_pattern else None)
        assertion_value = helpers.first_text(hints.assertion_value, state.regex_pattern, hints.expected_value)
        if assertion_field and assertion_operator:
            assertions.append(
                helpers.condition(
                    field=assertion_field,
                    operator=assertion_operator,
                    expected_value=assertion_value,
                )
            )
        if state.rule_type == "multi_composite_pipeline_check":
            pipeline_config = {
                "nodes": [
                    {
                        "node_id": f"ai-node-{uuid4().hex[:8]}",
                        "variable_tag": variable_tag,
                        "display_field": state.display_field,
                        "filters": filters,
                        "assertions": assertions,
                    }
                ]
            }
            return self._pipeline_intent(state, target, pipeline_config, key_column, helpers), []

        mapping_config = {
            "nodes": [
                {
                    "node_id": f"ai-node-{uuid4().hex[:8]}",
                    "variable_tag": variable_tag,
                    "display_field": state.display_field,
                    "filters": [{**item, "exclusion_ranges": []} for item in filters],
                }
            ]
        }
        return self._mapping_intent(state, target, mapping_config, key_column, helpers), []

    def _pipeline_intent(
        self,
        state: WorkflowCompileState,
        target: VariableIntent,
        pipeline_config: dict[str, object],
        key_column: str,
        helpers: WorkflowCompilerHelpers,
    ) -> RuleIntent:
        return RuleIntent(
            verdict="ready",
            rule_type=state.rule_type,
            confidence=max(state.intent.confidence, 0.7),
            reasoning_summary=helpers.append_field_correction_summary(
                state.intent.reasoning_summary or "已根据结构化线索自动生成多组串行规则。",
                state.field_correction_warnings,
            ),
            rule_name=state.intent.rule_name or f"{state.sheet}-{key_column}-多组串行校验",
            display_field=state.display_field,
            target=target,
            pipeline_config=pipeline_config,  # type: ignore[arg-type]
        )

    def _mapping_intent(
        self,
        state: WorkflowCompileState,
        target: VariableIntent,
        mapping_config: dict[str, object],
        key_column: str,
        helpers: WorkflowCompilerHelpers,
    ) -> RuleIntent:
        return RuleIntent(
            verdict="ready",
            rule_type=state.rule_type,
            confidence=max(state.intent.confidence, 0.7),
            reasoning_summary=helpers.append_field_correction_summary(
                state.intent.reasoning_summary or "已根据结构化线索自动生成多组映射规则。",
                state.field_correction_warnings,
            ),
            rule_name=state.intent.rule_name or f"{state.sheet}-{key_column}-多组映射校验",
            display_field=state.display_field,
            target=target,
            mapping_config=mapping_config,  # type: ignore[arg-type]
        )

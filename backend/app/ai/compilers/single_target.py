"""Compilers for single-target and cross-table rule hints."""

from __future__ import annotations

from backend.app.ai.compilers.base import WorkflowCompileState, WorkflowCompilerHelpers
from backend.app.ai.schemas import RuleIntent, VariableIntent
from backend.app.ai.workflow_hints import MissingItem


class SingleTargetCompiler:
    rule_types = {"not_null", "unique", "fixed_value_compare", "regex_check", "sequence_order_check"}

    def compile(
        self,
        state: WorkflowCompileState,
        helpers: WorkflowCompilerHelpers,
    ) -> tuple[RuleIntent | None, list[MissingItem]]:
        intent = state.intent
        hints = state.workflow_hints
        target_variable = state.target_variable
        if target_variable is not None and (target_variable.variable_kind or "single") != "single":
            return None, [
                MissingItem(kind="variable", message="该规则需要选择单变量，当前目标变量是组合变量。", suggested_action="none")
            ]
        if not state.target_field:
            return None, [MissingItem(kind="variable", message="单变量规则需要目标字段。", suggested_action="none")]
        if state.rule_type == "fixed_value_compare" and not (
            (hints.operator or intent.operator) and helpers.first_text(hints.expected_value, intent.expected_value)
        ):
            return None, [MissingItem(kind="parameter", message="固定值比较需要操作符和比较值。", suggested_action="none")]
        if state.rule_type == "regex_check" and not state.regex_pattern:
            return None, [MissingItem(kind="parameter", message="正则校验需要正则表达式。", suggested_action="none")]

        target = helpers.variable_intent_from_existing(target_variable) or VariableIntent(
            **state.common_variable_kwargs,
            variable_kind="single",
            column=state.target_field,
            expected_type=intent.target.expected_type if intent.target else "str",
        )
        return RuleIntent(
            verdict="ready",
            rule_type=state.rule_type,
            confidence=max(intent.confidence, 0.7),
            reasoning_summary=helpers.append_field_correction_summary(
                intent.reasoning_summary or "已根据结构化线索自动补齐数据源、变量和规则。",
                state.field_correction_warnings,
            ),
            rule_name=intent.rule_name,
            display_field=state.display_field,
            target=target,
            operator=hints.operator or intent.operator,
            expected_value=helpers.first_text(hints.expected_value, intent.expected_value),
            expected_value_mode=hints.expected_value_mode or intent.expected_value_mode,
            regex_pattern=state.regex_pattern,
            sequence_direction=hints.sequence_direction or intent.sequence_direction,
            sequence_step=helpers.first_text(hints.sequence_step, intent.sequence_step, "1"),
            sequence_start_mode=hints.sequence_start_mode or intent.sequence_start_mode or "auto",
            sequence_start_value=helpers.first_text(hints.sequence_start_value, intent.sequence_start_value),
        ), []


class CrossTableMappingCompiler:
    rule_types = {"cross_table_mapping"}

    def compile(
        self,
        state: WorkflowCompileState,
        helpers: WorkflowCompilerHelpers,
    ) -> tuple[RuleIntent | None, list[MissingItem]]:
        intent = state.intent
        hints = state.workflow_hints
        target_variable = state.target_variable
        reference_variable = state.reference_variable
        if target_variable is not None and (target_variable.variable_kind or "single") != "single":
            return None, [MissingItem(kind="variable", message="包含(in) 目标变量必须是单变量。", suggested_action="none")]
        if reference_variable is not None and (reference_variable.variable_kind or "single") != "single":
            return None, [MissingItem(kind="variable", message="包含(in) 引用变量必须是单变量。", suggested_action="none")]

        reference_field = helpers.first_text(
            hints.reference_field,
            intent.reference.column if intent.reference else None,
            reference_variable.column if reference_variable else None,
        )
        reference_sheet = helpers.first_text(
            hints.reference_sheet,
            intent.reference.sheet if intent.reference else None,
            reference_variable.sheet if reference_variable else None,
        )
        reference_source_url = helpers.first_text(
            hints.reference_source_url,
            intent.reference.path_or_url if intent.reference else None,
            state.source_url,
        )
        reference_source_id = helpers.first_text(
            hints.reference_source_id,
            intent.reference.source_id if intent.reference else None,
            reference_variable.source_id if reference_variable else None,
            helpers.derive_source_id(reference_source_url),
            state.source_id,
        )
        if not reference_field or not reference_sheet:
            return None, [MissingItem(kind="variable", message="跨表映射需要引用 Sheet 和引用字段。", suggested_action="none")]

        target = helpers.variable_intent_from_existing(target_variable) or VariableIntent(
            **state.common_variable_kwargs,
            variable_kind="single",
            column=state.target_field,
            expected_type="str",
        )
        reference = helpers.variable_intent_from_existing(reference_variable) or VariableIntent(
            source_id=reference_source_id,
            source_type=hints.reference_source_type or state.source_type,
            path_or_url=reference_source_url,
            sheet=reference_sheet,
            variable_kind="single",
            column=reference_field,
            expected_type="str",
        )
        return RuleIntent(
            verdict="ready",
            rule_type=state.rule_type,
            confidence=max(intent.confidence, 0.7),
            reasoning_summary=helpers.append_field_correction_summary(
                intent.reasoning_summary or "已根据结构化线索自动补齐跨表映射规则。",
                state.field_correction_warnings,
            ),
            rule_name=intent.rule_name,
            display_field=state.display_field,
            target=target,
            reference=reference,
        ), []

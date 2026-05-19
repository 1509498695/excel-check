"""Compiler for dual-composite compare rule hints."""

from __future__ import annotations

from uuid import uuid4

from backend.app.ai.compilers.base import WorkflowCompileState, WorkflowCompilerHelpers
from backend.app.ai.schemas import RuleIntent, VariableIntent
from backend.app.ai.workflow_hints import MissingItem


class DualCompositeCompiler:
    rule_types = {"dual_composite_compare"}

    def compile(
        self,
        state: WorkflowCompileState,
        helpers: WorkflowCompilerHelpers,
    ) -> tuple[RuleIntent | None, list[MissingItem]]:
        intent = state.intent
        hints = state.workflow_hints
        target_variable = state.target_variable
        reference_variable = state.reference_variable
        if target_variable is not None and (target_variable.variable_kind or "single") != "composite":
            return None, [MissingItem(kind="variable", message="跨组变量校验的左侧变量必须是组合变量。", suggested_action="none")]
        if reference_variable is not None and (reference_variable.variable_kind or "single") != "composite":
            return None, [MissingItem(kind="variable", message="跨组变量校验的右侧变量必须是组合变量。", suggested_action="none")]

        key_column = helpers.first_text(
            hints.key_column,
            hints.left_key_field,
            hints.right_key_field,
            target_variable.key_column if target_variable else None,
        )
        compare_fields = helpers.unique_texts(hints.compare_fields)
        left_filter_field = helpers.first_text(hints.left_filter_field)
        left_filter_value = helpers.first_text(hints.left_filter_value)
        right_filter_field = helpers.first_text(hints.right_filter_field)
        right_filter_value = helpers.first_text(hints.right_filter_value)
        missing_dual: list[MissingItem] = []
        if not key_column:
            missing_dual.append(MissingItem(kind="variable", message="跨组变量校验需要左右关联 Key 字段。", suggested_action="none"))
        if not compare_fields:
            missing_dual.append(MissingItem(kind="parameter", message="跨组变量校验需要至少一个比较字段。", suggested_action="none"))
        if not (left_filter_field and left_filter_value and right_filter_field and right_filter_value):
            missing_dual.append(MissingItem(kind="parameter", message="同一组合变量拆分左右两组时需要左右筛选条件。", suggested_action="none"))
        if missing_dual:
            return None, missing_dual

        key_column = key_column or "__key__"
        columns = helpers.unique_texts(
            [*hints.composite_columns, key_column, left_filter_field, right_filter_field, *compare_fields]
        )
        target = helpers.variable_intent_from_existing(target_variable) or VariableIntent(
            **state.common_variable_kwargs,
            variable_kind="composite",
            columns=columns,
            key_column=key_column,
            append_index_to_key=True,
            expected_type="json",
        )
        reference = helpers.variable_intent_from_existing(reference_variable) or target
        compare_operator = hints.compare_operator or intent.operator or "eq"
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
            rule_type=state.rule_type,
            confidence=max(intent.confidence, 0.75),
            reasoning_summary=helpers.append_field_correction_summary(
                intent.reasoning_summary or "已根据结构化线索自动生成跨组变量对比规则。",
                state.field_correction_warnings,
            ),
            rule_name=intent.rule_name or f"{state.sheet}-{key_column}-两组配置比对",
            display_field=state.display_field,
            target=target,
            reference=reference,
            key_check_mode=hints.key_check_mode or intent.key_check_mode or "baseline_only",
            left_key_field=hints.left_key_field or key_column,
            right_key_field=hints.right_key_field or key_column,
            comparisons=comparisons,  # type: ignore[arg-type]
            left_filters=[
                helpers.condition(
                    field=left_filter_field or "",
                    operator=hints.left_filter_operator or "eq",
                    expected_value=left_filter_value,
                )
            ],
            right_filters=[
                helpers.condition(
                    field=right_filter_field or "",
                    operator=hints.right_filter_operator or "eq",
                    expected_value=right_filter_value,
                )
            ],
        ), []

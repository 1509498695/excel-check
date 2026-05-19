"""Compiler for composite condition rule hints."""

from __future__ import annotations

from backend.app.ai.compilers.base import WorkflowCompileState, WorkflowCompilerHelpers
from backend.app.ai.schemas import RuleIntent, VariableIntent
from backend.app.ai.workflow_hints import MissingItem


class CompositeConditionCompiler:
    rule_types = {"composite_condition_check"}

    def compile(
        self,
        state: WorkflowCompileState,
        helpers: WorkflowCompilerHelpers,
    ) -> tuple[RuleIntent | None, list[MissingItem]]:
        intent = state.intent
        hints = state.workflow_hints
        target_variable = state.target_variable
        if target_variable is not None and (target_variable.variable_kind or "single") != "composite":
            return None, [MissingItem(kind="variable", message="组合分支校验需要选择组合变量。", suggested_action="none")]

        key_column, composite_columns = helpers.resolve_hint_composite_columns(
            hints,
            variable=target_variable,
            target_field=state.target_field,
            display_field=state.display_field,
            filter_field=state.filter_field,
        )
        if not key_column:
            key_column = helpers.infer_metadata_key_column(
                state.context,
                source_id=state.source_id,
                sheet=state.sheet,
            )
            if key_column and key_column not in composite_columns:
                composite_columns.insert(0, key_column)

        target_field = helpers.canonical_variable_field(target_variable, state.target_field)
        filter_field = helpers.canonical_variable_field(target_variable, state.filter_field)
        filter_hints = helpers.canonicalize_filter_hints(target_variable, state.filter_hints)
        display_field = helpers.canonical_variable_field(target_variable, state.display_field)
        key_column = helpers.canonical_variable_field(target_variable, key_column)
        assertion_field = helpers.canonical_variable_field(target_variable, hints.assertion_field or target_field)
        assertion_expected_field = helpers.canonical_variable_field(target_variable, hints.assertion_expected_field)
        if not key_column or len(composite_columns) < 2:
            return None, [
                MissingItem(
                    kind="variable",
                    message="组合分支校验需要组合变量列和 Key 列，请补充 Key 字段与组合变量列。",
                    suggested_action="none",
                    prefill={
                        "source_id": state.source_id or "",
                        "source_type": state.source_type or "local_excel",
                        "pathOrUrl": state.source_url or "",
                        "sheet": state.sheet or "",
                        "columns": composite_columns,
                        "key_column": key_column or "",
                    },
                )
            ]

        composite_config = helpers.build_hint_composite_config(
            target_field=target_field,
            regex_pattern=state.regex_pattern,
            filter_field=filter_field,
            filter_operator=state.filter_operator,
            filter_value=state.filter_value,
            filters=filter_hints,
            assertion_field=assertion_field,
            assertion_operator=hints.assertion_operator,
            assertion_value=hints.assertion_value,
            assertion_value_source=hints.assertion_value_source,
            assertion_expected_field=assertion_expected_field,
        ) or helpers.canonicalize_composite_config_fields(intent.composite_config, target_variable)
        if composite_config is None:
            return None, [MissingItem(kind="parameter", message="组合分支校验需要可执行的筛选或正则断言，请补充正则表达式或规则细节。", suggested_action="none")]

        target = helpers.variable_intent_from_existing(target_variable) or VariableIntent(
            **state.common_variable_kwargs,
            variable_kind="composite",
            columns=composite_columns,
            key_column=key_column,
            append_index_to_key=True,
            expected_type="json",
        )
        return RuleIntent(
            verdict="ready",
            rule_type=state.rule_type,
            confidence=max(intent.confidence, 0.7),
            reasoning_summary=helpers.append_field_correction_summary(
                intent.reasoning_summary or "已根据结构化线索自动补齐数据源、组合变量和组合分支规则。",
                state.field_correction_warnings,
            ),
            rule_name=intent.rule_name or f"{state.sheet}-{target_field}-格式校验",
            display_field=display_field,
            target=target,
            composite_config=composite_config,
        ), []

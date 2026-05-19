import type { AiRuleWorkflowHints } from '../../../../types/ai'
import type { SmartRuleWorkflowHintsState } from '../../../../utils/aiRuleInputDraft'

export function useSmartRuleTemplates(workflowHints: SmartRuleWorkflowHintsState) {
  function applyTemplateWorkflowHints(hints: AiRuleWorkflowHints): void {
    setWorkflowHint('ruleTypeHint', hints.rule_type_hint)
    setWorkflowHint('targetVariableTag', hints.target_variable_tag)
    setWorkflowHint('referenceVariableTag', hints.reference_variable_tag)
    setWorkflowHint('leftVariableTag', hints.left_variable_tag)
    setWorkflowHint('rightVariableTag', hints.right_variable_tag)
    setWorkflowHint('sourceId', hints.source_id)
    setWorkflowHint('sourceUrl', hints.source_url)
    setWorkflowHint('sheet', hints.sheet)
    setWorkflowHint('targetField', hints.target_field)
    setWorkflowHint('displayField', hints.display_field)
    setWorkflowHint('filterField', hints.filter_field)
    setWorkflowHint('filterOperator', hints.filter_operator)
    setWorkflowHint('filterValue', hints.filter_value)
    setWorkflowHint('assertionField', hints.assertion_field)
    setWorkflowHint('assertionOperator', hints.assertion_operator)
    setWorkflowHint('assertionValue', hints.assertion_value)
    setWorkflowHint('operator', hints.operator)
    setWorkflowHint('expectedValue', hints.expected_value)
    setWorkflowHint('expectedValueMode', hints.expected_value_mode)
    setWorkflowHint('regexPattern', hints.regex_pattern)
    setWorkflowHint('sequenceDirection', hints.sequence_direction)
    setWorkflowHint('sequenceStep', hints.sequence_step)
    setWorkflowHint('sequenceStartMode', hints.sequence_start_mode)
    setWorkflowHint('sequenceStartValue', hints.sequence_start_value)
    setWorkflowHint('keyColumn', hints.key_column)
    setWorkflowHint('compositeColumns', hints.composite_columns)
    setWorkflowHint('leftFilterField', hints.left_filter_field)
    setWorkflowHint('leftFilterOperator', hints.left_filter_operator)
    setWorkflowHint('leftFilterValue', hints.left_filter_value)
    setWorkflowHint('rightFilterField', hints.right_filter_field)
    setWorkflowHint('rightFilterOperator', hints.right_filter_operator)
    setWorkflowHint('rightFilterValue', hints.right_filter_value)
    setWorkflowHint('leftKeyField', hints.left_key_field)
    setWorkflowHint('rightKeyField', hints.right_key_field)
    setWorkflowHint('compareOperator', hints.compare_operator)
    setWorkflowHint('keyCheckMode', hints.key_check_mode)
    setWorkflowHint('compareFields', hints.compare_fields)
  }

  function setWorkflowHint(
    key: keyof SmartRuleWorkflowHintsState,
    value: string | string[] | null | undefined,
  ): void {
    if (Array.isArray(value)) {
      workflowHints[key] = value.join(',')
      return
    }
    workflowHints[key] = value ?? ''
  }

  return {
    applyTemplateWorkflowHints,
  }
}

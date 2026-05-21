import type { CompositeCondition } from '../../types/fixedRules'
import type { VariableTag } from '../../types/workbench'
import {
  buildSequenceSummary,
  getOperatorLabel,
  getRuleSelectionName,
  getVariableColumnSummary,
  summarizeCondition,
} from '../../rules'

export function useRuleSummary() {
  return {
    buildSequenceSummary,
    getOperatorLabel,
    getRuleSelectionName,
    getVariableColumnSummary,
    summarizeCondition: (condition: CompositeCondition, variable: VariableTag | null) =>
      summarizeCondition(condition, variable),
  }
}

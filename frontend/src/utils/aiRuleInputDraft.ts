import type { AiRuleWorkflowHints } from '../types/ai'

export const AI_RULE_INPUT_DEFAULT_GROUP_NAME = 'AI生成规则组'

export interface SmartRuleWorkflowHintsState {
  ruleTypeHint: string
  targetVariableTag: string
  referenceVariableTag: string
  leftVariableTag: string
  rightVariableTag: string
  sourceId: string
  sourceUrl: string
  sheet: string
  targetField: string
  ruleGroupName: string
  filterField: string
  filterOperator: string
  filterValue: string
  assertionField: string
  assertionOperator: string
  assertionValue: string
  operator: string
  expectedValue: string
  expectedValueMode: string
  displayField: string
  regexPattern: string
  sequenceDirection: string
  sequenceStep: string
  sequenceStartMode: string
  sequenceStartValue: string
  keyColumn: string
  compositeColumns: string
  leftFilterField: string
  leftFilterOperator: string
  leftFilterValue: string
  rightFilterField: string
  rightFilterOperator: string
  rightFilterValue: string
  leftKeyField: string
  rightKeyField: string
  compareFields: string
}

export interface AiRuleInputDraftState {
  description: string
  extraHints: string
  selectedVariableTags: string[]
  allowAutoComplete: boolean
  workflowHints: SmartRuleWorkflowHintsState
  templateWorkflowHints: AiRuleWorkflowHints
}

export function createDefaultSmartRuleWorkflowHintsState(): SmartRuleWorkflowHintsState {
  return {
    ruleTypeHint: '',
    targetVariableTag: '',
    referenceVariableTag: '',
    leftVariableTag: '',
    rightVariableTag: '',
    sourceId: '',
    sourceUrl: '',
    sheet: '',
    targetField: '',
    ruleGroupName: AI_RULE_INPUT_DEFAULT_GROUP_NAME,
    filterField: '',
    filterOperator: '',
    filterValue: '',
    assertionField: '',
    assertionOperator: '',
    assertionValue: '',
    operator: '',
    expectedValue: '',
    expectedValueMode: '',
    displayField: '',
    regexPattern: '',
    sequenceDirection: '',
    sequenceStep: '',
    sequenceStartMode: '',
    sequenceStartValue: '',
    keyColumn: '',
    compositeColumns: '',
    leftFilterField: '',
    leftFilterOperator: '',
    leftFilterValue: '',
    rightFilterField: '',
    rightFilterOperator: '',
    rightFilterValue: '',
    leftKeyField: '',
    rightKeyField: '',
    compareFields: '',
  }
}

export function createDefaultAiRuleInputDraftState(): AiRuleInputDraftState {
  return {
    description: '',
    extraHints: '',
    selectedVariableTags: [],
    allowAutoComplete: false,
    workflowHints: createDefaultSmartRuleWorkflowHintsState(),
    templateWorkflowHints: {},
  }
}

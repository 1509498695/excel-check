import type { AiRuleWorkflowHints } from '../types/ai'

export const AI_RULE_INPUT_DEFAULT_GROUP_NAME = 'AI生成规则组'
export const AI_RULE_DESCRIPTION_TEMPLATE = `筛选：
- 字段=值
- 字段唯一

Key值选择：字段名

判定：字段不能为空 / 字段不能重复 / 字段必须重复 / 字段=值 / 字段等于字段X`

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
  assertionValueSource: string
  assertionExpectedField: string
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
  compareOperator: string
  keyCheckMode: string
  compareFields: string
}

export interface GroupedSmartRuleWorkflowHintsState {
  source: {
    sourceId: string
    sourceUrl: string
    sheet: string
  }
  variables: {
    targetVariableTag: string
    referenceVariableTag: string
    leftVariableTag: string
    rightVariableTag: string
  }
  fields: {
    targetField: string
    displayField: string
    compositeColumns: string
  }
  filter: {
    filterField: string
    filterOperator: string
    filterValue: string
    leftFilterField: string
    leftFilterOperator: string
    leftFilterValue: string
    rightFilterField: string
    rightFilterOperator: string
    rightFilterValue: string
  }
  assertion: {
    assertionField: string
    assertionOperator: string
    assertionValueSource: string
    assertionExpectedField: string
    assertionValue: string
  }
  key: {
    keyColumn: string
    leftKeyField: string
    rightKeyField: string
    keyCheckMode: string
  }
  compare: {
    operator: string
    expectedValue: string
    expectedValueMode: string
    compareOperator: string
    compareFields: string
  }
  rule: {
    ruleTypeHint: string
    ruleGroupName: string
    regexPattern: string
    sequenceDirection: string
    sequenceStep: string
    sequenceStartMode: string
    sequenceStartValue: string
  }
}

export interface AiRuleInputDraftState {
  description: string
  extraHints: string
  selectedVariableTags: string[]
  allowAutoComplete: boolean
  workflowHints: SmartRuleWorkflowHintsState
  workflowHintGroups: GroupedSmartRuleWorkflowHintsState
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
    assertionValueSource: '',
    assertionExpectedField: '',
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
    compareOperator: '',
    keyCheckMode: '',
    compareFields: '',
  }
}

export function createDefaultGroupedSmartRuleWorkflowHintsState(): GroupedSmartRuleWorkflowHintsState {
  return groupSmartRuleWorkflowHints(createDefaultSmartRuleWorkflowHintsState())
}

export function groupSmartRuleWorkflowHints(
  hints: SmartRuleWorkflowHintsState,
): GroupedSmartRuleWorkflowHintsState {
  return {
    source: {
      sourceId: hints.sourceId,
      sourceUrl: hints.sourceUrl,
      sheet: hints.sheet,
    },
    variables: {
      targetVariableTag: hints.targetVariableTag,
      referenceVariableTag: hints.referenceVariableTag,
      leftVariableTag: hints.leftVariableTag,
      rightVariableTag: hints.rightVariableTag,
    },
    fields: {
      targetField: hints.targetField,
      displayField: hints.displayField,
      compositeColumns: hints.compositeColumns,
    },
    filter: {
      filterField: hints.filterField,
      filterOperator: hints.filterOperator,
      filterValue: hints.filterValue,
      leftFilterField: hints.leftFilterField,
      leftFilterOperator: hints.leftFilterOperator,
      leftFilterValue: hints.leftFilterValue,
      rightFilterField: hints.rightFilterField,
      rightFilterOperator: hints.rightFilterOperator,
      rightFilterValue: hints.rightFilterValue,
    },
    assertion: {
      assertionField: hints.assertionField,
      assertionOperator: hints.assertionOperator,
      assertionValueSource: hints.assertionValueSource,
      assertionExpectedField: hints.assertionExpectedField,
      assertionValue: hints.assertionValue,
    },
    key: {
      keyColumn: hints.keyColumn,
      leftKeyField: hints.leftKeyField,
      rightKeyField: hints.rightKeyField,
      keyCheckMode: hints.keyCheckMode,
    },
    compare: {
      operator: hints.operator,
      expectedValue: hints.expectedValue,
      expectedValueMode: hints.expectedValueMode,
      compareOperator: hints.compareOperator,
      compareFields: hints.compareFields,
    },
    rule: {
      ruleTypeHint: hints.ruleTypeHint,
      ruleGroupName: hints.ruleGroupName,
      regexPattern: hints.regexPattern,
      sequenceDirection: hints.sequenceDirection,
      sequenceStep: hints.sequenceStep,
      sequenceStartMode: hints.sequenceStartMode,
      sequenceStartValue: hints.sequenceStartValue,
    },
  }
}

export function flattenGroupedSmartRuleWorkflowHints(
  groups: GroupedSmartRuleWorkflowHintsState,
): SmartRuleWorkflowHintsState {
  return {
    ruleTypeHint: groups.rule.ruleTypeHint,
    targetVariableTag: groups.variables.targetVariableTag,
    referenceVariableTag: groups.variables.referenceVariableTag,
    leftVariableTag: groups.variables.leftVariableTag,
    rightVariableTag: groups.variables.rightVariableTag,
    sourceId: groups.source.sourceId,
    sourceUrl: groups.source.sourceUrl,
    sheet: groups.source.sheet,
    targetField: groups.fields.targetField,
    ruleGroupName: groups.rule.ruleGroupName,
    filterField: groups.filter.filterField,
    filterOperator: groups.filter.filterOperator,
    filterValue: groups.filter.filterValue,
    assertionField: groups.assertion.assertionField,
    assertionOperator: groups.assertion.assertionOperator,
    assertionValueSource: groups.assertion.assertionValueSource,
    assertionExpectedField: groups.assertion.assertionExpectedField,
    assertionValue: groups.assertion.assertionValue,
    operator: groups.compare.operator,
    expectedValue: groups.compare.expectedValue,
    expectedValueMode: groups.compare.expectedValueMode,
    displayField: groups.fields.displayField,
    regexPattern: groups.rule.regexPattern,
    sequenceDirection: groups.rule.sequenceDirection,
    sequenceStep: groups.rule.sequenceStep,
    sequenceStartMode: groups.rule.sequenceStartMode,
    sequenceStartValue: groups.rule.sequenceStartValue,
    keyColumn: groups.key.keyColumn,
    compositeColumns: groups.fields.compositeColumns,
    leftFilterField: groups.filter.leftFilterField,
    leftFilterOperator: groups.filter.leftFilterOperator,
    leftFilterValue: groups.filter.leftFilterValue,
    rightFilterField: groups.filter.rightFilterField,
    rightFilterOperator: groups.filter.rightFilterOperator,
    rightFilterValue: groups.filter.rightFilterValue,
    leftKeyField: groups.key.leftKeyField,
    rightKeyField: groups.key.rightKeyField,
    compareOperator: groups.compare.compareOperator,
    keyCheckMode: groups.key.keyCheckMode,
    compareFields: groups.compare.compareFields,
  }
}

export function serializeHintsToWorkflowHints(
  workflowHints: SmartRuleWorkflowHintsState | GroupedSmartRuleWorkflowHintsState,
  options: {
    templateWorkflowHints?: AiRuleWorkflowHints
    dryRunWorkflowHints?: AiRuleWorkflowHints
    selectedVariableTags?: string[]
  } = {},
): AiRuleWorkflowHints {
  const flatHints = isGroupedSmartRuleWorkflowHintsState(workflowHints)
    ? flattenGroupedSmartRuleWorkflowHints(workflowHints)
    : workflowHints
  const payload: AiRuleWorkflowHints = cloneWorkflowHints({
    ...(options.templateWorkflowHints ?? {}),
    ...(options.dryRunWorkflowHints ?? {}),
  })
  const selectedVariableTags = options.selectedVariableTags ?? []
  const putText = (key: keyof AiRuleWorkflowHints, value: string): void => {
    const trimmed = value.trim()
    if (trimmed) {
      ;(payload as Record<string, unknown>)[key] = trimmed
    }
  }
  const putKeyText = (key: keyof AiRuleWorkflowHints, value: string): void => {
    if (!isPlaceholderKeyColumn(value)) {
      putText(key, value)
    }
  }
  const putList = (
    key: keyof AiRuleWorkflowHints,
    value: string,
    options: { dropPlaceholderKey?: boolean } = {},
  ): void => {
    const items = value
      .replaceAll('，', ',')
      .split(',')
      .map((item) => item.trim())
      .filter((item) => item && !(options.dropPlaceholderKey && isPlaceholderKeyColumn(item)))
    if (items.length) {
      ;(payload as Record<string, unknown>)[key] = Array.from(new Set(items))
    }
  }

  putText('rule_type_hint', flatHints.ruleTypeHint)
  putText('target_variable_tag', flatHints.targetVariableTag || selectedVariableTags[0] || '')
  putText('left_variable_tag', flatHints.leftVariableTag || selectedVariableTags[0] || '')
  putText('reference_variable_tag', flatHints.referenceVariableTag || selectedVariableTags[1] || '')
  putText('right_variable_tag', flatHints.rightVariableTag || selectedVariableTags[1] || '')
  putText('source_id', flatHints.sourceId)
  putText('source_url', flatHints.sourceUrl)
  putText('sheet', flatHints.sheet)
  putText('target_field', flatHints.targetField)
  putText('display_field', flatHints.displayField)
  putText('filter_field', flatHints.filterField)
  putText('filter_value', flatHints.filterValue)
  putText('assertion_field', flatHints.assertionField)
  putText('assertion_value', flatHints.assertionValue)
  putText('assertion_expected_field', flatHints.assertionExpectedField)
  putText('operator', flatHints.operator)
  putText('expected_value', flatHints.expectedValue)
  putText('regex_pattern', flatHints.regexPattern)
  putText('sequence_step', flatHints.sequenceStep)
  putText('sequence_start_value', flatHints.sequenceStartValue)
  putKeyText('key_column', flatHints.keyColumn)
  putText('left_filter_field', flatHints.leftFilterField)
  putText('left_filter_value', flatHints.leftFilterValue)
  putText('right_filter_field', flatHints.rightFilterField)
  putText('right_filter_value', flatHints.rightFilterValue)
  putKeyText('left_key_field', flatHints.leftKeyField)
  putKeyText('right_key_field', flatHints.rightKeyField)
  putText('compare_operator', flatHints.compareOperator)
  putText('key_check_mode', flatHints.keyCheckMode)
  putList('composite_columns', flatHints.compositeColumns, { dropPlaceholderKey: true })
  putList('compare_fields', flatHints.compareFields)

  if (flatHints.sourceUrl.trim().match(/^(https?:|svn:)/i)) {
    payload.source_type = 'svn'
  }
  if (flatHints.filterOperator.trim()) {
    payload.filter_operator = flatHints.filterOperator as AiRuleWorkflowHints['filter_operator']
  }
  if (flatHints.assertionOperator.trim()) {
    payload.assertion_operator = flatHints.assertionOperator as AiRuleWorkflowHints['assertion_operator']
  }
  if (flatHints.assertionValueSource.trim()) {
    payload.assertion_value_source =
      flatHints.assertionValueSource as AiRuleWorkflowHints['assertion_value_source']
  }
  if (flatHints.expectedValueMode.trim()) {
    payload.expected_value_mode = flatHints.expectedValueMode as AiRuleWorkflowHints['expected_value_mode']
  }
  if (flatHints.sequenceDirection.trim()) {
    payload.sequence_direction = flatHints.sequenceDirection as AiRuleWorkflowHints['sequence_direction']
  }
  if (flatHints.sequenceStartMode.trim()) {
    payload.sequence_start_mode = flatHints.sequenceStartMode as AiRuleWorkflowHints['sequence_start_mode']
  }
  if (flatHints.leftFilterOperator.trim()) {
    payload.left_filter_operator = flatHints.leftFilterOperator as AiRuleWorkflowHints['left_filter_operator']
  }
  if (flatHints.rightFilterOperator.trim()) {
    payload.right_filter_operator = flatHints.rightFilterOperator as AiRuleWorkflowHints['right_filter_operator']
  }
  if (flatHints.compareOperator.trim()) {
    payload.compare_operator = flatHints.compareOperator as AiRuleWorkflowHints['compare_operator']
  }
  if (flatHints.keyCheckMode.trim()) {
    payload.key_check_mode = flatHints.keyCheckMode as AiRuleWorkflowHints['key_check_mode']
  }
  return payload
}

function isGroupedSmartRuleWorkflowHintsState(
  value: SmartRuleWorkflowHintsState | GroupedSmartRuleWorkflowHintsState,
): value is GroupedSmartRuleWorkflowHintsState {
  return 'source' in value && 'variables' in value && 'rule' in value
}

function isPlaceholderKeyColumn(value?: string): boolean {
  if (!value?.trim()) return false
  if (value.includes('未识别') || value.includes('需要用户确认')) return true
  const compact = value.replace(/[\s:：=为是列字段、，。；;]/g, '').toLowerCase()
  return ['key', '关联key', '业务key', '比对key', '对齐key', '主键', '唯一键', '索引'].includes(compact)
}

function cloneWorkflowHints(hints: AiRuleWorkflowHints): AiRuleWorkflowHints {
  return JSON.parse(JSON.stringify(hints)) as AiRuleWorkflowHints
}

export function createDefaultAiRuleInputDraftState(): AiRuleInputDraftState {
  return {
    description: AI_RULE_DESCRIPTION_TEMPLATE,
    extraHints: '',
    selectedVariableTags: [],
    allowAutoComplete: false,
    workflowHints: createDefaultSmartRuleWorkflowHintsState(),
    workflowHintGroups: createDefaultGroupedSmartRuleWorkflowHintsState(),
    templateWorkflowHints: {},
  }
}

import type {
  CompositeCondition,
  FixedRuleOperator,
  FixedRuleSelection,
} from '../types/fixedRules'
import type { VariableTag } from '../types/workbench'
import { OPERATOR_SYMBOL_MAP, RULE_SELECTION_NAME_MAP } from './constants'
import { getCompositeFieldLabel } from './fieldOptions'

export function getOperatorLabel(value: FixedRuleOperator): string {
  return OPERATOR_SYMBOL_MAP[value]
}

export function getRuleSelectionName(value: FixedRuleSelection): string {
  return RULE_SELECTION_NAME_MAP[value]
}

export function getSequenceDirectionLabel(direction: 'asc' | 'desc' | undefined): string {
  return direction === 'desc' ? '降序' : '升序'
}

export function buildSequenceSummary(
  direction: 'asc' | 'desc' | undefined,
  step: string | undefined,
  startMode: 'auto' | 'manual' | undefined,
  startValue: string | undefined,
): string {
  const normalizedStep = step?.trim() || '1'
  if (startMode === 'manual') {
    return `顺序校验（${getSequenceDirectionLabel(direction)}，步长 ${normalizedStep}，起始值 ${startValue?.trim() || '0'}）`
  }
  return `顺序校验（${getSequenceDirectionLabel(direction)}，步长 ${normalizedStep}，自动起始）`
}

export function getVariableColumnSummary(variable: VariableTag | null | undefined): string {
  if (!variable) {
    return '未绑定变量'
  }
  if ((variable.variable_kind ?? 'single') === 'composite') {
    return `Key=${variable.key_column || 'Key'}；成员列：${
      (variable.columns ?? [])
        .filter((column) => column !== variable.key_column)
        .join(' / ') || '未配置'
    }`
  }
  return variable.column?.trim() || '未配置列'
}

export function summarizeCondition(
  condition: CompositeCondition,
  variable: VariableTag | null,
): string {
  const fieldLabel = getCompositeFieldLabel(condition.field, variable)
  if (condition.operator === 'not_null') {
    return `${fieldLabel} 非空`
  }
  if (condition.operator === 'unique') {
    return `${fieldLabel} 唯一`
  }
  if (condition.operator === 'duplicate_required') {
    return `${fieldLabel} 必须重复`
  }
  if (condition.operator === 'regex') {
    return `${fieldLabel} 正则匹配 ${condition.expected_value ?? ''}`
  }
  if (condition.operator === 'contains') {
    return `${fieldLabel} 包含 ${condition.expected_value ?? ''}`
  }
  if (condition.operator === 'not_contains') {
    return `${fieldLabel} 不包含 ${condition.expected_value ?? ''}`
  }

  const operator = OPERATOR_SYMBOL_MAP[condition.operator as FixedRuleOperator]
  const expected =
    condition.value_source === 'field'
      ? getCompositeFieldLabel(condition.expected_field ?? '', variable)
      : condition.expected_value ?? ''
  return `${fieldLabel} ${operator} ${expected}`
}

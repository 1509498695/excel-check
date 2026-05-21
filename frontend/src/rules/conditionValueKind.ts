import type { CompositeCondition } from '../types/fixedRules'
import { COMPOSITE_COMPARE_OPERATORS } from './constants'

export type ConditionCompareValueKind = 'literal' | 'set' | 'field'

export interface ConditionCompareValueKindOption {
  label: string
  value: ConditionCompareValueKind
}

export function shouldShowConditionCompareValueKind(condition: CompositeCondition): boolean {
  return COMPOSITE_COMPARE_OPERATORS.has(condition.operator)
}

export function getConditionCompareValueKind(
  condition: CompositeCondition,
): ConditionCompareValueKind {
  if (condition.value_source === 'field') {
    return 'field'
  }
  if (
    (condition.operator === 'eq' || condition.operator === 'ne') &&
    condition.expected_value_mode === 'set'
  ) {
    return 'set'
  }
  return 'literal'
}

export function getConditionCompareValueKindOptions(
  condition: CompositeCondition,
): ConditionCompareValueKindOption[] {
  const options: ConditionCompareValueKindOption[] = [
    { label: '固定值', value: 'literal' },
  ]
  if (condition.operator === 'eq' || condition.operator === 'ne') {
    options.push({ label: '规则集', value: 'set' })
  }
  options.push({ label: '字段', value: 'field' })
  return options
}

export function applyConditionCompareValueKind(
  condition: CompositeCondition,
  kind: ConditionCompareValueKind,
): void {
  if (kind === 'field') {
    condition.value_source = 'field'
    condition.expected_value = undefined
    condition.expected_value_mode = undefined
    return
  }

  condition.value_source = 'literal'
  condition.expected_field = undefined
  if (typeof condition.expected_value !== 'string') {
    condition.expected_value = ''
  }
  condition.expected_value_mode =
    kind === 'set' && (condition.operator === 'eq' || condition.operator === 'ne')
      ? 'set'
      : condition.operator === 'eq' || condition.operator === 'ne'
        ? 'single'
        : undefined
}

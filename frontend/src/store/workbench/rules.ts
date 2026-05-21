import type { CompositeCondition, FixedRuleDefinition } from '../../types/fixedRules'
import type { VariableTag } from '../../types/workbench'
import {
  createEntityId,
  isCompositeVariable,
  isValidCompositeCondition,
  normalizeCompositeCondition,
  UNGROUPED_GROUP,
} from '../../utils/ruleOrchestrationModel'

export function createWorkbenchDemoRules(): FixedRuleDefinition[] {
  const gid = UNGROUPED_GROUP.group_id
  return [
    {
      rule_id: createEntityId('wb-rule'),
      group_id: gid,
      rule_name: 'items-ID-非空校验',
      target_variable_tag: '[items-id]',
      rule_type: 'not_null',
    },
    {
      rule_id: createEntityId('wb-rule'),
      group_id: gid,
      rule_name: 'items-ID-唯一校验',
      target_variable_tag: '[items-id]',
      rule_type: 'unique',
    },
    {
      rule_id: createEntityId('wb-rule'),
      group_id: gid,
      rule_name: 'items-ID-大于-0',
      target_variable_tag: '[items-id]',
      rule_type: 'fixed_value_compare',
      operator: 'gt',
      expected_value: '0',
    },
    {
      rule_id: createEntityId('wb-rule'),
      group_id: gid,
      rule_name: 'drops-RefID-大于-0',
      target_variable_tag: '[drops-ref]',
      rule_type: 'fixed_value_compare',
      operator: 'gt',
      expected_value: '0',
    },
  ]
}

export function isValidSequenceStep(value: string | undefined): boolean {
  const normalized = value?.trim() ?? ''
  if (!normalized) {
    return false
  }
  const numeric = Number(normalized)
  return Number.isFinite(numeric) && numeric > 0
}

export function isValidSequenceStartValue(value: string | undefined): boolean {
  const normalized = value?.trim() ?? ''
  if (!normalized) {
    return false
  }
  return Number.isFinite(Number(normalized))
}

export function resolveFieldAgainstAvailable(
  requestedField: string | undefined,
  availableFields: string[],
): string | null {
  const rawField = requestedField ?? ''
  if (availableFields.includes(rawField)) {
    return rawField
  }

  const normalizedField = rawField.trim()
  if (!normalizedField) {
    return null
  }

  const matchedFields = availableFields.filter((field) => field.trim() === normalizedField)
  return matchedFields.length === 1 ? matchedFields[0] : null
}

export function collectCompositeAvailableFields(variable: VariableTag | undefined): string[] {
  const fields = new Set<string>(['__key__'])
  const keyColumn = variable?.key_column
  if (keyColumn?.trim()) {
    fields.add(keyColumn)
  }
  ;(variable?.columns ?? []).forEach((column) => {
    if (column?.trim()) {
      fields.add(column)
    }
  })
  return [...fields]
}

export function isValidDualCompositeFilters(
  filters: CompositeCondition[] | undefined,
  availableFields: string[],
): boolean {
  return (filters ?? []).every((condition) => {
    if (!isValidCompositeCondition(condition, 'filter')) {
      return false
    }
    if (!resolveFieldAgainstAvailable(condition.field, availableFields)) {
      return false
    }
    if (
      condition.value_source === 'field' &&
      !resolveFieldAgainstAvailable(condition.expected_field, availableFields)
    ) {
      return false
    }
    return true
  })
}

export function normalizeDualCompositeFilters(
  filters: CompositeCondition[] | undefined,
  availableFields: string[],
): CompositeCondition[] {
  return (filters ?? []).map((condition) => {
    const normalized = normalizeCompositeCondition(condition)
    return {
      ...normalized,
      field: resolveFieldAgainstAvailable(normalized.field, availableFields) ?? normalized.field,
      expected_field:
        normalized.value_source === 'field'
          ? resolveFieldAgainstAvailable(normalized.expected_field, availableFields) ??
            normalized.expected_field
          : normalized.expected_field,
    }
  })
}

export function isValidDualCompositeRule(
  rule: FixedRuleDefinition,
  variableMap: Map<string, VariableTag>,
): boolean {
  const targetTag = rule.target_variable_tag.trim()
  const referenceTag = rule.reference_variable_tag?.trim() ?? ''
  const targetVariable = variableMap.get(targetTag)
  const referenceVariable = variableMap.get(referenceTag)

  if (!targetTag || !referenceTag) {
    return false
  }
  if (!isCompositeVariable(targetVariable) || !isCompositeVariable(referenceVariable)) {
    return false
  }
  if (!rule.key_check_mode || !['baseline_only', 'bidirectional'].includes(rule.key_check_mode)) {
    return false
  }
  if (!rule.comparisons?.length) {
    return false
  }

  const leftFieldList = collectCompositeAvailableFields(targetVariable)
  const rightFieldList = collectCompositeAvailableFields(referenceVariable)
  if (!resolveFieldAgainstAvailable(rule.left_key_field ?? '__key__', leftFieldList)) {
    return false
  }
  if (!resolveFieldAgainstAvailable(rule.right_key_field ?? '__key__', rightFieldList)) {
    return false
  }
  if (targetTag === referenceTag && (!rule.left_filters?.length || !rule.right_filters?.length)) {
    return false
  }
  if (!isValidDualCompositeFilters(rule.left_filters, leftFieldList)) {
    return false
  }
  if (!isValidDualCompositeFilters(rule.right_filters, rightFieldList)) {
    return false
  }

  return rule.comparisons.every((comparison) => {
    if (!comparison.comparison_id?.trim()) {
      return false
    }
    if (!resolveFieldAgainstAvailable(comparison.left_field, leftFieldList)) {
      return false
    }
    if (!resolveFieldAgainstAvailable(comparison.right_field, rightFieldList)) {
      return false
    }
    return ['eq', 'ne', 'gt', 'lt', 'not_null'].includes(comparison.operator)
  })
}

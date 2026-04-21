/**
 * 规则组编排共用模型：默认组、组合规则归一化与合法性判断。
 * 供固定规则页 Pinia 与工作台编排共用，避免两套逻辑漂移。
 */

import type {
  CompositeBranch,
  CompositeCondition,
  CompositeRuleConfig,
  FixedRuleDefinition,
  FixedRuleGroup,
} from '../types/fixedRules'
import type { VariableTag } from '../types/workbench'

export const UNGROUPED_GROUP: FixedRuleGroup = {
  group_id: 'ungrouped',
  group_name: '未分组',
  builtin: true,
}

export const RULE_ORCHESTRATION_PAGE_SIZE = 20

export function createEntityId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export function ensureDefaultGroup(groups: FixedRuleGroup[]): FixedRuleGroup[] {
  const normalized = groups.filter((group) => group.group_id !== UNGROUPED_GROUP.group_id)
  return [{ ...UNGROUPED_GROUP }, ...normalized]
}

export function normalizeExpectedValue(value: string | undefined): string | undefined {
  const normalized = value?.trim() ?? ''
  return normalized ? normalized : undefined
}

export function isCompareOperator(
  value: string | undefined,
): value is NonNullable<FixedRuleDefinition['operator']> {
  return value === 'eq' || value === 'ne' || value === 'gt' || value === 'lt'
}

export function isSingleVariable(variable: VariableTag | undefined | null): variable is VariableTag {
  return variable != null && (variable.variable_kind ?? 'single') === 'single'
}

export function isCompositeVariable(variable: VariableTag | undefined | null): variable is VariableTag {
  return variable != null && (variable.variable_kind ?? 'single') === 'composite'
}

function createConditionId(): string {
  return createEntityId('condition')
}

function createBranchId(): string {
  return createEntityId('branch')
}

export function normalizeCompositeCondition(condition: CompositeCondition): CompositeCondition {
  const operator = condition.operator
  const normalizedField = condition.field.trim()
  const normalizedConditionId = condition.condition_id.trim() || createConditionId()

  if (isCompareOperator(operator)) {
    const valueSource = condition.value_source === 'field' ? 'field' : 'literal'
    return {
      condition_id: normalizedConditionId,
      field: normalizedField,
      operator,
      value_source: valueSource,
      expected_value:
        valueSource === 'literal' ? normalizeExpectedValue(condition.expected_value) : undefined,
      expected_field: valueSource === 'field' ? condition.expected_field?.trim() : undefined,
    }
  }

  return {
    condition_id: normalizedConditionId,
    field: normalizedField,
    operator,
  }
}

export function normalizeCompositeBranch(branch: CompositeBranch): CompositeBranch {
  return {
    branch_id: branch.branch_id.trim() || createBranchId(),
    filters: branch.filters.map(normalizeCompositeCondition),
    assertions: branch.assertions.map(normalizeCompositeCondition),
  }
}

export function normalizeCompositeConfig(
  config: CompositeRuleConfig | undefined,
): CompositeRuleConfig | undefined {
  if (!config) {
    return undefined
  }

  return {
    global_filters: config.global_filters.map(normalizeCompositeCondition),
    branches: config.branches.map(normalizeCompositeBranch),
  }
}

export function isValidCompositeCondition(
  condition: CompositeCondition,
  section: 'filter' | 'assertion',
): boolean {
  const normalizedField = condition.field.trim()
  const normalizedConditionId = condition.condition_id.trim()
  if (!normalizedConditionId || !normalizedField) {
    return false
  }

  const operator = condition.operator
  if (section === 'filter' && (operator === 'unique' || operator === 'duplicate_required')) {
    return false
  }

  if (operator === 'not_null' || operator === 'unique' || operator === 'duplicate_required') {
    return true
  }

  if (!isCompareOperator(operator)) {
    return false
  }

  if (condition.value_source === 'field') {
    return Boolean(condition.expected_field?.trim())
  }

  return Boolean(normalizeExpectedValue(condition.expected_value))
}

export function isValidCompositeConfig(config: CompositeRuleConfig | undefined): boolean {
  if (!config) {
    return false
  }

  if (!config.global_filters.every((condition) => isValidCompositeCondition(condition, 'filter'))) {
    return false
  }

  if (!config.branches.length) {
    return false
  }

  return config.branches.every(
    (branch) =>
      Boolean(branch.branch_id.trim()) &&
      branch.filters.every((condition) => isValidCompositeCondition(condition, 'filter')) &&
      branch.assertions.length > 0 &&
      branch.assertions.every((condition) => isValidCompositeCondition(condition, 'assertion')),
  )
}

export function pruneRulesByRemovedTags(
  rules: FixedRuleDefinition[],
  removedTags: Set<string>,
): FixedRuleDefinition[] {
  if (!removedTags.size) {
    return rules
  }

  return rules.filter(
    (rule) =>
      !removedTags.has(rule.target_variable_tag) &&
      !removedTags.has(rule.reference_variable_tag?.trim() ?? ''),
  )
}

export function collectVariableTagsBySourceIds(
  variables: VariableTag[],
  sourceIds: Set<string>,
): string[] {
  return variables
    .filter((variable) => sourceIds.has(variable.source_id))
    .map((variable) => variable.tag)
}

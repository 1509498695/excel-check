/**
 * 规则组编排共用模型：默认组、组合规则归一化与合法性判断。
 * 供固定规则页 Pinia 与工作台编排共用，避免两套逻辑漂移。
 */

import type {
  CompositeBranch,
  CompositeCondition,
  CompositeRuleConfig,
  ExpectedValueMode,
  FixedRuleDefinition,
  FixedRuleGroup,
  MultiCompositeMappingConfig,
  MultiCompositeMappingExclusionRange,
  MultiCompositeMappingFilter,
  MultiCompositeMappingNode,
  MultiCompositePipelineConfig,
  MultiCompositePipelineNode,
  PipelineAssertionOperator,
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

export function normalizeExpectedValueMode(value: ExpectedValueMode | undefined): ExpectedValueMode | undefined {
  return value === 'set' ? 'set' : undefined
}

export function isCompareOperator(
  value: string | undefined,
): value is NonNullable<FixedRuleDefinition['operator']> {
  return value === 'eq' || value === 'ne' || value === 'gt' || value === 'lt'
}

export function isCompositeContainsOperator(
  value: string | undefined,
): value is 'contains' | 'not_contains' {
  return value === 'contains' || value === 'not_contains'
}

export function isCompositeRegexOperator(
  value: string | undefined,
): value is 'regex' {
  return value === 'regex'
}

function isPipelineAssertionOperator(
  value: string | undefined,
): value is PipelineAssertionOperator {
  return (
    value === 'eq' ||
    value === 'ne' ||
    value === 'gt' ||
    value === 'lt' ||
    value === 'not_null' ||
    value === 'regex' ||
    value === 'unique' ||
    value === 'duplicate_required'
  )
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

function createNodeId(): string {
  return createEntityId('node')
}

function createRangeId(): string {
  return createEntityId('range')
}

function preserveNonBlankIdentifier(value: string | undefined): string {
  const rawValue = value ?? ''
  return rawValue.trim() ? rawValue : ''
}

export function normalizeCompositeCondition(condition: CompositeCondition): CompositeCondition {
  const operator = condition.operator
  const normalizedField = preserveNonBlankIdentifier(condition.field)
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
      expected_value_mode:
        valueSource === 'literal' && (operator === 'eq' || operator === 'ne')
          ? normalizeExpectedValueMode(condition.expected_value_mode)
          : undefined,
      expected_field:
        valueSource === 'field'
          ? preserveNonBlankIdentifier(condition.expected_field) || undefined
          : undefined,
    }
  }

  if (isCompositeContainsOperator(operator)) {
    return {
      condition_id: normalizedConditionId,
      field: normalizedField,
      operator,
      value_source: 'literal',
      expected_value: normalizeExpectedValue(condition.expected_value),
    }
  }

  if (isCompositeRegexOperator(operator)) {
    return {
      condition_id: normalizedConditionId,
      field: normalizedField,
      operator,
      expected_value: normalizeExpectedValue(condition.expected_value),
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

export function normalizeMultiCompositePipelineNode(
  node: MultiCompositePipelineNode,
): MultiCompositePipelineNode {
  return {
    node_id: node.node_id.trim() || createNodeId(),
    variable_tag: preserveNonBlankIdentifier(node.variable_tag),
    filters: node.filters.map(normalizeCompositeCondition),
    assertions: node.assertions.map(normalizeCompositeCondition),
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

export function normalizeMultiCompositePipelineConfig(
  config: MultiCompositePipelineConfig | undefined,
): MultiCompositePipelineConfig | undefined {
  if (!config) {
    return undefined
  }

  return {
    nodes: config.nodes.map(normalizeMultiCompositePipelineNode),
  }
}

export function normalizeMultiCompositeMappingExclusionRange(
  range: MultiCompositeMappingExclusionRange,
): MultiCompositeMappingExclusionRange {
  return {
    range_id: range.range_id.trim() || createRangeId(),
    start_row: Number(range.start_row),
    end_row: Number(range.end_row),
  }
}

export function normalizeMultiCompositeMappingFilter(
  condition: MultiCompositeMappingFilter,
): MultiCompositeMappingFilter {
  const normalizedCondition = normalizeCompositeCondition(condition)
  return {
    ...normalizedCondition,
    exclusion_ranges: (condition.exclusion_ranges ?? []).map(
      normalizeMultiCompositeMappingExclusionRange,
    ),
  }
}

export function normalizeMultiCompositeMappingNode(
  node: MultiCompositeMappingNode,
): MultiCompositeMappingNode {
  return {
    node_id: node.node_id.trim() || createNodeId(),
    variable_tag: preserveNonBlankIdentifier(node.variable_tag),
    filters: (node.filters ?? []).map(normalizeMultiCompositeMappingFilter),
  }
}

export function normalizeMultiCompositeMappingConfig(
  config: MultiCompositeMappingConfig | undefined,
): MultiCompositeMappingConfig | undefined {
  if (!config) {
    return undefined
  }

  return {
    nodes: config.nodes.map(normalizeMultiCompositeMappingNode),
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

  if (isCompositeContainsOperator(operator)) {
    return Boolean(normalizeExpectedValue(condition.expected_value))
  }

  if (isCompositeRegexOperator(operator)) {
    return section === 'assertion' && Boolean(normalizeExpectedValue(condition.expected_value))
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

function isValidPipelineNode(node: MultiCompositePipelineNode): boolean {
  if (!node.node_id.trim() || !node.variable_tag.trim()) {
    return false
  }

  if (!node.filters.every((condition) => isValidCompositeCondition(condition, 'filter'))) {
    return false
  }

  if (!node.assertions.length) {
    return false
  }

  return node.assertions.every(
    (condition) =>
      isValidCompositeCondition(condition, 'assertion') &&
      isPipelineAssertionOperator(condition.operator),
  )
}

export function isValidMultiCompositePipelineConfig(
  config: MultiCompositePipelineConfig | undefined,
  variableMap?: Map<string, VariableTag>,
): boolean {
  if (!config?.nodes.length) {
    return false
  }

  return config.nodes.every((node) => {
    if (!isValidPipelineNode(node)) {
      return false
    }
    if (!variableMap) {
      return true
    }
    return isCompositeVariable(variableMap.get(node.variable_tag.trim()))
  })
}

function isValidMappingExclusionRange(range: MultiCompositeMappingExclusionRange): boolean {
  const startRow = Number(range.start_row)
  const endRow = Number(range.end_row)
  return (
    Boolean(range.range_id.trim()) &&
    Number.isInteger(startRow) &&
    Number.isInteger(endRow) &&
    startRow > 0 &&
    endRow > 0 &&
    startRow <= endRow
  )
}

function getCompositeAvailableFields(variable: VariableTag): Set<string> {
  const keyColumn = variable.key_column?.trim() ?? ''
  return new Set([
    '__key__',
    ...(variable.columns ?? [])
      .map((column) => column.trim())
      .filter((column) => column && column !== keyColumn),
  ])
}

function isValidMappingFilter(
  condition: MultiCompositeMappingFilter,
  availableFields?: Set<string>,
): boolean {
  if (!isValidCompositeCondition(condition, 'filter')) {
    return false
  }
  if (!condition.exclusion_ranges.every(isValidMappingExclusionRange)) {
    return false
  }
  return availableFields ? availableFields.has(condition.field.trim()) : true
}

function isValidMappingNode(
  node: MultiCompositeMappingNode,
  variableMap?: Map<string, VariableTag>,
): boolean {
  if (!node.node_id.trim() || !node.variable_tag.trim() || !node.filters.length) {
    return false
  }

  if (!variableMap) {
    return node.filters.every((condition) => isValidMappingFilter(condition))
  }

  const variable = variableMap.get(node.variable_tag.trim())
  if (!isCompositeVariable(variable)) {
    return false
  }

  const availableFields = getCompositeAvailableFields(variable)
  for (const condition of node.filters) {
    if (!isValidMappingFilter(condition, availableFields)) {
      return false
    }
  }
  return true
}

export function isValidMultiCompositeMappingConfig(
  config: MultiCompositeMappingConfig | undefined,
  variableMap?: Map<string, VariableTag>,
): boolean {
  if (!config?.nodes.length) {
    return false
  }

  return config.nodes.every((node) => isValidMappingNode(node, variableMap))
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
      !removedTags.has(rule.reference_variable_tag?.trim() ?? '') &&
      !(rule.pipeline_config?.nodes ?? []).some((node) =>
        removedTags.has(node.variable_tag.trim()),
      ) &&
      !(rule.mapping_config?.nodes ?? []).some((node) =>
        removedTags.has(node.variable_tag.trim()),
      ),
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

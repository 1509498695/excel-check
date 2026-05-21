import type {
  CompositeCondition,
  CompositeRuleConfig,
  DualCompositeComparison,
  MultiCompositeMappingConfig,
  MultiCompositeMappingNode,
  MultiCompositePipelineConfig,
  MultiCompositePipelineNode,
} from '../types/fixedRules'
import {
  createDualCompositeComparison,
  createMappingFilter,
  createMappingNode,
  createPipelineNode,
  createRuleBranch,
  createRuleCondition,
  createRuleEntityId,
} from './factory'

function withConditionId<T extends CompositeCondition>(condition: T): T {
  return {
    ...condition,
    condition_id: condition.condition_id || createRuleEntityId('condition'),
  }
}

export function normalizeDialogCompositeConfig(
  config?: CompositeRuleConfig,
): CompositeRuleConfig {
  return {
    global_filters: (config?.global_filters ?? []).map(withConditionId),
    branches: (config?.branches?.length ? config.branches : [createRuleBranch()]).map((branch) => ({
      branch_id: branch.branch_id || createRuleEntityId('branch'),
      filters: (branch.filters ?? []).map(withConditionId),
      assertions: (branch.assertions?.length ? branch.assertions : [createRuleCondition()]).map(
        withConditionId,
      ),
    })),
  }
}

export function normalizeDialogDualCompositeComparisons(
  comparisons?: DualCompositeComparison[],
): DualCompositeComparison[] {
  const nextComparisons = (comparisons?.length ? comparisons : [createDualCompositeComparison()]).map(
    (comparison) => ({
      comparison_id: comparison.comparison_id || createRuleEntityId('comparison'),
      left_field: comparison.left_field?.trim() ?? '',
      operator: comparison.operator ?? 'eq',
      right_field: comparison.right_field?.trim() ?? '',
    }),
  )
  return nextComparisons.length ? nextComparisons : [createDualCompositeComparison()]
}

export function normalizeDialogDualCompositeFilters(
  filters?: CompositeCondition[],
): CompositeCondition[] {
  return (filters ?? []).map(withConditionId)
}

export function normalizeDialogPipelineConfig(
  config: MultiCompositePipelineConfig | undefined,
  getDefaultCompositeVariableTag: (preferred?: string) => string,
  preferredVariableTag = '',
): MultiCompositePipelineConfig {
  const fallbackVariableTag = getDefaultCompositeVariableTag(preferredVariableTag)
  const nextNodes = (config?.nodes?.length ? config.nodes : [createPipelineNode(fallbackVariableTag)]).map(
    (node, index): MultiCompositePipelineNode => ({
      node_id: node.node_id || createRuleEntityId('pipeline-node'),
      variable_tag:
        getDefaultCompositeVariableTag(node.variable_tag || (index === 0 ? fallbackVariableTag : '')),
      display_field: node.display_field?.trim() ?? '',
      filters: (node.filters ?? []).map(withConditionId),
      assertions: (node.assertions?.length ? node.assertions : [createRuleCondition()]).map(
        withConditionId,
      ),
    }),
  )
  return { nodes: nextNodes }
}

export function normalizeDialogMappingConfig(
  config: MultiCompositeMappingConfig | undefined,
  getDefaultCompositeVariableTag: (preferred?: string) => string,
  preferredVariableTag = '',
): MultiCompositeMappingConfig {
  const fallbackVariableTag = getDefaultCompositeVariableTag(preferredVariableTag)
  const nextNodes = (config?.nodes?.length ? config.nodes : [createMappingNode(fallbackVariableTag)]).map(
    (node, index): MultiCompositeMappingNode => ({
      node_id: node.node_id || createRuleEntityId('mapping-node'),
      variable_tag:
        getDefaultCompositeVariableTag(node.variable_tag || (index === 0 ? fallbackVariableTag : '')),
      display_field: node.display_field?.trim() ?? '',
      filters: (node.filters?.length ? node.filters : [createMappingFilter()]).map((condition) => ({
        ...withConditionId(condition),
        exclusion_ranges: (condition.exclusion_ranges ?? []).map((range) => ({
          ...range,
          range_id: range.range_id || createRuleEntityId('mapping-range'),
        })),
      })),
    }),
  )
  return { nodes: nextNodes }
}

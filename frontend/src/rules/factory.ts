import type {
  CompositeBranch,
  CompositeCondition,
  DualCompositeComparison,
  MultiCompositeMappingExclusionRange,
  MultiCompositeMappingFilter,
  MultiCompositeMappingNode,
  MultiCompositePipelineNode,
} from '../types/fixedRules'

export function createRuleEntityId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export function createRuleCondition(): CompositeCondition {
  return {
    condition_id: createRuleEntityId('condition'),
    field: '',
    operator: 'eq',
    value_source: 'literal',
    expected_value: '',
    expected_value_mode: 'single',
    expected_field: '',
  }
}

export function createRuleBranch(): CompositeBranch {
  return {
    branch_id: createRuleEntityId('branch'),
    filters: [],
    assertions: [createRuleCondition()],
  }
}

export function createDualCompositeComparison(): DualCompositeComparison {
  return {
    comparison_id: createRuleEntityId('comparison'),
    left_field: '',
    operator: 'eq',
    right_field: '',
  }
}

export function createPipelineNode(variableTag = ''): MultiCompositePipelineNode {
  return {
    node_id: createRuleEntityId('pipeline-node'),
    variable_tag: variableTag,
    display_field: '',
    filters: [],
    assertions: [createRuleCondition()],
  }
}

export function createMappingExclusionRange(
  startRow = 2,
): MultiCompositeMappingExclusionRange {
  return {
    range_id: createRuleEntityId('mapping-range'),
    start_row: startRow,
    end_row: startRow,
    expected_value: '',
  }
}

export function createMappingFilter(): MultiCompositeMappingFilter {
  return {
    ...createRuleCondition(),
    exclusion_ranges: [],
  }
}

export function createMappingNode(variableTag = ''): MultiCompositeMappingNode {
  return {
    node_id: createRuleEntityId('mapping-node'),
    variable_tag: variableTag,
    display_field: '',
    filters: [],
  }
}

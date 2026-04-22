import type { AbnormalResult, DataSource, ExecutionMeta, VariableTag } from './workbench'

export type FixedRuleOperator = 'eq' | 'ne' | 'gt' | 'lt'
export type CompositeFilterOperator =
  | FixedRuleOperator
  | 'not_null'
  | 'contains'
  | 'not_contains'
export type CompositeAssertionOperator =
  | FixedRuleOperator
  | 'not_null'
  | 'regex'
  | 'unique'
  | 'duplicate_required'
export type CompositeConditionOperator = CompositeFilterOperator | CompositeAssertionOperator
export type CompositeValueSource = 'literal' | 'field'
export type DualCompositeKeyCheckMode = 'baseline_only' | 'bidirectional'
export type FixedRuleType =
  | 'fixed_value_compare'
  | 'regex_check'
  | 'not_null'
  | 'unique'
  | 'sequence_order_check'
  | 'cross_table_mapping'
  | 'composite_condition_check'
  | 'dual_composite_compare'
export type FixedRuleSelection =
  | FixedRuleOperator
  | 'regex_check'
  | 'not_null'
  | 'unique'
  | 'sequence_order_check'
  | 'in'
  | 'composite_condition_check'
  | 'dual_composite_compare'
export type SequenceDirection = 'asc' | 'desc'
export type SequenceStartMode = 'auto' | 'manual'

export interface CompositeCondition {
  condition_id: string
  field: string
  operator: CompositeConditionOperator
  value_source?: CompositeValueSource
  expected_value?: string
  expected_field?: string
}

export interface CompositeBranch {
  branch_id: string
  filters: CompositeCondition[]
  assertions: CompositeCondition[]
}

export interface CompositeRuleConfig {
  global_filters: CompositeCondition[]
  branches: CompositeBranch[]
}

export interface DualCompositeComparison {
  comparison_id: string
  left_field: string
  operator: FixedRuleOperator | 'not_null'
  right_field: string
}

export interface FixedRuleGroup {
  group_id: string
  group_name: string
  builtin: boolean
}

export interface FixedRuleDefinition {
  rule_id: string
  group_id: string
  rule_name: string
  target_variable_tag: string
  rule_type: FixedRuleType
  operator?: FixedRuleOperator
  expected_value?: string
  reference_variable_tag?: string
  sequence_direction?: SequenceDirection
  sequence_step?: string
  sequence_start_mode?: SequenceStartMode
  sequence_start_value?: string
  composite_config?: CompositeRuleConfig
  key_check_mode?: DualCompositeKeyCheckMode
  comparisons?: DualCompositeComparison[]
}

export interface FixedRulesConfig {
  version: number
  configured: boolean
  sources: DataSource[]
  variables: VariableTag[]
  groups: FixedRuleGroup[]
  rules: FixedRuleDefinition[]
}

export interface FixedRulesConfigIssue {
  level: 'warning' | 'error'
  source_id?: string | null
  variable_tag?: string | null
  rule_id?: string | null
  message: string
}

export interface FixedRulesConfigResponse {
  code: number
  msg: string
  data: FixedRulesConfig
  meta?: {
    config_issues?: FixedRulesConfigIssue[]
  }
}

export interface FixedRulesExecuteResponse {
  code: number
  msg: string
  meta: ExecutionMeta
  data: {
    total?: number
    list?: AbnormalResult[]
    page?: number
    size?: number
    abnormal_results: AbnormalResult[]
  }
}

export interface FixedRulesSvnUpdateItem {
  working_copy: string
  status: 'success' | 'error'
  output: string
  used_executable: string
  error?: string
}

export interface FixedRulesSvnUpdateResponse {
  code: number
  msg: string
  data: {
    total_paths: number
    updated_paths: number
    results: FixedRulesSvnUpdateItem[]
  }
}

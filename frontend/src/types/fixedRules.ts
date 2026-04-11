import type { AbnormalResult, DataSource, ExecutionMeta, VariableTag } from './workbench'

export type FixedRuleOperator = 'eq' | 'ne' | 'gt' | 'lt'
export type FixedRuleType = 'fixed_value_compare' | 'not_null' | 'unique'
export type FixedRuleSelection = FixedRuleOperator | 'not_null' | 'unique'

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

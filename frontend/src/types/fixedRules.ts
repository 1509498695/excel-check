import type { AbnormalResult, ExecutionMeta } from './workbench'

export type FixedRuleOperator = 'eq' | 'ne' | 'gt' | 'lt'

export interface FixedRuleBinding {
  file_path: string
  sheet: string
  column: string
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
  binding: FixedRuleBinding
  operator: FixedRuleOperator
  expected_value: string
}

export interface FixedRulesConfig {
  version: number
  configured: boolean
  groups: FixedRuleGroup[]
  rules: FixedRuleDefinition[]
}

export interface FixedRulesConfigResponse {
  code: number
  msg: string
  data: FixedRulesConfig
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

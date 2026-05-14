import type { ApiResponse, ApiStatusResponse } from './api'
import type { FixedRuleDefinition, FixedRuleType } from './fixedRules'
import type { DataSource, VariableTag } from './workbench'

export type AiProviderPreset =
  | 'openai'
  | 'anthropic'
  | 'gemini'
  | 'deepseek'
  | 'qwen'
  | 'kimi'
  | 'zhipu'
  | 'openrouter'
  | 'custom_openai'

export type AiProviderProtocol = 'openai_compatible' | 'anthropic' | 'gemini'
export type AiDraftVerdict = 'ready' | 'needs_input' | 'rejected'
export type AiRuleInputMode = 'free_text' | 'structured' | 'template'
export type AiMissingAction =
  | 'open_source_dialog'
  | 'open_single_variable_dialog'
  | 'open_composite_variable_dialog'
  | 'edit_description'
  | 'none'

export interface AiProviderConfigInput {
  provider_preset: AiProviderPreset
  base_url?: string | null
  model?: string | null
  api_key?: string | null
  extra_headers?: Record<string, string>
}

export interface AiProviderConfig {
  provider_preset: AiProviderPreset
  protocol: AiProviderProtocol
  base_url: string
  model: string
  api_key_masked: string
  has_extra_headers: boolean
  updated_at?: string | null
}

export interface AiProviderTestResult {
  ok: boolean
  latency_ms?: number | null
  category?: string | null
  message?: string | null
}

export interface AiRuleDraftRequest {
  description: string
  extra_hints?: string | null
  workflow_hints?: AiRuleWorkflowHints | null
  input_mode?: AiRuleInputMode
  allow_auto_complete?: boolean
  selected_variable_tags?: string[]
}

export type RulePromptOptimizeStatus = 'optimized' | 'needs_input' | 'failed'

export interface RulePromptOptimizeRequest {
  selected_variable_tags: string[]
  raw_description: string
  allow_auto_complete?: boolean
  context?: Record<string, unknown>
}

export interface RulePromptOptimizeClues {
  rule_type_hint?: FixedRuleType | null
  involved_variables: string[]
  target_field?: string | null
  key_field?: string | null
  filters: Array<Record<string, unknown>>
  compare_fields: string[]
  compare_operator?: 'eq' | 'ne' | 'gt' | 'lt' | null
}

export interface RulePromptOptimizeResult {
  status: RulePromptOptimizeStatus
  raw_description: string
  optimized_description: string
  detected_clues: RulePromptOptimizeClues
  missing: string[]
  warnings: string[]
  confidence?: number | null
  fallback: boolean
}

export interface AiRuleWorkflowHints {
  rule_type_hint?: FixedRuleType | null
  target_variable_tag?: string | null
  reference_variable_tag?: string | null
  left_variable_tag?: string | null
  right_variable_tag?: string | null
  source_id?: string | null
  source_type?: 'local_excel' | 'svn' | null
  source_url?: string | null
  sheet?: string | null
  target_field?: string | null
  display_field?: string | null
  filter_field?: string | null
  filter_operator?: 'eq' | 'ne' | 'gt' | 'lt' | 'contains' | 'not_contains' | null
  filter_value?: string | null
  assertion_field?: string | null
  assertion_operator?:
    | 'eq'
    | 'ne'
    | 'gt'
    | 'lt'
    | 'not_null'
    | 'regex'
    | 'unique'
    | 'duplicate_required'
    | null
  assertion_value?: string | null
  operator?: 'eq' | 'ne' | 'gt' | 'lt' | null
  expected_value?: string | null
  expected_value_mode?: 'single' | 'set' | null
  regex_pattern?: string | null
  sequence_direction?: 'asc' | 'desc' | null
  sequence_step?: string | null
  sequence_start_mode?: 'auto' | 'manual' | null
  sequence_start_value?: string | null
  key_column?: string | null
  composite_columns?: string[]
  reference_source_id?: string | null
  reference_source_type?: 'local_excel' | 'svn' | null
  reference_source_url?: string | null
  reference_sheet?: string | null
  reference_field?: string | null
  reference_key_column?: string | null
  reference_composite_columns?: string[]
  left_filter_field?: string | null
  left_filter_operator?: 'eq' | 'ne' | 'gt' | 'lt' | 'contains' | 'not_contains' | null
  left_filter_value?: string | null
  right_filter_field?: string | null
  right_filter_operator?: 'eq' | 'ne' | 'gt' | 'lt' | 'contains' | 'not_contains' | null
  right_filter_value?: string | null
  left_key_field?: string | null
  right_key_field?: string | null
  compare_fields?: string[]
  pipeline_nodes?: Record<string, unknown>[]
  mapping_nodes?: Record<string, unknown>[]
}

export interface AiMissingItem {
  kind: 'source' | 'variable' | 'rule' | 'parameter' | 'ability'
  message: string
  suggested_action: AiMissingAction
  prefill: Record<string, unknown>
}

export interface AiRuleDraftPayload {
  sources_to_add: DataSource[]
  variables_to_add: VariableTag[]
  rules_to_add: FixedRuleDefinition[]
  reuse_variable_tags: string[]
}

export interface AiRuleDraft {
  draft_id?: number | null
  description?: string | null
  verdict: AiDraftVerdict
  rule_type?: FixedRuleType | null
  confidence: number
  reasoning_summary: string
  draft: AiRuleDraftPayload
  missing: AiMissingItem[]
  rejection_reason?: string | null
  extension_suggestions: string[]
  applied: boolean
  created_at?: string | null
}

export type AiProviderConfigResponse = ApiResponse<AiProviderConfig | null>
export type AiProviderSaveResponse = ApiResponse<AiProviderConfig>
export type AiProviderTestResponse = ApiResponse<AiProviderTestResult>
export type AiRuleDraftResponse = ApiResponse<AiRuleDraft>
export type AiRuleDraftListResponse = ApiResponse<{ items: AiRuleDraft[]; total: number }>
export type RulePromptOptimizeResponse = ApiResponse<RulePromptOptimizeResult>
export type AiDraftClearResponse = ApiResponse<{ deleted: number }>
export type AiStatusResponse = ApiStatusResponse

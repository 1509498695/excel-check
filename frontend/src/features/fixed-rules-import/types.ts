import type { ApiResponse } from '../../types/api'
import type { FixedRuleDefinition, FixedRuleGroup, FixedRulesConfig } from '../../types/fixedRules'
import type { DataSource, VariableTag } from '../../types/workbench'

export type ImportScopeMode = 'all' | 'groups' | 'rules'
export type SourceMappingAction = 'new' | 'reuse' | 'replace' | 'skip'
export type ImportItemStatus = 'new' | 'reuse' | 'renamed' | 'skipped' | 'error'
export type DuplicateRuleAction = 'rename' | 'skip'

export interface ImportScope {
  mode: ImportScopeMode
  group_ids?: string[]
  rule_ids?: string[]
}

export interface SourceMapping {
  personal_source_id: string
  action: SourceMappingAction
  project_source_id?: string | null
  next_source?: DataSource | null
  confirmed?: boolean
}

export interface ImportConflictResolutions {
  variable_tags?: Record<string, string>
  rule_names?: Record<string, string>
  group_names?: Record<string, string>
}

export interface WorkbenchImportPreviewRequest {
  scope: ImportScope
  selected_rule_ids?: string[] | null
  selected_group_ids?: string[] | null
  user_id?: number | null
  project_id?: number | null
  source_mappings: SourceMapping[]
  conflict_resolutions?: ImportConflictResolutions
  duplicate_rule_actions?: Record<string, DuplicateRuleAction>
}

export interface ImportConflict {
  kind: string
  level: 'info' | 'warning' | 'error'
  item_id: string
  message: string
  candidates: string[]
}

export interface ImportSummary {
  sources_new: number
  sources_reused: number
  sources_skipped: number
  variables_new: number
  variables_reused: number
  variables_skipped: number
  groups_new: number
  groups_reused: number
  rules_new: number
  rules_renamed: number
  rules_skipped: number
  blocking_errors: number
}

export interface SourceMappingDraft {
  personal_source: DataSource
  recommended_action: SourceMappingAction
  project_source_id?: string | null
  next_source?: DataSource | null
  reason: string
  candidates: DataSource[]
  requires_confirmation?: boolean
}

export interface ImportItemResult {
  item_id: string
  status: ImportItemStatus
  message: string
  next_id?: string | null
  details?: Record<string, unknown>
}

export interface VariablePreviewResult {
  tag: string
  status: 'ok' | 'warning' | 'error'
  message: string
  preview?: Record<string, unknown> | null
}

export interface WorkbenchImportDraft {
  personal_config: FixedRulesConfig
  project_config: FixedRulesConfig
  importable_groups: FixedRuleGroup[]
  importable_rules: FixedRuleDefinition[]
  importable_sources: DataSource[]
  importable_variables: VariableTag[]
  source_mappings: SourceMappingDraft[]
  conflicts: ImportConflict[]
  summary: ImportSummary
}

export interface WorkbenchImportPreview {
  summary: ImportSummary
  source_results: ImportItemResult[]
  variable_results: ImportItemResult[]
  group_results: ImportItemResult[]
  rule_results: ImportItemResult[]
  variable_previews: VariablePreviewResult[]
  conflicts: ImportConflict[]
  blocking_errors: string[]
  next_config_preview: FixedRulesConfig
}

export type WorkbenchImportDraftResponse = ApiResponse<WorkbenchImportDraft>
export type WorkbenchImportPreviewResponse = ApiResponse<WorkbenchImportPreview>
export type WorkbenchImportCommitResponse = ApiResponse<
  FixedRulesConfig,
  {
    import_summary: ImportSummary
    source_results: ImportItemResult[]
    variable_results: ImportItemResult[]
    group_results: ImportItemResult[]
    rule_results: ImportItemResult[]
  }
>

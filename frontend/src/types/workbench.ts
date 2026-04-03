export type SourceType = 'local_excel' | 'local_csv' | 'feishu' | 'svn'

export type ExpectedType = 'int' | 'str' | 'json'

export type RuleMode = 'static' | 'dynamic'

export interface DataSource {
  id: string
  type: SourceType
  path?: string
  url?: string
  pathOrUrl?: string
  token?: string
}

export interface VariableTag {
  tag: string
  source_id: string
  sheet: string
  column: string
  expected_type?: ExpectedType | null
}

export interface ValidationRuleDraftState {
  paramsText?: string
}

export interface ValidationRule {
  rule_id?: string
  rule_type: string
  params: Record<string, unknown>
  mode?: RuleMode
  draftState?: ValidationRuleDraftState
}

export interface TaskTree {
  sources: DataSource[]
  variables: VariableTag[]
  rules: ValidationRule[]
}

export interface ExecutionMeta {
  execution_time_ms: number
  total_rows_scanned: number
  failed_sources: string[]
}

export interface AbnormalResult {
  level: 'error' | 'warning' | 'success' | string
  rule_name: string
  location: string
  row_index: number
  raw_value: unknown
  message: string
}

export interface ExecuteResponse {
  code: number
  msg: string
  meta: ExecutionMeta
  data: {
    abnormal_results: AbnormalResult[]
  }
}

export interface SourceCapabilitiesResponse {
  code: number
  msg: string
  data: {
    source_types: SourceType[]
    implemented: boolean
  }
}

export interface LocalPickResponse {
  code: number
  msg: string
  data: {
    selected_path: string
    source_type: Extract<SourceType, 'local_excel' | 'local_csv'>
  }
}

export interface SourceSheetMetadata {
  name: string
  columns: string[]
}

export interface SourceMetadata {
  source_id: string
  source_type: SourceType
  sheets: SourceSheetMetadata[]
}

export interface SourceMetadataResponse {
  code: number
  msg: string
  data: SourceMetadata
}

export interface ColumnPreviewRow {
  row_index: number
  value: unknown
}

export interface VariablePreviewData {
  source_id: string
  source_type: SourceType
  source_path?: string
  sheet: string
  column: string
  preview_rows: ColumnPreviewRow[]
  total_rows: number
  loaded_rows?: number
  loaded_all_rows?: boolean
  preview_limit: number
}

export interface ColumnPreviewRequest {
  source: DataSource
  sheet: string
  column: string
  limit?: number
}

export interface ColumnPreviewResponse {
  code: number
  msg: string
  data: VariablePreviewData
}

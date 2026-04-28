export interface ApiResponse<TData = unknown, TMeta = unknown> {
  code: number
  msg: string
  data: TData
  meta?: TMeta
}

export interface ApiStatusResponse {
  code: number
  msg: string
}

export interface ExecutionMeta {
  execution_time_ms: number
  total_rows_scanned: number
  failed_sources: string[]
  result_id?: number
}

export interface AbnormalResult {
  level: 'error' | 'warning' | 'success' | string
  rule_name: string
  location: string
  row_index: number
  raw_value: unknown
  message: string
}

export interface ExecutionResultData<TItem = AbnormalResult> {
  total?: number
  list?: TItem[]
  page?: number
  size?: number
  abnormal_results: TItem[]
}

export interface ExecutionResponse<TItem = AbnormalResult> extends ApiResponse<
  ExecutionResultData<TItem>,
  ExecutionMeta
> {
  meta: ExecutionMeta
}

export interface ApiFileResponse {
  blob: Blob
  filename: string
}

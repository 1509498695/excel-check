import { apiFetch } from '../../utils/apiFetch'
import type {
  WorkbenchImportCommitResponse,
  WorkbenchImportDraftResponse,
  WorkbenchImportPreviewRequest,
  WorkbenchImportPreviewResponse,
} from './types'

export interface WorkbenchImportDraftParams {
  selected_rule_ids?: string[]
  selected_group_ids?: string[]
}

function buildDraftQuery(params?: WorkbenchImportDraftParams): string {
  const searchParams = new URLSearchParams()
  params?.selected_rule_ids?.forEach((ruleId) => {
    searchParams.append('selected_rule_ids', ruleId)
  })
  params?.selected_group_ids?.forEach((groupId) => {
    searchParams.append('selected_group_ids', groupId)
  })
  const query = searchParams.toString()
  return query ? `?${query}` : ''
}

export function fetchWorkbenchImportDraft(
  params?: WorkbenchImportDraftParams,
): Promise<WorkbenchImportDraftResponse> {
  return apiFetch<WorkbenchImportDraftResponse>(
    `/api/v1/fixed-rules/import/workbench/draft${buildDraftQuery(params)}`,
  )
}

export function previewWorkbenchImport(
  payload: WorkbenchImportPreviewRequest,
): Promise<WorkbenchImportPreviewResponse> {
  return apiFetch<WorkbenchImportPreviewResponse>('/api/v1/fixed-rules/import/workbench/preview', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function commitWorkbenchImport(
  payload: WorkbenchImportPreviewRequest,
): Promise<WorkbenchImportCommitResponse> {
  return apiFetch<WorkbenchImportCommitResponse>('/api/v1/fixed-rules/import/workbench/commit', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

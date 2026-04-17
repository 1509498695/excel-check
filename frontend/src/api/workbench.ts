import type {
  ColumnPreviewRequest,
  ColumnPreviewResponse,
  CompositePreviewRequest,
  CompositePreviewResponse,
  DataSource,
  ExecuteResponse,
  LocalPickResponse,
  SourceCapabilitiesResponse,
  SourceMetadataResponse,
  TaskTree,
} from '../types/workbench'
import { apiFetch } from '../utils/apiFetch'

export async function fetchSourceCapabilities(): Promise<SourceCapabilitiesResponse> {
  return apiFetch<SourceCapabilitiesResponse>('/api/v1/sources/capabilities')
}

export async function pickLocalSourcePath(
  sourceType: 'local_excel' | 'local_csv',
): Promise<LocalPickResponse> {
  return apiFetch<LocalPickResponse>('/api/v1/sources/local-pick', {
    method: 'POST',
    body: JSON.stringify({ source_type: sourceType }),
  })
}

export async function fetchSourceMetadata(source: DataSource): Promise<SourceMetadataResponse> {
  return apiFetch<SourceMetadataResponse>('/api/v1/sources/metadata', {
    method: 'POST',
    body: JSON.stringify(source),
  })
}

export async function fetchColumnPreview(
  payload: ColumnPreviewRequest,
): Promise<ColumnPreviewResponse> {
  return apiFetch<ColumnPreviewResponse>('/api/v1/sources/column-preview', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function fetchCompositePreview(
  payload: CompositePreviewRequest,
): Promise<CompositePreviewResponse> {
  return apiFetch<CompositePreviewResponse>('/api/v1/sources/composite-preview', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function executeTaskTree(taskTree: TaskTree): Promise<ExecuteResponse> {
  return apiFetch<ExecuteResponse>('/api/v1/engine/execute', {
    method: 'POST',
    body: JSON.stringify(taskTree),
  })
}

export async function fetchWorkbenchConfig(): Promise<{ code: number; msg: string; data: Record<string, unknown> }> {
  return apiFetch('/api/v1/workbench/config')
}

export async function saveWorkbenchConfig(
  config: Record<string, unknown>,
): Promise<{ code: number; msg: string }> {
  return apiFetch('/api/v1/workbench/config', {
    method: 'PUT',
    body: JSON.stringify(config),
  })
}

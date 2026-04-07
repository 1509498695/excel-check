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

async function parseApiError(response: Response): Promise<never> {
  let message = '请求失败，请稍后重试。'

  try {
    const payload = (await response.json()) as { detail?: string }
    message = payload.detail ?? message
  } catch {
    message = `${response.status} ${response.statusText}`
  }

  throw new Error(message)
}

export async function fetchSourceCapabilities(): Promise<SourceCapabilitiesResponse> {
  const response = await fetch('/api/v1/sources/capabilities')

  if (!response.ok) {
    await parseApiError(response)
  }

  return (await response.json()) as SourceCapabilitiesResponse
}

export async function pickLocalSourcePath(
  sourceType: 'local_excel' | 'local_csv',
): Promise<LocalPickResponse> {
  const response = await fetch('/api/v1/sources/local-pick', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      source_type: sourceType,
    }),
  })

  if (!response.ok) {
    await parseApiError(response)
  }

  return (await response.json()) as LocalPickResponse
}

export async function fetchSourceMetadata(source: DataSource): Promise<SourceMetadataResponse> {
  const response = await fetch('/api/v1/sources/metadata', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(source),
  })

  if (!response.ok) {
    await parseApiError(response)
  }

  return (await response.json()) as SourceMetadataResponse
}

export async function fetchColumnPreview(
  payload: ColumnPreviewRequest,
): Promise<ColumnPreviewResponse> {
  const response = await fetch('/api/v1/sources/column-preview', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    await parseApiError(response)
  }

  return (await response.json()) as ColumnPreviewResponse
}

export async function fetchCompositePreview(
  payload: CompositePreviewRequest,
): Promise<CompositePreviewResponse> {
  const response = await fetch('/api/v1/sources/composite-preview', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    await parseApiError(response)
  }

  return (await response.json()) as CompositePreviewResponse
}

export async function executeTaskTree(taskTree: TaskTree): Promise<ExecuteResponse> {
  const response = await fetch('/api/v1/engine/execute', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(taskTree),
  })

  if (!response.ok) {
    await parseApiError(response)
  }

  return (await response.json()) as ExecuteResponse
}

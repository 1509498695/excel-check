import type {
  FixedRulesConfig,
  FixedRulesConfigResponse,
  FixedRulesExecuteResponse,
  FixedRulesSvnUpdateResponse,
} from '../types/fixedRules'

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

export async function fetchFixedRulesConfig(): Promise<FixedRulesConfigResponse> {
  const response = await fetch('/api/v1/fixed-rules/config')

  if (!response.ok) {
    await parseApiError(response)
  }

  return (await response.json()) as FixedRulesConfigResponse
}

export async function saveFixedRulesConfig(
  config: FixedRulesConfig,
): Promise<FixedRulesConfigResponse> {
  const response = await fetch('/api/v1/fixed-rules/config', {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(config),
  })

  if (!response.ok) {
    await parseApiError(response)
  }

  return (await response.json()) as FixedRulesConfigResponse
}

export async function executeFixedRules(): Promise<FixedRulesExecuteResponse> {
  const response = await fetch('/api/v1/fixed-rules/execute', {
    method: 'POST',
  })

  if (!response.ok) {
    await parseApiError(response)
  }

  return (await response.json()) as FixedRulesExecuteResponse
}

export async function triggerFixedRulesSvnUpdate(): Promise<FixedRulesSvnUpdateResponse> {
  const response = await fetch('/api/v1/fixed-rules/svn-update', {
    method: 'POST',
  })

  if (!response.ok) {
    await parseApiError(response)
  }

  return (await response.json()) as FixedRulesSvnUpdateResponse
}

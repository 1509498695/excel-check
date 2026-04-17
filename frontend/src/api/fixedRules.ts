import type {
  FixedRulesConfig,
  FixedRulesConfigResponse,
  FixedRulesExecuteResponse,
  FixedRulesSvnUpdateResponse,
} from '../types/fixedRules'
import { apiFetch } from '../utils/apiFetch'

export async function fetchFixedRulesConfig(): Promise<FixedRulesConfigResponse> {
  return apiFetch<FixedRulesConfigResponse>('/api/v1/fixed-rules/config')
}

export async function saveFixedRulesConfig(
  config: FixedRulesConfig,
): Promise<FixedRulesConfigResponse> {
  return apiFetch<FixedRulesConfigResponse>('/api/v1/fixed-rules/config', {
    method: 'PUT',
    body: JSON.stringify(config),
  })
}

export async function executeFixedRules(): Promise<FixedRulesExecuteResponse> {
  return apiFetch<FixedRulesExecuteResponse>('/api/v1/fixed-rules/execute', {
    method: 'POST',
  })
}

export async function triggerFixedRulesSvnUpdate(): Promise<FixedRulesSvnUpdateResponse> {
  return apiFetch<FixedRulesSvnUpdateResponse>('/api/v1/fixed-rules/svn-update', {
    method: 'POST',
  })
}

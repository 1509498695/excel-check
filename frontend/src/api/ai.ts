import type {
  AiDraftClearResponse,
  AiProviderConfigInput,
  AiProviderConfigResponse,
  AiProviderSaveResponse,
  AiProviderTestResponse,
  AiRuleDraftListResponse,
  AiRuleDraftRequest,
  AiRuleDraftResponse,
  AiStatusResponse,
  RulePromptOptimizeRequest,
  RulePromptOptimizeResponse,
} from '../types/ai'
import { apiFetch } from '../utils/apiFetch'

export async function getAiProvider(): Promise<AiProviderConfigResponse> {
  return apiFetch<AiProviderConfigResponse>('/api/v1/ai/providers/me')
}

export async function saveAiProvider(
  payload: AiProviderConfigInput,
): Promise<AiProviderSaveResponse> {
  return apiFetch<AiProviderSaveResponse>('/api/v1/ai/providers/me', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function deleteAiProvider(): Promise<AiStatusResponse> {
  return apiFetch<AiStatusResponse>('/api/v1/ai/providers/me', {
    method: 'DELETE',
  })
}

export async function testAiProvider(
  payload: AiProviderConfigInput,
): Promise<AiProviderTestResponse> {
  return apiFetch<AiProviderTestResponse>('/api/v1/ai/providers/test', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function generateRuleDraft(
  payload: AiRuleDraftRequest,
): Promise<AiRuleDraftResponse> {
  return apiFetch<AiRuleDraftResponse>('/api/v1/ai/agents/rule-draft', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function optimizeRulePrompt(
  payload: RulePromptOptimizeRequest,
): Promise<RulePromptOptimizeResponse> {
  return apiFetch<RulePromptOptimizeResponse>('/api/v1/ai/agents/rule-prompt-optimize', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function dryRunRulePromptOptimize(
  payload: RulePromptOptimizeRequest,
): Promise<RulePromptOptimizeResponse> {
  return apiFetch<RulePromptOptimizeResponse>('/api/v1/ai/agents/rule-prompt-optimize?dry_run=true', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function listAiDrafts(limit = 20): Promise<AiRuleDraftListResponse> {
  return apiFetch<AiRuleDraftListResponse>(`/api/v1/ai/drafts?limit=${limit}`)
}

export async function deleteAiDraft(draftId: number): Promise<AiStatusResponse> {
  return apiFetch<AiStatusResponse>(`/api/v1/ai/drafts/${draftId}`, {
    method: 'DELETE',
  })
}

export async function clearAiDrafts(): Promise<AiDraftClearResponse> {
  return apiFetch<AiDraftClearResponse>('/api/v1/ai/drafts', {
    method: 'DELETE',
  })
}

export async function markAiDraftApplied(draftId: number): Promise<AiStatusResponse> {
  return apiFetch<AiStatusResponse>(`/api/v1/ai/drafts/${draftId}/apply`, {
    method: 'POST',
  })
}

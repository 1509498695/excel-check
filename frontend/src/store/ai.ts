import { defineStore } from 'pinia'

import {
  clearAiDrafts,
  deleteAiDraft,
  deleteAiProvider,
  generateRuleDraft,
  getAiProvider,
  listAiDrafts,
  markAiDraftApplied,
  optimizeRulePrompt,
  saveAiProvider,
  testAiProvider,
} from '../api/ai'
import type {
  AiProviderConfig,
  AiProviderConfigInput,
  AiProviderTestResult,
  AiRuleDraft,
  AiRuleDraftRequest,
  RulePromptOptimizeRequest,
  RulePromptOptimizeResult,
} from '../types/ai'

interface AiState {
  provider: AiProviderConfig | null
  drafts: AiRuleDraft[]
  currentDraft: AiRuleDraft | null
  isProviderLoading: boolean
  isProviderSaving: boolean
  isProviderTesting: boolean
  isDraftGenerating: boolean
  isPromptOptimizing: boolean
  isDraftHistoryLoading: boolean
  error: string
  promptOptimizeResult: RulePromptOptimizeResult | null
}

export const useAiStore = defineStore('ai', {
  state: (): AiState => ({
    provider: null,
    drafts: [],
    currentDraft: null,
    isProviderLoading: false,
    isProviderSaving: false,
    isProviderTesting: false,
    isDraftGenerating: false,
    isPromptOptimizing: false,
    isDraftHistoryLoading: false,
    error: '',
    promptOptimizeResult: null,
  }),

  getters: {
    isConfigured(state): boolean {
      return Boolean(state.provider?.api_key_masked)
    },
  },

  actions: {
    clearError(): void {
      this.error = ''
    },

    async loadProvider(): Promise<void> {
      this.isProviderLoading = true
      this.error = ''
      try {
        const response = await getAiProvider()
        this.provider = response.data
      } catch (error) {
        this.error = error instanceof Error ? error.message : '读取 AI 配置失败。'
      } finally {
        this.isProviderLoading = false
      }
    },

    async saveProvider(payload: AiProviderConfigInput): Promise<void> {
      this.isProviderSaving = true
      this.error = ''
      try {
        const response = await saveAiProvider(payload)
        this.provider = response.data
      } catch (error) {
        this.error = error instanceof Error ? error.message : '保存 AI 配置失败。'
        throw error
      } finally {
        this.isProviderSaving = false
      }
    },

    async deleteProvider(): Promise<void> {
      this.isProviderSaving = true
      this.error = ''
      try {
        await deleteAiProvider()
        this.provider = null
      } catch (error) {
        this.error = error instanceof Error ? error.message : '删除 AI 配置失败。'
        throw error
      } finally {
        this.isProviderSaving = false
      }
    },

    async testProvider(payload: AiProviderConfigInput): Promise<AiProviderTestResult> {
      this.isProviderTesting = true
      this.error = ''
      try {
        const response = await testAiProvider(payload)
        return response.data
      } catch (error) {
        this.error = error instanceof Error ? error.message : '测试 AI 连接失败。'
        throw error
      } finally {
        this.isProviderTesting = false
      }
    },

    async generateDraft(
      description: string,
      extraHints?: string,
      workflowHints?: AiRuleDraftRequest['workflow_hints'],
      options?: {
        inputMode?: AiRuleDraftRequest['input_mode']
        allowAutoComplete?: boolean
        selectedVariableTags?: string[]
      },
    ): Promise<AiRuleDraft> {
      this.isDraftGenerating = true
      this.error = ''
      try {
        const response = await generateRuleDraft({
          description,
          extra_hints: extraHints?.trim() || null,
          workflow_hints: workflowHints ?? null,
          input_mode: options?.inputMode ?? 'free_text',
          allow_auto_complete: options?.allowAutoComplete ?? true,
          selected_variable_tags: options?.selectedVariableTags ?? [],
        })
        this.currentDraft = response.data
        await this.loadDrafts()
        return response.data
      } catch (error) {
        this.error = error instanceof Error ? error.message : '生成 AI 规则草稿失败。'
        throw error
      } finally {
        this.isDraftGenerating = false
      }
    },

    async optimizePrompt(payload: RulePromptOptimizeRequest): Promise<RulePromptOptimizeResult> {
      this.isPromptOptimizing = true
      this.error = ''
      try {
        const response = await optimizeRulePrompt(payload)
        this.promptOptimizeResult = response.data
        return response.data
      } catch (error) {
        this.error = error instanceof Error ? error.message : '优化规则描述失败。'
        throw error
      } finally {
        this.isPromptOptimizing = false
      }
    },

    clearPromptOptimizeResult(): void {
      this.promptOptimizeResult = null
    },

    async loadDrafts(): Promise<void> {
      this.isDraftHistoryLoading = true
      this.error = ''
      try {
        const response = await listAiDrafts(20)
        this.drafts = response.data.items
      } catch (error) {
        this.error = error instanceof Error ? error.message : '读取 AI 草稿历史失败。'
      } finally {
        this.isDraftHistoryLoading = false
      }
    },

    setCurrentDraft(draft: AiRuleDraft): void {
      this.currentDraft = draft
    },

    async markApplied(draftId: number | null | undefined): Promise<void> {
      if (!draftId) {
        return
      }
      await markAiDraftApplied(draftId)
      if (this.currentDraft?.draft_id === draftId) {
        this.currentDraft = { ...this.currentDraft, applied: true }
      }
      this.drafts = this.drafts.map((draft) =>
        draft.draft_id === draftId ? { ...draft, applied: true } : draft,
      )
    },

    async deleteDraft(draftId: number): Promise<void> {
      await deleteAiDraft(draftId)
      this.drafts = this.drafts.filter((draft) => draft.draft_id !== draftId)
      if (this.currentDraft?.draft_id === draftId) {
        this.currentDraft = null
      }
    },

    async clearDraftHistory(): Promise<void> {
      await clearAiDrafts()
      this.drafts = []
      this.currentDraft = null
    },
  },
})

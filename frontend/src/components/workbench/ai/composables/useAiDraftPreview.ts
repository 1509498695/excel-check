import { computed, ref, type Ref } from 'vue'
import { ElMessage } from 'element-plus'

import type { AiRuleDraft, AiRuleDraftPayload } from '../../../../types/ai'
import type { AbnormalResult, ExecutionResponse } from '../../../../types/api'
import { buildAiPreviewExplanation } from '../../../../utils/aiPreviewExplanation'

interface UseAiDraftPreviewOptions {
  currentDraft: Ref<AiRuleDraft | null>
  previewAiRuleDraft: (payload: AiRuleDraftPayload) => Promise<ExecutionResponse>
  buildDraftPayloadForWorkflow: (draft: AiRuleDraft) => AiRuleDraftPayload
}

export function useAiDraftPreview(options: UseAiDraftPreviewOptions) {
  const previewResult = ref<ExecutionResponse | null>(null)
  const previewError = ref('')
  const isPreviewing = ref(false)
  const previewRows = computed<AbnormalResult[]>(() => {
    const data = previewResult.value?.data
    return data?.list ?? data?.abnormal_results ?? []
  })
  const previewTotal = computed(() => previewResult.value?.data.total ?? previewRows.value.length)
  const previewFailedSources = computed(() => previewResult.value?.meta.failed_sources ?? [])
  const previewExplanation = computed(() => buildAiPreviewExplanation(previewResult.value))
  const isPreviewSuccessful = computed(
    () => Boolean(previewResult.value) && !previewError.value && previewFailedSources.value.length === 0,
  )

  function resetPreview(): void {
    previewResult.value = null
    previewError.value = ''
  }

  async function previewDraft(draft = options.currentDraft.value): Promise<boolean> {
    if (!draft || draft.verdict !== 'ready') {
      ElMessage.warning('当前没有可预校验的 ready 草稿。')
      return false
    }
    if (!draft.draft.rules_to_add.length) {
      ElMessage.warning('当前草稿没有可执行规则。')
      return false
    }

    isPreviewing.value = true
    previewError.value = ''
    previewResult.value = null
    try {
      previewResult.value = await options.previewAiRuleDraft(options.buildDraftPayloadForWorkflow(draft))
      if (previewFailedSources.value.length) {
        ElMessage.warning('预校验完成，但存在数据源读取失败。')
      } else {
        ElMessage.success('预校验完成，可查看结果后决定是否添加。')
      }
      return previewFailedSources.value.length === 0
    } catch (error) {
      previewError.value = error instanceof Error ? error.message : '预校验失败。'
      ElMessage.error(previewError.value)
      return false
    } finally {
      isPreviewing.value = false
    }
  }

  return {
    previewResult,
    previewError,
    isPreviewing,
    previewRows,
    previewTotal,
    previewFailedSources,
    previewExplanation,
    isPreviewSuccessful,
    resetPreview,
    previewDraft,
  }
}

import { ref, type ComputedRef, type Ref } from 'vue'
import { ElMessage } from 'element-plus'

import type { AiRuleDraft, AiRuleDraftPayload } from '../../../../types/ai'
import type { FixedRuleDefinition } from '../../../../types/fixedRules'

interface UseAiDraftApplyOptions {
  currentDraft: Ref<AiRuleDraft | null>
  isPreviewSuccessful: ComputedRef<boolean>
  duplicateRuleIds: ComputedRef<Set<string>>
  applyAiRuleDraft: (payload: AiRuleDraftPayload) => Promise<string[]>
  markApplied: (draftId: number | null | undefined) => Promise<void>
  buildDraftPayloadForWorkflow: (
    draft: AiRuleDraft,
    options?: { rule?: FixedRuleDefinition; rules?: FixedRuleDefinition[]; ensureGroup?: boolean },
  ) => AiRuleDraftPayload
  onApplied: (ruleIds: string[], options?: { execute?: boolean }) => void
}

export function useAiDraftApply(options: UseAiDraftApplyOptions) {
  const isApplying = ref(false)

  async function applyDraft(applyOptions?: { execute?: boolean; rule?: FixedRuleDefinition }): Promise<void> {
    const draft = options.currentDraft.value
    if (!draft || draft.verdict !== 'ready') {
      ElMessage.warning('当前没有可添加的规则草稿。')
      return
    }
    if (!options.isPreviewSuccessful.value) {
      ElMessage.warning('请先完成预校验，确认数据源和规则可执行后再添加。')
      return
    }
    if (!draft.draft.rules_to_add.length) {
      ElMessage.warning('当前草稿没有规则可添加。')
      return
    }
    const candidateRules = applyOptions?.rule ? [applyOptions.rule] : draft.draft.rules_to_add
    const rulesToApply = candidateRules.filter((rule) => !options.duplicateRuleIds.value.has(rule.rule_id))
    const skippedCount = candidateRules.length - rulesToApply.length
    if (!rulesToApply.length) {
      ElMessage.warning('当前规则已存在，无需重复添加。')
      return
    }

    isApplying.value = true
    try {
      const payload = options.buildDraftPayloadForWorkflow(draft, {
        rules: rulesToApply,
        ensureGroup: true,
      })
      const ruleIds = await options.applyAiRuleDraft(payload)
      if (!applyOptions?.rule || draft.draft.rules_to_add.length === 1) {
        await options.markApplied(draft.draft_id)
      }
      ElMessage.success(
        skippedCount
          ? `已跳过 ${skippedCount} 条已有规则，新增 ${ruleIds.length} 条规则并保存。`
          : `已添加 ${ruleIds.length} 条规则并保存。`,
      )
      options.onApplied(ruleIds, { execute: applyOptions?.execute })
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : '添加规则失败。')
    } finally {
      isApplying.value = false
    }
  }

  return {
    isApplying,
    applyDraft,
  }
}

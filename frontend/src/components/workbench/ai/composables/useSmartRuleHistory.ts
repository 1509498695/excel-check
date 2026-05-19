import { ElMessage, ElMessageBox } from 'element-plus'
import type { Ref } from 'vue'

import type { AiRuleDraft } from '../../../../types/ai'
import type { SmartRuleWorkflowHintsState } from '../../../../utils/aiRuleInputDraft'

interface UseSmartRuleHistoryOptions {
  description: Ref<string>
  selectedVariableTags: Ref<string[]>
  workflowHints: SmartRuleWorkflowHintsState
  defaultGroupName: string
  clearManualHintEdits: () => void
  setCurrentDraft: (draft: AiRuleDraft) => void
  clearPromptOptimizeResult: () => void
  deleteDraft: (draftId: number) => Promise<void>
  clearDraftHistory: () => Promise<void>
  resetPreview: () => void
}

export function useSmartRuleHistory(options: UseSmartRuleHistoryOptions) {
  function hydrateHintsFromDraft(draft: AiRuleDraft): void {
    options.clearManualHintEdits()
    const firstSource = draft.draft.sources_to_add[0]
    const firstVariable = draft.draft.variables_to_add[0]
    const firstRule = draft.draft.rules_to_add[0]
    const reusedTags = new Set(draft.draft.reuse_variable_tags)
    draft.draft.rules_to_add.forEach((rule) => {
      if (rule.target_variable_tag) reusedTags.add(rule.target_variable_tag)
      if (rule.reference_variable_tag) reusedTags.add(rule.reference_variable_tag)
    })
    options.selectedVariableTags.value = Array.from(reusedTags)
    options.workflowHints.ruleTypeHint = firstRule?.rule_type || options.workflowHints.ruleTypeHint
    options.workflowHints.targetVariableTag = firstRule?.target_variable_tag || options.workflowHints.targetVariableTag
    options.workflowHints.referenceVariableTag =
      firstRule?.reference_variable_tag || options.workflowHints.referenceVariableTag
    options.workflowHints.leftVariableTag = firstRule?.target_variable_tag || options.workflowHints.leftVariableTag
    options.workflowHints.rightVariableTag = firstRule?.reference_variable_tag || options.workflowHints.rightVariableTag
    options.workflowHints.sourceId = firstVariable?.source_id || firstSource?.id || options.workflowHints.sourceId
    options.workflowHints.sourceUrl =
      firstSource?.pathOrUrl || firstSource?.url || firstSource?.path || options.workflowHints.sourceUrl
    options.workflowHints.sheet = firstVariable?.sheet || options.workflowHints.sheet
    options.workflowHints.targetField =
      firstVariable?.variable_kind === 'composite'
        ? firstVariable.columns?.[0] ?? options.workflowHints.targetField
        : firstVariable?.column || options.workflowHints.targetField
    options.workflowHints.displayField = firstRule?.display_field || options.workflowHints.displayField
    options.workflowHints.ruleGroupName = options.defaultGroupName
    options.workflowHints.keyColumn = firstVariable?.key_column || options.workflowHints.keyColumn
    options.workflowHints.compositeColumns =
      firstVariable?.variable_kind === 'composite'
        ? (firstVariable.columns ?? []).join(',')
        : options.workflowHints.compositeColumns
  }

  function loadHistoryDraft(draft: AiRuleDraft): void {
    options.setCurrentDraft(draft)
    options.clearPromptOptimizeResult()
    const originalDescription = draft.description?.trim()
    if (originalDescription) {
      options.description.value = originalDescription
    }
    hydrateHintsFromDraft(draft)
    options.resetPreview()
  }

  async function deleteHistoryDraft(draft: AiRuleDraft): Promise<void> {
    if (!draft.draft_id) return
    await options.deleteDraft(draft.draft_id)
    ElMessage.success('草稿已删除。')
  }

  async function clearHistory(): Promise<void> {
    try {
      await ElMessageBox.confirm('确认清空最近 20 条 AI 草稿历史？', '清空草稿历史', {
        confirmButtonText: '清空',
        cancelButtonText: '取消',
        type: 'warning',
      })
    } catch {
      return
    }
    await options.clearDraftHistory()
    options.resetPreview()
    ElMessage.success('草稿历史已清空。')
  }

  return {
    hydrateHintsFromDraft,
    loadHistoryDraft,
    deleteHistoryDraft,
    clearHistory,
  }
}

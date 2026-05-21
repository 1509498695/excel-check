import { ref } from 'vue'

export type RuleDialogMode = 'create' | 'edit'

export function useRuleDialog() {
  const isRuleDialogVisible = ref(false)
  const ruleDialogMode = ref<RuleDialogMode>('create')
  const isInitializingRuleDialog = ref(false)

  function beginRuleDialog(mode: RuleDialogMode): void {
    isInitializingRuleDialog.value = true
    ruleDialogMode.value = mode
  }

  function showRuleDialog(): void {
    isRuleDialogVisible.value = true
  }

  function closeRuleDialog(): void {
    isRuleDialogVisible.value = false
  }

  function finishRuleDialogInit(): void {
    isInitializingRuleDialog.value = false
  }

  return {
    isRuleDialogVisible,
    ruleDialogMode,
    isInitializingRuleDialog,
    beginRuleDialog,
    showRuleDialog,
    closeRuleDialog,
    finishRuleDialogInit,
  }
}

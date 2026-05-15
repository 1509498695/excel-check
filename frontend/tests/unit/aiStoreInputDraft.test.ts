import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useAiStore } from '../../src/store/ai'

describe('ai store smart rule input draft', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with an empty session draft and the default AI rule group', () => {
    const store = useAiStore()

    expect(store.smartRuleInputDraft.description).toBe('')
    expect(store.smartRuleInputDraft.extraHints).toBe('')
    expect(store.smartRuleInputDraft.selectedVariableTags).toEqual([])
    expect(store.smartRuleInputDraft.allowAutoComplete).toBe(false)
    expect(store.smartRuleInputDraft.workflowHints.ruleGroupName).toBe('AI生成规则组')
    expect(store.smartRuleInputDraft.templateWorkflowHints).toEqual({})
  })

  it('resets user input, selected variables and workflow hints back to defaults', () => {
    const store = useAiStore()
    store.smartRuleInputDraft.description = '校验 ID 不能为空'
    store.smartRuleInputDraft.extraHints = '预校验建议'
    store.smartRuleInputDraft.selectedVariableTags = ['[items-id]']
    store.smartRuleInputDraft.allowAutoComplete = true
    store.smartRuleInputDraft.workflowHints.targetField = 'ID'
    store.smartRuleInputDraft.workflowHints.ruleGroupName = '临时分组'
    store.smartRuleInputDraft.templateWorkflowHints = {
      target_field: 'ID',
      target_variable_tag: '[items-id]',
    }

    store.resetSmartRuleInputDraft()

    expect(store.smartRuleInputDraft.description).toBe('')
    expect(store.smartRuleInputDraft.extraHints).toBe('')
    expect(store.smartRuleInputDraft.selectedVariableTags).toEqual([])
    expect(store.smartRuleInputDraft.allowAutoComplete).toBe(false)
    expect(store.smartRuleInputDraft.workflowHints.targetField).toBe('')
    expect(store.smartRuleInputDraft.workflowHints.ruleGroupName).toBe('AI生成规则组')
    expect(store.smartRuleInputDraft.templateWorkflowHints).toEqual({})
  })
})

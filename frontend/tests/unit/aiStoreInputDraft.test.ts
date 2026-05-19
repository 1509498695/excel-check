import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useAiStore } from '../../src/store/ai'
import {
  AI_RULE_DESCRIPTION_TEMPLATE,
  createDefaultSmartRuleWorkflowHintsState,
  groupSmartRuleWorkflowHints,
  serializeHintsToWorkflowHints,
} from '../../src/utils/aiRuleInputDraft'

describe('ai store smart rule input draft', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with the default short template and the default AI rule group', () => {
    const store = useAiStore()

    expect(store.smartRuleInputDraft.description).toBe(AI_RULE_DESCRIPTION_TEMPLATE)
    expect(store.smartRuleInputDraft.extraHints).toBe('')
    expect(store.smartRuleInputDraft.selectedVariableTags).toEqual([])
    expect(store.smartRuleInputDraft.allowAutoComplete).toBe(false)
    expect(store.smartRuleInputDraft.workflowHints.ruleGroupName).toBe('AI生成规则组')
    expect(store.smartRuleInputDraft.workflowHintGroups.rule.ruleGroupName).toBe('AI生成规则组')
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
    store.smartRuleInputDraft.workflowHintGroups.rule.ruleGroupName = '临时分组'
    store.smartRuleInputDraft.templateWorkflowHints = {
      target_field: 'ID',
      target_variable_tag: '[items-id]',
    }

    store.resetSmartRuleInputDraft()

    expect(store.smartRuleInputDraft.description).toBe(AI_RULE_DESCRIPTION_TEMPLATE)
    expect(store.smartRuleInputDraft.extraHints).toBe('')
    expect(store.smartRuleInputDraft.selectedVariableTags).toEqual([])
    expect(store.smartRuleInputDraft.allowAutoComplete).toBe(false)
    expect(store.smartRuleInputDraft.workflowHints.targetField).toBe('')
    expect(store.smartRuleInputDraft.workflowHints.ruleGroupName).toBe('AI生成规则组')
    expect(store.smartRuleInputDraft.workflowHintGroups.rule.ruleGroupName).toBe('AI生成规则组')
    expect(store.smartRuleInputDraft.templateWorkflowHints).toEqual({})
  })

  it('serializes flat workflow hints through the single backend payload entrypoint', () => {
    const workflowHints = createDefaultSmartRuleWorkflowHintsState()
    workflowHints.sourceUrl = 'https://svn.example.com/config.xls'
    workflowHints.sheet = 'items'
    workflowHints.targetField = 'ID'
    workflowHints.keyColumn = 'Key'
    workflowHints.compositeColumns = 'Key, ID, Name'
    workflowHints.filterField = 'Status'
    workflowHints.filterOperator = 'ne'
    workflowHints.filterValue = '0'

    const payload = serializeHintsToWorkflowHints(workflowHints, {
      dryRunWorkflowHints: {
        filters: [{ field: 'Type', operator: 'eq', value: 'main' }],
      },
      selectedVariableTags: ['[items-id]'],
    })

    expect(payload.source_type).toBe('svn')
    expect(payload.target_variable_tag).toBe('[items-id]')
    expect(payload.key_column).toBeUndefined()
    expect(payload.composite_columns).toEqual(['ID', 'Name'])
    expect(payload.filter_operator).toBe('ne')
    expect(payload.filters).toEqual([{ field: 'Type', operator: 'eq', value: 'main' }])
  })

  it('serializes grouped workflow hints with the same backend payload shape', () => {
    const workflowHints = createDefaultSmartRuleWorkflowHintsState()
    workflowHints.sourceId = 'src_demo'
    workflowHints.sheet = 'items'
    workflowHints.targetField = 'ID'
    workflowHints.ruleTypeHint = 'not_null'
    workflowHints.targetVariableTag = '[items-id]'

    const payload = serializeHintsToWorkflowHints(groupSmartRuleWorkflowHints(workflowHints))

    expect(payload).toMatchObject({
      source_id: 'src_demo',
      sheet: 'items',
      target_field: 'ID',
      rule_type_hint: 'not_null',
      target_variable_tag: '[items-id]',
    })
  })
})

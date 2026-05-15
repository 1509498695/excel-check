// @vitest-environment happy-dom

import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { defineComponent } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import WorkbenchAiRulePanel from '../../src/components/workbench/WorkbenchAiRulePanel.vue'
import { useAiStore } from '../../src/store/ai'
import { useWorkbenchStore } from '../../src/store/workbench'
import type { AiRuleDraft } from '../../src/types/ai'
import type { VariableTag } from '../../src/types/workbench'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('../../src/api/ai', () => ({
  clearAiDrafts: vi.fn(),
  deleteAiDraft: vi.fn(),
  deleteAiProvider: vi.fn(),
  generateRuleDraft: vi.fn(),
  getAiProvider: vi.fn().mockResolvedValue({
    code: 0,
    msg: 'ok',
    data: {
      provider_preset: 'openai',
      protocol: 'openai_compatible',
      base_url: 'https://api.openai.com/v1',
      model: 'test-model',
      api_key_masked: 'sk-***',
      has_extra_headers: false,
    },
  }),
  listAiDrafts: vi.fn().mockResolvedValue({
    code: 0,
    msg: 'ok',
    data: { items: [], total: 0 },
  }),
  markAiDraftApplied: vi.fn(),
  optimizeRulePrompt: vi.fn(),
  saveAiProvider: vi.fn(),
  testAiProvider: vi.fn(),
}))

const variable: VariableTag = {
  tag: '[items-id]',
  source_id: 'src_items',
  sheet: 'items',
  variable_kind: 'single',
  column: 'ID',
  expected_type: 'int',
}

const ButtonStub = {
  template: '<button type="button" v-bind="$attrs"><slot name="icon" /><slot /></button>',
}

const historyDraft: AiRuleDraft = {
  draft_id: 1,
  description: '历史草稿：校验 ID 不能为空',
  verdict: 'ready',
  rule_type: 'not_null',
  confidence: 0.9,
  reasoning_summary: '历史草稿',
  draft: {
    sources_to_add: [],
    variables_to_add: [variable],
    rules_to_add: [
      {
        rule_id: 'history-not-null',
        group_id: 'AI生成规则组',
        rule_name: 'ID 非空',
        target_variable_tag: '[items-id]',
        rule_type: 'not_null',
      },
    ],
    reuse_variable_tags: ['[items-id]'],
  },
  missing: [],
  extension_suggestions: [],
  applied: false,
}

const SmartRuleInputCardStub = defineComponent({
  props: {
    description: { type: String, required: true },
    selectedVariableTags: { type: Array, required: true },
  },
  emits: ['update:description', 'update:selectedVariableTags', 'clear', 'load-example', 'apply-template'],
  setup(_props, { emit }) {
    function updateDescription(event: Event): void {
      emit('update:description', (event.target as HTMLTextAreaElement).value)
    }
    function selectVariable(): void {
      emit('update:selectedVariableTags', ['[items-id]'])
    }
    return { selectVariable, updateDescription }
  },
  template: `
    <section>
      <textarea
        data-test="smart-description"
        :value="description"
        @input="updateDescription"
      />
      <button type="button" data-test="smart-select-variable" @click="selectVariable">select</button>
      <button type="button" data-test="smart-clear" @click="$emit('clear')">clear</button>
      <button type="button" data-test="smart-load-example" @click="$emit('load-example')">example</button>
      <button type="button" data-test="smart-apply-template" @click="$emit('apply-template', 'single-not-null')">template</button>
      <span data-test="smart-selected-tags">{{ selectedVariableTags.join(',') }}</span>
    </section>
  `,
})

const DraftHistoryPanelStub = defineComponent({
  emits: ['fill'],
  setup(_props, { emit }) {
    function fillHistory(): void {
      emit('fill', historyDraft)
    }
    return { fillHistory }
  },
  template: '<button type="button" data-test="draft-fill" @click="fillHistory">fill</button>',
})

function mountPanel(pinia: Pinia) {
  setActivePinia(pinia)
  const workbenchStore = useWorkbenchStore()
  workbenchStore.variables = [variable]
  return mount(WorkbenchAiRulePanel, {
    global: {
      plugins: [pinia],
      stubs: {
        AiRuleResultList: true,
        DraftHistoryPanel: DraftHistoryPanelStub,
        PendingConfigPreview: true,
        PrimaryButton: ButtonStub,
        SecondaryButton: ButtonStub,
        SmartRuleInputCard: SmartRuleInputCardStub,
        'el-drawer': { template: '<div><slot /></div>' },
        'el-table': { template: '<table><slot /></table>' },
        'el-table-column': true,
        CircleCheck: true,
        MagicStick: true,
        Refresh: true,
        VideoPlay: true,
      },
    },
  })
}

describe('WorkbenchAiRulePanel smart input draft', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('keeps description and selected variables after the panel is remounted', async () => {
    const pinia = createPinia()
    const firstWrapper = mountPanel(pinia)
    await flushPromises()

    await firstWrapper.get('[data-test="smart-description"]').setValue('校验 ID 不能为空')
    await firstWrapper.get('[data-test="smart-select-variable"]').trigger('click')

    const aiStore = useAiStore()
    expect(aiStore.smartRuleInputDraft.description).toBe('校验 ID 不能为空')
    expect(aiStore.smartRuleInputDraft.selectedVariableTags).toEqual(['[items-id]'])

    firstWrapper.unmount()
    const secondWrapper = mountPanel(pinia)
    await flushPromises()

    const textarea = secondWrapper.get<HTMLInputElement>('[data-test="smart-description"]').element
    expect(textarea.value).toBe('校验 ID 不能为空')
    expect(secondWrapper.get('[data-test="smart-selected-tags"]').text()).toBe('[items-id]')
  })

  it('clears the session draft only when the user clicks clear input', async () => {
    const pinia = createPinia()
    const wrapper = mountPanel(pinia)
    await flushPromises()

    const aiStore = useAiStore()
    aiStore.smartRuleInputDraft.description = '校验 ID 不能为空'
    aiStore.smartRuleInputDraft.selectedVariableTags = ['[items-id]']
    aiStore.smartRuleInputDraft.workflowHints.targetField = 'ID'
    aiStore.smartRuleInputDraft.workflowHints.ruleGroupName = '临时分组'

    await wrapper.get('[data-test="smart-clear"]').trigger('click')

    expect(aiStore.smartRuleInputDraft.description).toBe('')
    expect(aiStore.smartRuleInputDraft.selectedVariableTags).toEqual([])
    expect(aiStore.smartRuleInputDraft.workflowHints.targetField).toBe('')
    expect(aiStore.smartRuleInputDraft.workflowHints.ruleGroupName).toBe('AI生成规则组')
  })

  it('writes example, template and history fill actions into the same session draft', async () => {
    const pinia = createPinia()
    const wrapper = mountPanel(pinia)
    await flushPromises()
    const aiStore = useAiStore()

    await wrapper.get('[data-test="smart-load-example"]').trigger('click')
    expect(aiStore.smartRuleInputDraft.description).toContain('校验规则筛选DESC3')

    await wrapper.get('[data-test="smart-select-variable"]').trigger('click')
    await wrapper.get('[data-test="smart-apply-template"]').trigger('click')
    expect(aiStore.smartRuleInputDraft.description).toContain('ID 字段不能为空')
    expect(aiStore.smartRuleInputDraft.workflowHints.ruleTypeHint).toBe('not_null')

    await wrapper.get('[data-test="draft-fill"]').trigger('click')
    expect(aiStore.smartRuleInputDraft.description).toBe('历史草稿：校验 ID 不能为空')
    expect(aiStore.smartRuleInputDraft.selectedVariableTags).toEqual(['[items-id]'])
    expect(aiStore.smartRuleInputDraft.workflowHints.targetVariableTag).toBe('[items-id]')
  })
})

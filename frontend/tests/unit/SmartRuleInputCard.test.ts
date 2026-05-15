// @vitest-environment happy-dom

import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import SmartRuleInputCard from '../../src/components/workbench/SmartRuleInputCard.vue'
import type { VariableTag } from '../../src/types/workbench'
import {
  getAvailableAiRuleTemplates,
  getRecommendedAiRuleTemplates,
} from '../../src/utils/aiRuleTemplates'

const variables: VariableTag[] = [
  {
    tag: '[items-id]',
    source_id: 'src_items',
    sheet: 'items',
    variable_kind: 'single',
    column: 'ID',
  },
]

const ButtonStub = {
  template: '<button type="button" v-bind="$attrs"><slot name="icon" /><slot /></button>',
}

const globalStubs = {
  PrimaryButton: ButtonStub,
  SecondaryButton: ButtonStub,
  'el-select': { template: '<div><slot /></div>' },
  'el-option': { template: '<div><slot /></div>' },
  'el-switch': { template: '<button type="button" />' },
  'el-input': { template: '<textarea />' },
  Delete: true,
  MagicStick: true,
  Refresh: true,
  Setting: true,
  ArrowDown: true,
  ArrowUp: true,
}

function mountInputCard(options: { withRecommendations?: boolean } = {}) {
  return mount(SmartRuleInputCard, {
    props: {
      description: '',
      selectedVariableTags: ['[items-id]'],
      allowAutoComplete: false,
      variables,
      providerLabel: 'OpenAI / test-model',
      isConfigured: true,
      isGenerating: false,
      isOptimizing: false,
      canGenerate: true,
      maxLength: 800,
      promptText: 'prompt',
      templates: getAvailableAiRuleTemplates({
        selectedVariables: variables,
        allowAutoComplete: false,
      }),
      recommendedTemplates: options.withRecommendations
        ? getRecommendedAiRuleTemplates(variables)
        : [],
    },
    global: {
      stubs: globalStubs,
    },
  })
}

describe('SmartRuleInputCard', () => {
  it('renders variable-based recommendations and emits the selected card id', async () => {
    const wrapper = mountInputCard({ withRecommendations: true })

    expect(wrapper.text()).toContain('根据已选变量推荐')
    expect(wrapper.text()).toContain('ID 不能为空')

    await wrapper.get('[data-test="ai-rule-recommendation-card"]').trigger('click')

    expect(wrapper.emitted('apply-template')?.[0]).toEqual([
      'recommended-single-not-null-items-id',
    ])
  })

  it('keeps regular templates collapsed by default and emits after expanding', async () => {
    const wrapper = mountInputCard({ withRecommendations: false })

    expect(wrapper.text()).not.toContain('根据已选变量推荐')
    expect(wrapper.text()).toContain('规则模板 / 常用案例')
    expect(wrapper.find('[data-test="ai-rule-template-card"]').exists()).toBe(false)

    await wrapper.get('[data-test="ai-rule-template-toggle"]').trigger('click')

    expect(wrapper.find('[data-test="ai-rule-template-card"]').exists()).toBe(true)

    await wrapper.get('[data-test="ai-rule-template-card"]').trigger('click')

    expect(wrapper.emitted('apply-template')?.[0]).toEqual(['single-not-null'])
  })
})

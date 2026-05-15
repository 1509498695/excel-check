// @vitest-environment happy-dom

import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AiRuleResultItem from '../../src/components/workbench/AiRuleResultItem.vue'
import type { AiRuleResultViewModel } from '../../src/utils/aiRuleViewModel'

const ButtonStub = {
  template: '<button type="button" v-bind="$attrs"><slot name="icon" /><slot /></button>',
}

const globalStubs = {
  PrimaryButton: ButtonStub,
  SecondaryButton: ButtonStub,
  CircleCheck: true,
  CircleClose: true,
  CirclePlus: true,
  EditPen: true,
  MagicStick: true,
  Plus: true,
  QuestionFilled: true,
  View: true,
}

function mountResultItem(item: AiRuleResultViewModel) {
  return mount(AiRuleResultItem, {
    props: {
      item,
      canApply: true,
      canAutoCompleteApply: true,
      autoCompleteApplyLoading: false,
    },
    global: {
      stubs: globalStubs,
    },
  })
}

function baseItem(overrides: Partial<AiRuleResultViewModel> = {}): AiRuleResultViewModel {
  return {
    id: 'rule-1',
    status: 'ready',
    title: 'Status 只能是 0 或 1',
    ruleTypeLabel: '常量比较',
    sourceLabel: 'items（本地 Excel）',
    sheetLabel: 'items',
    fieldLabel: 'Status',
    variableLabel: '[items-status]',
    groupLabel: 'AI生成规则组',
    metaText: '规则类型 常量比较',
    missingText: '',
    reasonText: '',
    explanationTitle: '为什么匹配为常量比较',
    explanationItems: [
      {
        label: '匹配依据',
        text: '识别到固定值集合判断，适合用常量比较。',
        tone: 'success',
      },
      {
        label: '规则对象',
        text: '目标变量 [items-status]，字段 Status。',
      },
    ],
    nextActionText: '先点“查看配置”确认变量、字段和参数。',
    rewriteHintText: '',
    resolveActionText: '',
    rule: {
      rule_id: 'rule-1',
      group_id: 'ai-group',
      rule_name: 'Status 只能是 0 或 1',
      target_variable_tag: '[items-status]',
      rule_type: 'fixed_value_compare',
      operator: 'eq',
      expected_value: '0,1',
      expected_value_mode: 'set',
    },
    ...overrides,
  }
}

describe('AiRuleResultItem', () => {
  it('renders ready explanation cards and keeps ready actions', async () => {
    const wrapper = mountResultItem(baseItem())

    expect(wrapper.text()).toContain('为什么匹配为常量比较')
    expect(wrapper.text()).toContain('固定值集合判断')
    expect(wrapper.text()).toContain('查看配置')
    expect(wrapper.text()).toContain('添加规则')

    await wrapper.findAll('button').find((button) => button.text().includes('查看配置'))?.trigger('click')

    expect(wrapper.emitted('view-config')).toHaveLength(1)
  })

  it('uses the missing suggested action as the repair button label', async () => {
    const missing = {
      kind: 'variable' as const,
      message: '缺少组合变量。',
      suggested_action: 'open_composite_variable_dialog' as const,
      prefill: { sheet: 'items' },
    }
    const wrapper = mountResultItem(
      baseItem({
        status: 'needs_input',
        title: '信息不足，暂不能自动添加',
        explanationTitle: '还缺变量',
        explanationItems: [{ label: '缺口说明', text: missing.message, tone: 'warning' }],
        nextActionText: '点击“新增组合变量”补齐 Key 和组合字段。',
        resolveActionText: '新增组合变量',
        missingText: missing.message,
        missing,
        rule: undefined,
      }),
    )

    expect(wrapper.text()).toContain('还缺变量')
    expect(wrapper.text()).toContain('新增组合变量')

    await wrapper.findAll('button').find((button) => button.text().includes('新增组合变量'))?.trigger('click')

    expect(wrapper.emitted('resolve-missing')?.[0]).toEqual([missing])
  })

  it('renders rejected rewrite guidance and emits rewrite-rule', async () => {
    const wrapper = mountResultItem(
      baseItem({
        status: 'rejected',
        title: '当前规则不可添加',
        explanationTitle: '为什么当前不可添加',
        explanationItems: [{ label: '拒绝原因', text: '当前规则库不支持聚合统计。', tone: 'danger' }],
        nextActionText: '点击“改写规则”回到输入框。',
        rewriteHintText: '可尝试改写成：非空、唯一、固定值比较、跨组 Key 对比。',
        rule: undefined,
      }),
    )

    expect(wrapper.text()).toContain('为什么当前不可添加')
    expect(wrapper.text()).toContain('跨组 Key 对比')

    await wrapper.findAll('button').find((button) => button.text().includes('改写规则'))?.trigger('click')

    expect(wrapper.emitted('rewrite-rule')).toHaveLength(1)
  })
})

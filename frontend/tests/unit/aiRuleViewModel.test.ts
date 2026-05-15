import { describe, expect, it } from 'vitest'

import type { AiRuleDraft } from '../../src/types/ai'
import {
  mapAiDraftToResultItems,
  markAiRuleResultDuplicate,
} from '../../src/utils/aiRuleViewModel'

function baseDraft(overrides: Partial<AiRuleDraft> = {}): AiRuleDraft {
  return {
    draft_id: 1,
    description: '检查状态字段只能是 0 或 1',
    verdict: 'ready',
    rule_type: 'fixed_value_compare',
    confidence: 0.91,
    reasoning_summary: '识别到固定值集合判断，适合用常量比较。',
    draft: {
      sources_to_add: [
        {
          id: 'items',
          type: 'local_excel',
          pathOrUrl: 'D:/fixtures/items.xlsx',
        },
      ],
      variables_to_add: [
        {
          tag: '[items-status]',
          source_id: 'items',
          sheet: 'items',
          variable_kind: 'single',
          column: 'Status',
        },
      ],
      rules_to_add: [
        {
          rule_id: 'ai-rule-status',
          group_id: 'ai-group',
          rule_name: 'Status 只能是 0 或 1',
          target_variable_tag: '[items-status]',
          display_field: 'Status',
          rule_type: 'fixed_value_compare',
          operator: 'eq',
          expected_value: '0,1',
          expected_value_mode: 'set',
        },
      ],
      reuse_variable_tags: [],
    },
    missing: [],
    rejection_reason: null,
    extension_suggestions: [],
    applied: false,
    created_at: '2026-05-15T10:00:00Z',
    ...overrides,
  }
}

describe('aiRuleViewModel', () => {
  it('maps ready drafts to explanation cards with rule type reasoning', () => {
    const item = mapAiDraftToResultItems(baseDraft())[0]

    expect(item.status).toBe('ready')
    expect(item.explanationTitle).toBe('为什么匹配为常量比较')
    expect(item.explanationItems.map((entry) => entry.label)).toContain('匹配依据')
    expect(item.explanationItems.map((entry) => entry.text).join(' ')).toContain('固定值集合判断')
    expect(item.nextActionText).toContain('查看配置')
  })

  it('maps needs_input missing items to concrete repair actions', () => {
    const [item] = mapAiDraftToResultItems(
      baseDraft({
        verdict: 'needs_input',
        rule_type: 'composite_condition_check',
        draft: {
          sources_to_add: [],
          variables_to_add: [],
          rules_to_add: [],
          reuse_variable_tags: [],
        },
        missing: [
          {
            kind: 'parameter',
            message: '缺少筛选字段和判断字段。',
            suggested_action: 'edit_description',
            prefill: { sheet: 'items', filter_field: '' },
          },
        ],
      }),
    )

    expect(item.status).toBe('needs_input')
    expect(item.explanationTitle).toBe('还缺规则参数')
    expect(item.resolveActionText).toBe('回到输入框改写')
    expect(item.nextActionText).toContain('回到输入框改写')
    expect(item.explanationItems.map((entry) => entry.text).join(' ')).toContain('缺少筛选字段')
  })

  it('maps rejected drafts to supported-rule rewrite guidance', () => {
    const [item] = mapAiDraftToResultItems(
      baseDraft({
        verdict: 'rejected',
        rule_type: null,
        reasoning_summary: '用户需要按组聚合后比较总数。',
        draft: {
          sources_to_add: [],
          variables_to_add: [],
          rules_to_add: [],
          reuse_variable_tags: [],
        },
        missing: [],
        rejection_reason: '当前规则库不支持按分组聚合统计。',
        extension_suggestions: ['后续可新增聚合统计规则。'],
      }),
    )

    expect(item.status).toBe('rejected')
    expect(item.explanationTitle).toBe('为什么当前不可添加')
    expect(item.explanationItems.map((entry) => entry.text).join(' ')).toContain('分组聚合统计')
    expect(item.rewriteHintText).toContain('非空')
    expect(item.rewriteHintText).toContain('跨组 Key 对比')
  })

  it('marks duplicate ready items without losing explanation fields', () => {
    const [readyItem] = mapAiDraftToResultItems(baseDraft())
    const duplicateItem = markAiRuleResultDuplicate(readyItem)

    expect(duplicateItem.status).toBe('duplicate')
    expect(duplicateItem.reasonText).toContain('已有相同规则')
    expect(duplicateItem.explanationTitle).toContain('已有相同规则')
    expect(duplicateItem.nextActionText).toContain('重新 AI 校验')
  })
})

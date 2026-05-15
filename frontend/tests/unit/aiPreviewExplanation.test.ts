import { describe, expect, it } from 'vitest'

import type { ExecutionResponse } from '../../src/types/api'
import { buildAiPreviewExplanation } from '../../src/utils/aiPreviewExplanation'

function buildResponse(overrides: Partial<ExecutionResponse> = {}): ExecutionResponse {
  return {
    code: 0,
    msg: 'ok',
    meta: {
      execution_time_ms: 12,
      total_rows_scanned: 20,
      failed_sources: [],
      result_id: 1,
    },
    data: {
      total: 0,
      page: 1,
      size: 20,
      list: [],
      abnormal_results: [],
    },
    ...overrides,
  }
}

describe('buildAiPreviewExplanation', () => {
  it('returns passed state when preview has no abnormal rows or failed sources', () => {
    const explanation = buildAiPreviewExplanation(buildResponse())

    expect(explanation.passed).toBe(true)
    expect(explanation.canRegenerate).toBe(false)
    expect(explanation.summaryTitle).toBe('预校验通过')
    expect(explanation.adjustmentHints).toBe('')
  })

  it('explains failed sources and creates adjustment hints', () => {
    const explanation = buildAiPreviewExplanation(
      buildResponse({
        meta: {
          execution_time_ms: 12,
          total_rows_scanned: 0,
          failed_sources: ['src_items'],
          result_id: 1,
        },
      }),
    )

    expect(explanation.passed).toBe(false)
    expect(explanation.failedSources).toEqual(['src_items'])
    expect(explanation.suggestions[0]).toContain('数据源路径')
    expect(explanation.adjustmentHints).toContain('失败数据源：src_items')
    expect(explanation.adjustmentHints).toContain('不要直接保存规则')
  })

  it('groups preview rows by rule name and message with location samples', () => {
    const explanation = buildAiPreviewExplanation(
      buildResponse({
        data: {
          total: 8,
          page: 1,
          size: 20,
          abnormal_results: [],
          list: [
            {
              level: 'warning',
              rule_name: '状态非空',
              location: 'items -> Status',
              row_index: 2,
              raw_value: '',
              display_value: 'item_1',
              message: '字段不能为空。',
            },
            {
              level: 'warning',
              rule_name: '状态非空',
              location: 'items -> Status',
              row_index: 5,
              raw_value: null,
              display_value: 'item_2',
              message: '字段不能为空。',
            },
          ],
        },
      }),
    )

    expect(explanation.totalAbnormal).toBe(8)
    expect(explanation.sampleCount).toBe(2)
    expect(explanation.issueGroups).toHaveLength(1)
    expect(explanation.issueGroups[0].sampleCount).toBe(2)
    expect(explanation.issueGroups[0].sampleRows[0]).toMatchObject({
      rowIndex: 2,
      location: 'items -> Status',
      rawValue: '空值',
      displayValue: 'item_1',
    })
    expect(explanation.adjustmentHints).toContain('规则「状态非空」')
    expect(explanation.adjustmentHints).toContain('行 2，定位 items -> Status')
  })

  it('maps common abnormal messages to repair suggestions', () => {
    const explanation = buildAiPreviewExplanation(
      buildResponse({
        data: {
          total: 5,
          page: 1,
          size: 20,
          abnormal_results: [
            {
              level: 'warning',
              rule_name: '格式校验',
              location: 'items -> Code',
              row_index: 3,
              raw_value: 'abc',
              message: '不符合正则格式。',
            },
            {
              level: 'warning',
              rule_name: 'Key 对比',
              location: 'items -> ID',
              row_index: 4,
              raw_value: '1001',
              message: '缺失该 Key (1001)。',
            },
            {
              level: 'warning',
              rule_name: '状态规则集',
              location: 'items -> Status',
              row_index: 5,
              raw_value: '3',
              message: '不在规则集中的任一值。',
            },
            {
              level: 'warning',
              rule_name: '筛选失败',
              location: 'items -> Type',
              row_index: 6,
              raw_value: 'legacy',
              message: '筛选条件未通过。',
            },
          ],
          list: undefined,
        },
      }),
    )

    expect(explanation.suggestions.join(' ')).toContain('正则表达式')
    expect(explanation.suggestions.join(' ')).toContain('关联 Key')
    expect(explanation.suggestions.join(' ')).toContain('期望值或规则集')
    expect(explanation.suggestions.join(' ')).toContain('筛选字段')
    expect(explanation.adjustmentHints).toContain('异常总数：5')
  })
})

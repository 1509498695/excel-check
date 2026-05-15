import type { AbnormalResult, ExecutionResponse } from '../types/api'

export interface AiPreviewIssueSample {
  ruleName: string
  location: string
  rowIndex: number
  rawValue: string
  displayValue: string
  message: string
}

export interface AiPreviewIssueGroup {
  id: string
  ruleName: string
  message: string
  sampleCount: number
  sampleRows: AiPreviewIssueSample[]
  locations: string[]
  suggestion: string
}

export interface AiPreviewExplanationViewModel {
  hasResult: boolean
  passed: boolean
  hasIssues: boolean
  totalAbnormal: number
  sampleCount: number
  scannedRows: number
  failedSources: string[]
  summaryTitle: string
  summaryText: string
  issueGroups: AiPreviewIssueGroup[]
  suggestions: string[]
  adjustmentHints: string
  canRegenerate: boolean
}

const MAX_GROUPS = 4
const MAX_SAMPLES_PER_GROUP = 3
const MAX_HINT_GROUPS = 3

const emptyExplanation: AiPreviewExplanationViewModel = {
  hasResult: false,
  passed: false,
  hasIssues: false,
  totalAbnormal: 0,
  sampleCount: 0,
  scannedRows: 0,
  failedSources: [],
  summaryTitle: '尚未执行预校验',
  summaryText: 'AI 草稿生成后会先用临时 TaskTree 预校验，确认可执行后再允许添加。',
  issueGroups: [],
  suggestions: [],
  adjustmentHints: '',
  canRegenerate: false,
}

export function buildAiPreviewExplanation(
  result: ExecutionResponse | null | undefined,
): AiPreviewExplanationViewModel {
  if (!result) return { ...emptyExplanation }

  const rows = getPreviewRows(result)
  const failedSources = result.meta.failed_sources ?? []
  const totalAbnormal = result.data.total ?? rows.length
  const scannedRows = result.meta.total_rows_scanned ?? 0
  const issueGroups = buildIssueGroups(rows)
  const failureSuggestions = failedSources.length
    ? ['先修复读取失败的数据源路径、凭据或文件可访问性，再重新预校验。']
    : []
  const suggestions = Array.from(
    new Set([...failureSuggestions, ...issueGroups.map((group) => group.suggestion)]),
  )
  const hasIssues = totalAbnormal > 0 || failedSources.length > 0
  const summaryTitle = hasIssues ? '预校验发现需要确认的问题' : '预校验通过'
  const summaryText = hasIssues
    ? `本次扫描 ${scannedRows} 行，发现 ${totalAbnormal} 条异常，样例中归纳出 ${issueGroups.length} 类主要原因。`
    : `本次扫描 ${scannedRows} 行，未发现异常，也没有数据源读取失败。`

  return {
    hasResult: true,
    passed: !hasIssues,
    hasIssues,
    totalAbnormal,
    sampleCount: rows.length,
    scannedRows,
    failedSources,
    summaryTitle,
    summaryText,
    issueGroups,
    suggestions,
    adjustmentHints: buildAdjustmentHints({
      totalAbnormal,
      sampleCount: rows.length,
      scannedRows,
      failedSources,
      issueGroups,
      suggestions,
    }),
    canRegenerate: hasIssues,
  }
}

function getPreviewRows(result: ExecutionResponse): AbnormalResult[] {
  return result.data.list ?? result.data.abnormal_results ?? []
}

function buildIssueGroups(rows: AbnormalResult[]): AiPreviewIssueGroup[] {
  const groupMap = new Map<string, AiPreviewIssueGroup>()
  rows.forEach((row) => {
    const ruleName = row.rule_name || '未命名规则'
    const message = row.message || '未提供异常说明'
    const key = `${ruleName}\u0000${message}`
    const sample = toSample(row, ruleName, message)
    const current = groupMap.get(key)
    if (current) {
      current.sampleCount += 1
      if (current.sampleRows.length < MAX_SAMPLES_PER_GROUP) {
        current.sampleRows.push(sample)
      }
      if (sample.location && !current.locations.includes(sample.location)) {
        current.locations.push(sample.location)
      }
      return
    }
    groupMap.set(key, {
      id: `preview-${groupMap.size + 1}`,
      ruleName,
      message,
      sampleCount: 1,
      sampleRows: [sample],
      locations: sample.location ? [sample.location] : [],
      suggestion: inferSuggestion(message),
    })
  })

  return Array.from(groupMap.values())
    .sort((left, right) => right.sampleCount - left.sampleCount)
    .slice(0, MAX_GROUPS)
}

function toSample(row: AbnormalResult, ruleName: string, message: string): AiPreviewIssueSample {
  return {
    ruleName,
    location: row.location || '-',
    rowIndex: row.row_index,
    rawValue: formatPreviewValue(row.raw_value, '空值'),
    displayValue: formatPreviewValue(row.display_value, ''),
    message,
  }
}

function inferSuggestion(message: string): string {
  const text = message.toLowerCase()
  if (message.includes('不能为空') || message.includes('空值') || text.includes('null')) {
    return '确认这些空值是否属于业务允许：允许则补充筛选条件或空值策略，不允许则保留非空规则并修复源表数据。'
  }
  if (message.includes('正则') || text.includes('regex') || message.includes('格式')) {
    return '检查正则表达式、字段格式示例和是否需要先加筛选条件，避免把不适用的数据行纳入格式校验。'
  }
  if (message.includes('规则集') || message.includes('期望值') || message.includes('固定值')) {
    return '确认期望值或规则集是否缺少合法取值；如果异常样例其实合法，应把这些值补入规则描述。'
  }
  if (message.includes('Key') || message.includes('key') || message.includes('对齐') || message.includes('缺失该')) {
    return '检查左右变量的关联 Key、筛选条件和比较字段，必要时明确业务 Key 或补充缺失侧数据。'
  }
  if (message.includes('筛选') || message.includes('过滤')) {
    return '核对筛选字段、操作符和判定值；如果只应检查部分行，请在描述中明确筛选条件。'
  }
  if (message.includes('顺序') || message.includes('连续') || message.includes('步长')) {
    return '确认顺序方向、步长和起始值；如果存在跳号或分段连续，请把分段规则写进描述。'
  }
  return '根据样例行确认规则是否过严或字段映射是否有偏差，再补充更明确的字段、筛选、Key 或判断值。'
}

function buildAdjustmentHints(input: {
  totalAbnormal: number
  sampleCount: number
  scannedRows: number
  failedSources: string[]
  issueGroups: AiPreviewIssueGroup[]
  suggestions: string[]
}): string {
  if (!input.failedSources.length && !input.issueGroups.length) return ''

  const lines = [
    '预校验调整建议：',
    `- 扫描行数：${input.scannedRows}`,
    `- 异常总数：${input.totalAbnormal}`,
    `- 当前页样例数：${input.sampleCount}`,
  ]
  if (input.failedSources.length) {
    lines.push(`- 失败数据源：${input.failedSources.join('、')}`)
  }
  input.issueGroups.slice(0, MAX_HINT_GROUPS).forEach((group, index) => {
    const samples = group.sampleRows
      .map(
        (sample) =>
          `行 ${sample.rowIndex}，定位 ${sample.location}，原始值 ${sample.rawValue || '空值'}${
            sample.displayValue ? `，显示字段 ${sample.displayValue}` : ''
          }`,
      )
      .join('；')
    lines.push(
      `- 主要原因 ${index + 1}：规则「${group.ruleName}」在样例中出现 ${group.sampleCount} 次；说明：${group.message}；样例：${samples}`,
    )
  })
  if (input.suggestions.length) {
    lines.push(`- 修复方向：${input.suggestions.join('；')}`)
  }
  lines.push(
    '- 请基于用户原始描述和以上预校验反馈调整规则草稿的字段映射、筛选条件、Key、比较值或正则表达式。',
    '- 只返回新的规则草稿，不要直接保存规则，不要改变 Excel Check 现有 API 或配置格式。',
  )
  return lines.join('\n')
}

function formatPreviewValue(value: unknown, emptyText: string): string {
  if (value === null || value === undefined || value === '') return emptyText
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

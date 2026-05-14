import type { AiMissingItem, AiRuleDraft, AiRuleDraftPayload } from '../types/ai'
import type { FixedRuleDefinition, FixedRuleType } from '../types/fixedRules'
import type { DataSource, VariableTag } from '../types/workbench'
import { getSourceTypeLabel } from './workbenchMeta'

export type AiRuleUiStatus =
  | 'ready'
  | 'duplicate'
  | 'needs_input'
  | 'rejected'
  | 'applied'
  | 'loading'
  | 'empty'
  | 'error'

export interface AiRuleResultViewModel {
  id: string
  status: AiRuleUiStatus
  title: string
  ruleTypeLabel: string
  sourceLabel: string
  sheetLabel: string
  fieldLabel: string
  variableLabel: string
  groupLabel: string
  metaText: string
  missingText: string
  reasonText: string
  rule?: FixedRuleDefinition
  missing?: AiMissingItem
}

export interface PendingConfigPreviewViewModel {
  sources: string[]
  variables: string[]
  rules: string[]
}

export interface AiResultSummaryViewModel {
  total: number
  ready: number
  needsInput: number
  rejected: number
  applied: number
  text: string
  label: string
  tone: 'success' | 'warning' | 'danger' | 'primary' | 'neutral'
}

export interface DraftHistoryViewModel {
  id: string
  title: string
  ruleCount: number
  timeLabel: string
  status: AiRuleUiStatus
  statusLabel: string
  draft: AiRuleDraft
}

const ruleTypeLabelMap: Record<FixedRuleType, string> = {
  fixed_value_compare: '常量比较',
  regex_check: '正则校验',
  not_null: '非空校验',
  unique: '唯一校验',
  sequence_order_check: '顺序校验',
  cross_table_mapping: '跨表映射',
  composite_condition_check: '组合分支',
  dual_composite_compare: '跨组变量',
  multi_composite_pipeline_check: '多组串行',
  multi_composite_mapping_check: '多组映射',
}

export function getAiRuleTypeLabel(ruleType?: FixedRuleType | null): string {
  return ruleType ? ruleTypeLabelMap[ruleType] ?? ruleType : '-'
}

export function normalizeRuleStatus(draft: AiRuleDraft | null | undefined): AiRuleUiStatus {
  if (!draft) return 'empty'
  if (draft.applied) return 'applied'
  return draft.verdict
}

export function getStatusLabel(status: AiRuleUiStatus): string {
  const labels: Record<AiRuleUiStatus, string> = {
    ready: 'ready / 可添加',
    duplicate: '已有规则 / 不用添加',
    needs_input: 'needs_input / 需补充',
    rejected: 'rejected / 不可添加',
    applied: 'applied / 已添加',
    loading: 'loading',
    empty: 'empty',
    error: 'error',
  }
  return labels[status]
}

function getRuleSourceId(rule: FixedRuleDefinition): string {
  return (
    rule.target_variable_tag?.match(/^\[?([^-_\]]+)/)?.[1] ??
    rule.reference_variable_tag?.match(/^\[?([^-_\]]+)/)?.[1] ??
    '-'
  )
}

function getRuleTargetField(rule: FixedRuleDefinition): string {
  const tag = rule.target_variable_tag ?? ''
  const normalized = tag.replace(/^\[/, '').replace(/\]$/, '')
  const segments = normalized.split('-').filter(Boolean)
  return segments.at(-1) ?? rule.display_field ?? '-'
}

function getRuleTitle(rule: FixedRuleDefinition): string {
  const target = rule.target_variable_tag?.replace(/^\[/, '').replace(/\]$/, '') ?? ''
  if (rule.rule_name?.trim()) return rule.rule_name.trim()
  return target || getAiRuleTypeLabel(rule.rule_type)
}

function getVariableByTag(
  payload: AiRuleDraftPayload,
  rule: FixedRuleDefinition,
): VariableTag | undefined {
  const targetTag = rule.target_variable_tag?.trim()
  return payload.variables_to_add.find((variable) => variable.tag === targetTag)
}

function getSourceById(payload: AiRuleDraftPayload, sourceId?: string): DataSource | undefined {
  if (!sourceId) return undefined
  return payload.sources_to_add.find((source) => source.id === sourceId)
}

function formatSource(source: DataSource | undefined, fallback: string): string {
  if (!source) return fallback || '-'
  return `${source.id}（${getSourceTypeLabel(source.type)}）`
}

function buildRuleMeta(rule: FixedRuleDefinition, payload: AiRuleDraftPayload): AiRuleResultViewModel {
  const variable = getVariableByTag(payload, rule)
  const source = getSourceById(payload, variable?.source_id)
  const sourceLabel = formatSource(source, variable?.source_id ?? getRuleSourceId(rule))
  const sheetLabel = variable?.sheet ?? '-'
  const fieldLabel =
    variable?.variable_kind === 'composite'
      ? (variable.columns ?? []).join('、') || '-'
      : variable?.column ?? getRuleTargetField(rule)
  const variableLabel = variable?.tag ?? rule.target_variable_tag ?? '-'
  const groupLabel = rule.group_id || 'AI生成规则组'
  const ruleTypeLabel = getAiRuleTypeLabel(rule.rule_type)
  const metaParts = [
    `规则类型 ${ruleTypeLabel}`,
    `数据源 ${sourceLabel}`,
    `Sheet ${sheetLabel}`,
    `字段 ${fieldLabel}`,
    `变量 ${variableLabel}`,
    `规则组 ${groupLabel}`,
  ]

  return {
    id: rule.rule_id,
    status: 'ready',
    title: getRuleTitle(rule),
    ruleTypeLabel,
    sourceLabel,
    sheetLabel,
    fieldLabel,
    variableLabel,
    groupLabel,
    metaText: metaParts.join('   '),
    missingText: '',
    reasonText: '',
    rule,
  }
}

export function mapAiDraftToResultItems(draft: AiRuleDraft | null): AiRuleResultViewModel[] {
  if (!draft) return []

  const readyItems = draft.draft.rules_to_add.map((rule) => ({
    ...buildRuleMeta(rule, draft.draft),
    status: draft.applied ? ('applied' as const) : ('ready' as const),
  }))

  const missingItems: AiRuleResultViewModel[] = draft.missing.map((item, index) => ({
    id: `missing-${item.kind}-${index}`,
    status: 'needs_input' as const,
    title: '信息不足，暂不能自动添加',
    ruleTypeLabel: getAiRuleTypeLabel(draft.rule_type),
    sourceLabel: '-',
    sheetLabel: '-',
    fieldLabel: '-',
    variableLabel: '-',
    groupLabel: 'AI生成规则组',
    metaText: `缺口类型 ${item.kind}`,
    missingText: item.message,
    reasonText: '',
    missing: item,
  }))

  const rejectedItems: AiRuleResultViewModel[] =
    draft.verdict === 'rejected'
      ? [
          {
            id: `rejected-${draft.draft_id ?? draft.created_at ?? 'current'}`,
            status: 'rejected' as const,
            title: draft.reasoning_summary || '当前规则不可添加',
            ruleTypeLabel: getAiRuleTypeLabel(draft.rule_type),
            sourceLabel: '-',
            sheetLabel: '-',
            fieldLabel: '-',
            variableLabel: '-',
            groupLabel: 'AI生成规则组',
            metaText: `规则类型 ${getAiRuleTypeLabel(draft.rule_type)}`,
            missingText: draft.missing.map((item) => item.message).join('；'),
            reasonText: [
              draft.rejection_reason || '当前支持的规则类型无法表达该需求。',
              ...(draft.extension_suggestions ?? []).map((item) => `扩展建议：${item}`),
            ].join('；'),
          },
        ]
      : []

  if (draft.verdict === 'needs_input' && !missingItems.length) {
    missingItems.push({
      id: `needs-input-${draft.draft_id ?? 'current'}`,
      status: 'needs_input',
      title: draft.reasoning_summary || '需要补充规则线索',
      ruleTypeLabel: getAiRuleTypeLabel(draft.rule_type),
      sourceLabel: '-',
      sheetLabel: '-',
      fieldLabel: '-',
      variableLabel: '-',
      groupLabel: 'AI生成规则组',
      metaText: `规则类型 ${getAiRuleTypeLabel(draft.rule_type)}`,
      missingText: '请补充数据源、Sheet、列名或规则参数后重新校验。',
      reasonText: '',
    })
  }

  return [...readyItems, ...missingItems, ...rejectedItems]
}

export function buildAiResultSummary(draft: AiRuleDraft | null): AiResultSummaryViewModel {
  const items = mapAiDraftToResultItems(draft)
  const ready = items.filter((item) => item.status === 'ready').length
  const needsInput = items.filter((item) => item.status === 'needs_input').length
  const rejected = items.filter((item) => item.status === 'rejected').length
  const applied = items.filter((item) => item.status === 'applied').length
  const total = items.length
  const label =
    rejected && !ready && !applied
      ? '不可添加'
      : needsInput || rejected
      ? '部分可添加'
      : applied
      ? '已应用'
      : ready
      ? '可添加'
      : '待校验'
  const tone =
    rejected && !ready && !applied
      ? 'danger'
      : needsInput || rejected
      ? 'warning'
      : ready || applied
      ? 'success'
      : 'neutral'

  return {
    total,
    ready,
    needsInput,
    rejected,
    applied,
    label,
    tone,
    text: `共识别 ${total} 条规则：${ready} 条可添加，${needsInput} 条需补充，${rejected} 条不可添加`,
  }
}

export function buildPendingConfigPreview(draft: AiRuleDraft | null): PendingConfigPreviewViewModel {
  if (!draft || draft.verdict === 'rejected') {
    return { sources: [], variables: [], rules: [] }
  }

  return {
    sources: [
      ...draft.draft.sources_to_add.map((source) => `新增 ${source.id}`),
      ...(draft.draft.sources_to_add.length ? [] : ['复用当前数据源']),
    ],
    variables: [
      ...draft.draft.variables_to_add.map((variable) => `新增 ${variable.tag}`),
      ...draft.draft.reuse_variable_tags.map((tag) => `复用 ${tag}`),
    ],
    rules: draft.draft.rules_to_add.map((rule) => `新增 ${rule.rule_name || rule.rule_id}`),
  }
}

function formatHistoryTime(value?: string | null): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const now = new Date()
  const sameDay = date.toDateString() === now.toDateString()
  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  const time = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  if (sameDay) return `今天 ${time}`
  if (date.toDateString() === yesterday.toDateString()) return `昨天 ${time}`
  return date.toLocaleString()
}

export function mapDraftToHistoryViewModel(draft: AiRuleDraft): DraftHistoryViewModel {
  const status = normalizeRuleStatus(draft)
  const title =
    draft.draft.rules_to_add[0]?.rule_name ||
    draft.reasoning_summary ||
    (draft.verdict === 'rejected' ? '不可添加规则草稿' : 'AI 规则草稿')
  return {
    id: String(draft.draft_id ?? `${draft.created_at}-${title}`),
    title,
    ruleCount: draft.draft.rules_to_add.length,
    timeLabel: formatHistoryTime(draft.created_at),
    status,
    statusLabel: getStatusLabel(status),
    draft,
  }
}

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CircleCheck, MagicStick, Refresh, VideoPlay } from '@element-plus/icons-vue'

import AiRuleResultList from './AiRuleResultList.vue'
import DraftHistoryPanel from './DraftHistoryPanel.vue'
import PendingConfigPreview from './PendingConfigPreview.vue'
import SmartRuleInputCard from './SmartRuleInputCard.vue'
import type { SmartRuleWorkflowHintsState } from './SmartRuleHintsPanel.vue'
import PrimaryButton from '../shell/PrimaryButton.vue'
import SecondaryButton from '../shell/SecondaryButton.vue'
import { useAiStore } from '../../store/ai'
import { useWorkbenchStore } from '../../store/workbench'
import type {
  AiMissingItem,
  AiRuleDraft,
  AiRuleDraftPayload,
  AiRuleWorkflowHints,
} from '../../types/ai'
import type { AbnormalResult, ExecutionResponse } from '../../types/api'
import type { FixedRuleDefinition } from '../../types/fixedRules'
import type { VariableTag } from '../../types/workbench'
import {
  buildPendingConfigPreview,
  getAiRuleTypeLabel,
  mapAiDraftToResultItems,
  mapDraftToHistoryViewModel,
  markAiRuleResultDuplicate,
  type AiResultSummaryViewModel,
  type AiRuleResultViewModel,
} from '../../utils/aiRuleViewModel'
import {
  applyAiRuleTemplate,
  getAvailableAiRuleTemplates,
  getRecommendedAiRuleTemplates,
} from '../../utils/aiRuleTemplates'
import { buildAiPreviewExplanation } from '../../utils/aiPreviewExplanation'
import { extractSmartRuleWorkflowHints } from '../../utils/aiRuleHintExtractor'
import { getFixedRuleDuplicateSet } from '../../utils/ruleFingerprint'

const emit = defineEmits<{
  (e: 'applied', ruleIds: string[]): void
  (e: 'applied-and-execute', ruleIds: string[]): void
  (e: 'open-source-prefill', prefill: Record<string, unknown>): void
  (e: 'open-single-variable-prefill', prefill: Record<string, unknown>): void
  (e: 'open-composite-variable-prefill', prefill: Record<string, unknown>): void
}>()

const AI_RULE_GROUP_NAME = 'AI生成规则组'
const DESCRIPTION_MAX_LENGTH = 800
const AUTO_FILL_DELAY_MS = 350
const BUSINESS_RULE_EXAMPLE =
  '校验规则筛选DESC3=升级p1建筑到p2级p4次,完成p2等级的p1科研，两种类型。STR_ABSwitch字段=GreenServer:0 or SLG2:0。'

const COMMON_WORKFLOW_PROMPT = `你是 Excel Check 项目的规则工作流 Agent。你的任务是把用户的自然语言导表检查需求，转换成当前系统可执行的个人校验配置，并严格按“先校验、后确认、再添加”的流程执行。

## 固定流程

1. 收集输入
用户至少需要提供：
- 配置表来源：SVN 链接或已存在数据源标识
- 工作表 sheet 名称
- 目标字段
- 规则描述
- 可选过滤条件
- 可选合法示例 / 非法示例
- 可选是否允许空值

如果缺少关键输入，不要编造，直接返回缺失项。

2. 读取并探测数据
必须先读取真实文件，确认：
- 数据源是否可访问
- sheet 是否存在
- 字段是否存在
- 总行数
- 目标字段样例
- 过滤字段样例
- 是否存在重复 key，必要时建议启用 append_index_to_key

3. 解析用户规则
从用户描述中提取：
- target_field：被校验字段
- filter_conditions：过滤条件
- assertion：校验断言
- legal_examples：合法示例
- invalid_examples：非法示例
- empty_policy：空值允许 / 不允许 / 未说明
- expected_result：期望异常含义

4. 匹配当前系统能力
优先映射到现有规则类型：
- 单字段非空：not_null
- 单字段唯一：unique
- 单字段固定值比较：fixed_value_compare
- 单字段正则：regex_check
- 单字段顺序 / 连续性：sequence_order_check
- 字段包含字典：cross_table_mapping
- 带过滤条件的字段校验：composite_condition_check
- 跨组合变量比较：dual_composite_compare
- 多节点串行：multi_composite_pipeline_check
- 多组映射：multi_composite_mapping_check

如果规则需要“按另一个字段过滤后再校验目标字段”，必须优先使用 composite_condition_check，不要降级成单字段 regex_check。
如果规则描述为“筛选 A=1 和 A=2，以 B 为 key，判断 C/D 是否相等”，必须优先使用 dual_composite_compare，并把 A 放入左右筛选、B 放入左右关联 Key、C/D 放入比较字段。

5. 生成候选规则
生成当前系统可保存的结构：
- data_source
- variable
- rule
- rule_type
- filters
- assertions
- display_field
- rule_name
- reason

要求：
- 不修改后端协议
- 不新增系统不存在的规则类型
- 不把无法表达的需求硬塞进现有规则
- 规则名称要清晰，能体现 sheet、字段和校验目的

6. 先执行预校验
在保存到个人校验前，先用候选配置执行一次校验，返回：
- 是否执行成功
- 扫描行数
- 过滤掉的行数或过滤条件说明
- 异常总数
- 异常样例，至少包含行号、原始值、说明、展示字段
- 规则是否符合用户描述

7. 判断是否可添加
如果当前系统能力足够表达规则，返回：
- can_add_rule: true
- 待添加规则摘要
- 预校验结果
- 等待用户确认是否添加

如果当前系统能力不足，返回：
- can_add_rule: false
- 不能添加的原因
- 缺失的功能点
- 建议的系统改造方向
- 可以临时替代的规则方案，如果存在

8. 用户确认后添加规则
只有用户明确确认后，才把规则写入个人校验配置。
添加时必须幂等：
- 数据源已存在则复用或更新
- 变量已存在则复用或更新
- 规则已存在则更新，不重复创建
- 不清空用户已有配置

9. 添加后复跑
添加完成后，再执行一次该规则，返回最终结果：
- 保存是否成功
- result_id
- 扫描行数
- 异常数量
- 异常明细摘要
- 用户下一步可以在个人校验页执行或导出结果

## 输出格式

请始终按以下结构输出：

### 规则理解
- 数据源：
- Sheet：
- 目标字段：
- 过滤条件：
- 校验目标：
- 空值策略：
- 合法示例：
- 当前能力匹配：

### 候选配置
- 数据源：
- 变量：
- 规则类型：
- 规则名称：
- 过滤条件：
- 校验条件：
- 展示字段：

### 预校验结果
- 是否成功：
- 扫描行数：
- 异常数量：
- 异常样例：

### 添加判断
- can_add_rule:
- reason:
- missing_capabilities:

### 等待确认
如果 can_add_rule=true，询问用户是否确认添加到个人校验。
如果 can_add_rule=false，说明为什么不能添加，以及需要补什么功能。

## 严格约束

- 不能在未读取真实表结构前直接生成最终规则。
- 不能在未预校验前直接写入个人校验。
- 不能在用户未确认前保存规则。
- 不能伪造执行结果。
- 不能把当前系统不支持的能力说成已支持。
- 如果规则需要过滤条件，优先使用组合分支校验。
- 如果单字段 regex 无法表达过滤逻辑，必须说明原因。`

const router = useRouter()
const aiStore = useAiStore()
const workbenchStore = useWorkbenchStore()

const description = ref('')
const extraHints = ref('')
const selectedVariableTags = ref<string[]>([])
const isApplying = ref(false)
const previewResult = ref<ExecutionResponse | null>(null)
const previewError = ref('')
const isPreviewing = ref(false)
const isAutoCompletingAndApplying = ref(false)
const isRegeneratingWithPreviewAdvice = ref(false)
const configDrawerVisible = ref(false)
const configDrawerItem = ref<AiRuleResultViewModel | null>(null)
const selectedApplyGroupId = ref('')
const allowAutoComplete = ref(false)

const workflowHints = reactive<SmartRuleWorkflowHintsState>({
  ruleTypeHint: '',
  targetVariableTag: '',
  referenceVariableTag: '',
  leftVariableTag: '',
  rightVariableTag: '',
  sourceId: '',
  sourceUrl: '',
  sheet: '',
  targetField: '',
  ruleGroupName: AI_RULE_GROUP_NAME,
  filterField: '',
  filterOperator: '',
  filterValue: '',
  assertionField: '',
  assertionOperator: '',
  assertionValue: '',
  operator: '',
  expectedValue: '',
  expectedValueMode: '',
  displayField: '',
  regexPattern: '',
  sequenceDirection: '',
  sequenceStep: '',
  sequenceStartMode: '',
  sequenceStartValue: '',
  keyColumn: '',
  compositeColumns: '',
  leftFilterField: '',
  leftFilterOperator: '',
  leftFilterValue: '',
  rightFilterField: '',
  rightFilterOperator: '',
  rightFilterValue: '',
  leftKeyField: '',
  rightKeyField: '',
  compareFields: '',
})
const templateWorkflowHints = ref<AiRuleWorkflowHints>({})

type SmartRuleHintKey = keyof SmartRuleWorkflowHintsState

const manuallyEditedHintKeys = new Set<SmartRuleHintKey>()
let autoFillTimer: ReturnType<typeof setTimeout> | null = null

const currentDraft = computed(() => aiStore.currentDraft)
const promptOptimizeResult = computed(() => aiStore.promptOptimizeResult)
const isConfigured = computed(() => aiStore.isConfigured)
const hasRuleDescription = computed(() => description.value.trim().length >= 4)
const canGenerate = computed(
  () =>
    isConfigured.value &&
    hasRuleDescription.value &&
    (allowAutoComplete.value || selectedVariableTags.value.length > 0),
)
const duplicateRuleIds = computed(() => {
  if (!currentDraft.value?.draft.rules_to_add.length) {
    return new Set<string>()
  }
  return getFixedRuleDuplicateSet(
    workbenchStore.orchestrationRules,
    currentDraft.value.draft.rules_to_add,
  )
})
const addableDraftRules = computed(
  () => currentDraft.value?.draft.rules_to_add.filter((rule) => !duplicateRuleIds.value.has(rule.rule_id)) ?? [],
)
const duplicateReadyRuleCount = computed(() => duplicateRuleIds.value.size)
const resultItems = computed(() =>
  mapAiDraftToResultItems(currentDraft.value).map((item) => {
    if (item.status !== 'ready' || !item.rule || !duplicateRuleIds.value.has(item.rule.rule_id)) {
      return item
    }
    return markAiRuleResultDuplicate(item)
  }),
)
const resultSummary = computed(() => buildAiResultSummaryFromItems(resultItems.value))
const pendingPreview = computed(() => buildPendingConfigPreview(currentDraft.value))
const historyItems = computed(() => aiStore.drafts.map(mapDraftToHistoryViewModel))
const applyGroupOptions = computed(() => workbenchStore.allRuleGroups)
const selectedTemplateVariables = computed(() => {
  const variablesByTag = new Map(workbenchStore.variables.map((variable) => [variable.tag, variable]))
  return selectedVariableTags.value
    .map((tag) => variablesByTag.get(tag))
    .filter((variable): variable is VariableTag => Boolean(variable))
})
const availableAiRuleTemplates = computed(() =>
  getAvailableAiRuleTemplates({
    selectedVariables: selectedTemplateVariables.value,
    allowAutoComplete: allowAutoComplete.value,
  }),
)
const recommendedAiRuleTemplates = computed(() =>
  getRecommendedAiRuleTemplates(selectedTemplateVariables.value),
)
const providerLabel = computed(() => {
  if (!aiStore.provider) return '未配置'
  return `${getProviderPresetLabel(aiStore.provider.provider_preset)} / ${aiStore.provider.model}`
})
const previewRows = computed<AbnormalResult[]>(() => {
  const data = previewResult.value?.data
  return data?.list ?? data?.abnormal_results ?? []
})
const previewTotal = computed(() => previewResult.value?.data.total ?? previewRows.value.length)
const previewFailedSources = computed(() => previewResult.value?.meta.failed_sources ?? [])
const previewExplanation = computed(() => buildAiPreviewExplanation(previewResult.value))
const isPreviewSuccessful = computed(
  () => Boolean(previewResult.value) && !previewError.value && previewFailedSources.value.length === 0,
)
const hasReadyRules = computed(
  () =>
    currentDraft.value?.verdict === 'ready' &&
    !currentDraft.value.applied &&
    Boolean(currentDraft.value.draft.rules_to_add.length),
)
const canApplyDraft = computed(
  () =>
    hasReadyRules.value &&
    isPreviewSuccessful.value &&
    addableDraftRules.value.length > 0 &&
    !isApplying.value,
)
const canAutoCompleteAndApply = computed(
  () =>
    allowAutoComplete.value &&
    currentDraft.value?.verdict === 'needs_input' &&
    canGenerate.value &&
    !aiStore.isDraftGenerating &&
    !isPreviewing.value &&
    !isApplying.value &&
    !isAutoCompletingAndApplying.value,
)
const canRegenerateWithPreviewAdvice = computed(
  () =>
    previewExplanation.value.canRegenerate &&
    currentDraft.value?.verdict === 'ready' &&
    !currentDraft.value.applied &&
    canGenerate.value &&
    !aiStore.isDraftGenerating &&
    !isPreviewing.value &&
    !isApplying.value &&
    !isAutoCompletingAndApplying.value &&
    !isRegeneratingWithPreviewAdvice.value,
)
const configDrawerPayload = computed(() => {
  const rule = configDrawerItem.value?.rule
  if (!rule || !currentDraft.value) return ''
  const variables = collectVariablesForRule(rule, currentDraft.value.draft)
  const sourceIds = new Set(variables.map((variable) => variable.source_id))
  const sources = currentDraft.value.draft.sources_to_add.filter((source) => sourceIds.has(source.id))
  return JSON.stringify({ sources, variables, rule }, null, 2)
})

onMounted(async () => {
  await Promise.all([aiStore.loadProvider(), aiStore.loadDrafts()])
})

onBeforeUnmount(() => {
  clearAutoFillTimer()
})

watch(description, () => {
  resetPreview()
  scheduleDescriptionHintAutoFill()
})

function getProviderPresetLabel(preset: string): string {
  const labels: Record<string, string> = {
    openai: 'OpenAI',
    anthropic: 'Anthropic Claude',
    gemini: 'Google Gemini',
    deepseek: 'DeepSeek',
    qwen: '通义千问',
    kimi: 'Kimi',
    zhipu: '智谱 GLM',
    openrouter: 'OpenRouter',
    custom_openai: '自定义',
  }
  return labels[preset] ?? preset
}

function buildAiResultSummaryFromItems(items: AiRuleResultViewModel[]): AiResultSummaryViewModel {
  const ready = items.filter((item) => item.status === 'ready').length
  const duplicate = items.filter((item) => item.status === 'duplicate').length
  const needsInput = items.filter((item) => item.status === 'needs_input').length
  const rejected = items.filter((item) => item.status === 'rejected').length
  const applied = items.filter((item) => item.status === 'applied').length
  const total = items.length
  const label =
    rejected && !ready && !applied
      ? '不可添加'
      : needsInput || rejected
        ? '部分可添加'
        : ready
          ? '可添加'
          : duplicate
            ? '已有规则'
            : applied
              ? '已应用'
              : '待校验'
  const tone =
    rejected && !ready && !applied
      ? 'danger'
      : needsInput || rejected
        ? 'warning'
        : ready || applied
          ? 'success'
          : duplicate
            ? 'primary'
            : 'neutral'

  return {
    total,
    ready,
    needsInput,
    rejected,
    applied,
    label,
    tone,
    text: `共识别 ${total} 条规则：${ready} 条可添加，${duplicate} 条已有，${needsInput} 条需补充，${rejected} 条不可添加`,
  }
}

function resetPreview(): void {
  previewResult.value = null
  previewError.value = ''
}

function clearAutoFillTimer(): void {
  if (autoFillTimer !== null) {
    clearTimeout(autoFillTimer)
    autoFillTimer = null
  }
}

function scheduleDescriptionHintAutoFill(): void {
  clearAutoFillTimer()
  if (!description.value.trim()) {
    return
  }
  autoFillTimer = setTimeout(() => {
    autoFillTimer = null
    applyDescriptionHints()
  }, AUTO_FILL_DELAY_MS)
}

function applyDescriptionHints(): void {
  const extracted = extractSmartRuleWorkflowHints(description.value)
  const extractedRecord = extracted as Partial<Record<SmartRuleHintKey, string>>
  let changed = false
  const autoResetKeys = new Set<SmartRuleHintKey>([
    'ruleTypeHint',
    'targetVariableTag',
    'referenceVariableTag',
    'leftVariableTag',
    'rightVariableTag',
    'sourceId',
    'sourceUrl',
    'sheet',
    'targetField',
    'filterField',
    'filterOperator',
    'filterValue',
    'assertionField',
    'assertionOperator',
    'assertionValue',
    'operator',
    'expectedValue',
    'expectedValueMode',
    'displayField',
    'regexPattern',
    'sequenceDirection',
    'sequenceStep',
    'sequenceStartMode',
    'sequenceStartValue',
    'keyColumn',
    'compositeColumns',
    'leftFilterField',
    'leftFilterOperator',
    'leftFilterValue',
    'rightFilterField',
    'rightFilterOperator',
    'rightFilterValue',
    'leftKeyField',
    'rightKeyField',
    'compareFields',
  ])
  autoResetKeys.forEach((key) => {
    if (manuallyEditedHintKeys.has(key)) return
    const nextValue = String(extractedRecord[key] ?? '')
    if (workflowHints[key] && workflowHints[key] !== nextValue) {
      workflowHints[key] = nextValue
      changed = true
    }
  })
  ;(Object.entries(extracted) as Array<[SmartRuleHintKey, string]>).forEach(([key, value]) => {
    if (!value || manuallyEditedHintKeys.has(key)) {
      return
    }
    if (workflowHints[key] !== value) {
      workflowHints[key] = value
      changed = true
    }
  })
  if (changed) {
    syncRoleHintsFromSelectedVariables()
    resetPreview()
  }
}

function updateSelectedVariableTags(value: string[]): void {
  selectedVariableTags.value = Array.from(new Set(value.map((item) => item.trim()).filter(Boolean)))
  templateWorkflowHints.value = {}
  syncRoleHintsFromSelectedVariables()
  resetPreview()
}

function updateAllowAutoComplete(value: boolean): void {
  allowAutoComplete.value = value
  aiStore.clearPromptOptimizeResult()
  resetPreview()
}

function syncRoleHintsFromSelectedVariables(): void {
  const [firstTag = '', secondTag = ''] = selectedVariableTags.value
  workflowHints.targetVariableTag = firstTag
  workflowHints.leftVariableTag = firstTag
  workflowHints.referenceVariableTag = secondTag
  workflowHints.rightVariableTag = secondTag
}

function buildStructuredHintsText(): string {
  const variableMode = allowAutoComplete.value
    ? '允许 AI 自动补齐数据源和变量，已选变量仅作为优先上下文'
    : '仅使用已选变量池变量'
  const lines = [
    '输入模式：目标变量 + 规则描述',
    `变量来源：${variableMode}`,
    selectedVariableTags.value.length ? `已选变量：${selectedVariableTags.value.join(',')}` : '',
    workflowHints.targetVariableTag ? `目标变量：${workflowHints.targetVariableTag}` : '',
    workflowHints.referenceVariableTag ? `引用变量：${workflowHints.referenceVariableTag}` : '',
    workflowHints.leftVariableTag ? `左侧变量：${workflowHints.leftVariableTag}` : '',
    workflowHints.rightVariableTag ? `右侧变量：${workflowHints.rightVariableTag}` : '',
    workflowHints.ruleGroupName ? `规则组：${workflowHints.ruleGroupName}` : '',
  ].filter(Boolean)
  return lines.join('\n')
}

function buildExtraHintsPayload(adjustmentHints = ''): string | undefined {
  const structuredHints = buildStructuredHintsText()
  const merged = [extraHints.value.trim(), adjustmentHints.trim(), structuredHints]
    .filter(Boolean)
    .join('\n\n')
  return merged || undefined
}

function buildDescriptionPayload(): string {
  const rawDescription = description.value.trim()
  if (rawDescription) return rawDescription
  const structuredHints = buildStructuredHintsText()
  return structuredHints || '按结构化表单生成个人校验规则。'
}

function buildWorkflowHintsPayload(): AiRuleWorkflowHints {
  const payload: AiRuleWorkflowHints = cloneWorkflowHints(templateWorkflowHints.value)
  const putText = (key: keyof AiRuleWorkflowHints, value: string): void => {
    const trimmed = value.trim()
    if (trimmed) {
      ;(payload as Record<string, unknown>)[key] = trimmed
    }
  }
  const putKeyText = (key: keyof AiRuleWorkflowHints, value: string): void => {
    if (!isPlaceholderKeyColumn(value)) {
      putText(key, value)
    }
  }
  const putList = (
    key: keyof AiRuleWorkflowHints,
    value: string,
    options: { dropPlaceholderKey?: boolean } = {},
  ): void => {
    const items = value
      .replaceAll('，', ',')
      .split(',')
      .map((item) => item.trim())
      .filter((item) => item && !(options.dropPlaceholderKey && isPlaceholderKeyColumn(item)))
    if (items.length) {
      ;(payload as Record<string, unknown>)[key] = Array.from(new Set(items))
    }
  }

  putText('rule_type_hint', workflowHints.ruleTypeHint)
  putText('target_variable_tag', workflowHints.targetVariableTag || selectedVariableTags.value[0] || '')
  putText('left_variable_tag', workflowHints.leftVariableTag || selectedVariableTags.value[0] || '')
  putText('reference_variable_tag', workflowHints.referenceVariableTag || selectedVariableTags.value[1] || '')
  putText('right_variable_tag', workflowHints.rightVariableTag || selectedVariableTags.value[1] || '')
  putText('source_id', workflowHints.sourceId)
  putText('source_url', workflowHints.sourceUrl)
  putText('sheet', workflowHints.sheet)
  putText('target_field', workflowHints.targetField)
  putText('display_field', workflowHints.displayField)
  putText('filter_field', workflowHints.filterField)
  putText('filter_value', workflowHints.filterValue)
  putText('assertion_field', workflowHints.assertionField)
  putText('assertion_value', workflowHints.assertionValue)
  putText('operator', workflowHints.operator)
  putText('expected_value', workflowHints.expectedValue)
  putText('regex_pattern', workflowHints.regexPattern)
  putText('sequence_step', workflowHints.sequenceStep)
  putText('sequence_start_value', workflowHints.sequenceStartValue)
  putKeyText('key_column', workflowHints.keyColumn)
  putText('left_filter_field', workflowHints.leftFilterField)
  putText('left_filter_value', workflowHints.leftFilterValue)
  putText('right_filter_field', workflowHints.rightFilterField)
  putText('right_filter_value', workflowHints.rightFilterValue)
  putKeyText('left_key_field', workflowHints.leftKeyField)
  putKeyText('right_key_field', workflowHints.rightKeyField)
  putList('composite_columns', workflowHints.compositeColumns, { dropPlaceholderKey: true })
  putList('compare_fields', workflowHints.compareFields)

  if (workflowHints.sourceUrl.trim().match(/^(https?:|svn:)/i)) {
    payload.source_type = 'svn'
  }
  if (workflowHints.filterOperator.trim()) {
    payload.filter_operator = workflowHints.filterOperator as AiRuleWorkflowHints['filter_operator']
  }
  if (workflowHints.assertionOperator.trim()) {
    payload.assertion_operator = workflowHints.assertionOperator as AiRuleWorkflowHints['assertion_operator']
  }
  if (workflowHints.expectedValueMode.trim()) {
    payload.expected_value_mode = workflowHints.expectedValueMode as AiRuleWorkflowHints['expected_value_mode']
  }
  if (workflowHints.sequenceDirection.trim()) {
    payload.sequence_direction = workflowHints.sequenceDirection as AiRuleWorkflowHints['sequence_direction']
  }
  if (workflowHints.sequenceStartMode.trim()) {
    payload.sequence_start_mode = workflowHints.sequenceStartMode as AiRuleWorkflowHints['sequence_start_mode']
  }
  if (workflowHints.leftFilterOperator.trim()) {
    payload.left_filter_operator = workflowHints.leftFilterOperator as AiRuleWorkflowHints['left_filter_operator']
  }
  if (workflowHints.rightFilterOperator.trim()) {
    payload.right_filter_operator = workflowHints.rightFilterOperator as AiRuleWorkflowHints['right_filter_operator']
  }
  return payload
}

function cloneWorkflowHints(hints: AiRuleWorkflowHints): AiRuleWorkflowHints {
  return JSON.parse(JSON.stringify(hints)) as AiRuleWorkflowHints
}

function isPlaceholderKeyColumn(value?: string): boolean {
  if (!value?.trim()) return false
  if (value.includes('未识别') || value.includes('需要用户确认')) return true
  const compact = value.replace(/[\s:：=为是列字段、，。；;]/g, '').toLowerCase()
  return ['key', '关联key', '业务key', '比对key', '对齐key', '主键', '唯一键', '索引'].includes(compact)
}

function cloneRule(rule: FixedRuleDefinition): FixedRuleDefinition {
  return JSON.parse(JSON.stringify(rule)) as FixedRuleDefinition
}

function collectVariablesForRule(rule: FixedRuleDefinition, draft: AiRuleDraftPayload): VariableTag[] {
  const tags = new Set<string>()
  if (rule.target_variable_tag?.trim()) tags.add(rule.target_variable_tag.trim())
  if (rule.reference_variable_tag?.trim()) tags.add(rule.reference_variable_tag.trim())
  rule.pipeline_config?.nodes.forEach((node) => {
    if (node.variable_tag.trim()) tags.add(node.variable_tag.trim())
  })
  rule.mapping_config?.nodes.forEach((node) => {
    if (node.variable_tag.trim()) tags.add(node.variable_tag.trim())
  })
  return draft.variables_to_add.filter((variable) => tags.has(variable.tag))
}

function buildDraftPayloadForWorkflow(
  draft: AiRuleDraft,
  options?: { rule?: FixedRuleDefinition; rules?: FixedRuleDefinition[]; ensureGroup?: boolean },
): AiRuleDraftPayload {
  const displayField = workflowHints.displayField.trim()
  const groupName = workflowHints.ruleGroupName.trim() || AI_RULE_GROUP_NAME
  const selectedGroupId = applyGroupOptions.value.some(
    (group) => group.group_id === selectedApplyGroupId.value,
  )
    ? selectedApplyGroupId.value
    : ''
  const groupId = options?.ensureGroup
    ? selectedGroupId || workbenchStore.ensureOrchestrationGroupByName(groupName)
    : groupName
  const rules = options?.rules ?? (options?.rule ? [options.rule] : draft.draft.rules_to_add)
  return {
    sources_to_add: draft.draft.sources_to_add.map((source) => ({ ...source })),
    variables_to_add: draft.draft.variables_to_add.map((variable) => ({ ...variable })),
    reuse_variable_tags: [...draft.draft.reuse_variable_tags],
    rules_to_add: rules.map((rule) => ({
      ...cloneRule(rule),
      group_id: groupId,
      display_field: rule.display_field || displayField || undefined,
    })),
  }
}

function loadBusinessRuleExample(): void {
  clearAutoFillTimer()
  manuallyEditedHintKeys.clear()
  templateWorkflowHints.value = {}
  description.value = BUSINESS_RULE_EXAMPLE
  Object.assign(workflowHints, {
    ruleTypeHint: '',
    targetVariableTag: selectedVariableTags.value[0] ?? '',
    referenceVariableTag: '',
    leftVariableTag: selectedVariableTags.value[0] ?? '',
    rightVariableTag: '',
    sourceId: '',
    sourceUrl: '',
    sheet: '',
    targetField: '',
    ruleGroupName: AI_RULE_GROUP_NAME,
    filterField: '',
    filterOperator: '',
    filterValue: '',
    assertionField: '',
    assertionOperator: '',
    assertionValue: '',
    operator: '',
    expectedValue: '',
    expectedValueMode: '',
    displayField: '',
    regexPattern: '',
    sequenceDirection: '',
    sequenceStep: '',
    sequenceStartMode: '',
    sequenceStartValue: '',
    keyColumn: '',
    compositeColumns: '',
    leftFilterField: '',
    leftFilterOperator: '',
    leftFilterValue: '',
    rightFilterField: '',
    rightFilterOperator: '',
    rightFilterValue: '',
    leftKeyField: '',
    rightKeyField: '',
    compareFields: '',
  })
  extraHints.value = ''
  applyDescriptionHints()
  syncRoleHintsFromSelectedVariables()
  resetPreview()
  ElMessage.success('已载入规则描述示例，请选择变量池变量后校验。')
}

function handleApplyRuleTemplate(templateId: string): void {
  try {
    clearAutoFillTimer()
    manuallyEditedHintKeys.clear()
    const result = applyAiRuleTemplate(
      templateId,
      [...recommendedAiRuleTemplates.value, ...availableAiRuleTemplates.value],
      selectedTemplateVariables.value,
    )
    description.value = result.description
    templateWorkflowHints.value = cloneWorkflowHints(result.workflowHints)
    applyTemplateWorkflowHints(result.workflowHints)
    if (result.allowAutoComplete) {
      allowAutoComplete.value = true
    }
    extraHints.value = ''
    aiStore.clearPromptOptimizeResult()
    aiStore.clearCurrentDraft()
    resetPreview()
    ElMessage.success('已载入规则模板，请确认描述后再 AI 校验。')
  } catch (error) {
    ElMessage.warning(error instanceof Error ? error.message : '载入规则模板失败。')
  }
}

function applyTemplateWorkflowHints(hints: AiRuleWorkflowHints): void {
  setWorkflowHint('ruleTypeHint', hints.rule_type_hint)
  setWorkflowHint('targetVariableTag', hints.target_variable_tag)
  setWorkflowHint('referenceVariableTag', hints.reference_variable_tag)
  setWorkflowHint('leftVariableTag', hints.left_variable_tag)
  setWorkflowHint('rightVariableTag', hints.right_variable_tag)
  setWorkflowHint('sourceId', hints.source_id)
  setWorkflowHint('sourceUrl', hints.source_url)
  setWorkflowHint('sheet', hints.sheet)
  setWorkflowHint('targetField', hints.target_field)
  setWorkflowHint('displayField', hints.display_field)
  setWorkflowHint('filterField', hints.filter_field)
  setWorkflowHint('filterOperator', hints.filter_operator)
  setWorkflowHint('filterValue', hints.filter_value)
  setWorkflowHint('assertionField', hints.assertion_field)
  setWorkflowHint('assertionOperator', hints.assertion_operator)
  setWorkflowHint('assertionValue', hints.assertion_value)
  setWorkflowHint('operator', hints.operator)
  setWorkflowHint('expectedValue', hints.expected_value)
  setWorkflowHint('expectedValueMode', hints.expected_value_mode)
  setWorkflowHint('regexPattern', hints.regex_pattern)
  setWorkflowHint('sequenceDirection', hints.sequence_direction)
  setWorkflowHint('sequenceStep', hints.sequence_step)
  setWorkflowHint('sequenceStartMode', hints.sequence_start_mode)
  setWorkflowHint('sequenceStartValue', hints.sequence_start_value)
  setWorkflowHint('keyColumn', hints.key_column)
  setWorkflowHint('compositeColumns', hints.composite_columns)
  setWorkflowHint('leftFilterField', hints.left_filter_field)
  setWorkflowHint('leftFilterOperator', hints.left_filter_operator)
  setWorkflowHint('leftFilterValue', hints.left_filter_value)
  setWorkflowHint('rightFilterField', hints.right_filter_field)
  setWorkflowHint('rightFilterOperator', hints.right_filter_operator)
  setWorkflowHint('rightFilterValue', hints.right_filter_value)
  setWorkflowHint('leftKeyField', hints.left_key_field)
  setWorkflowHint('rightKeyField', hints.right_key_field)
  setWorkflowHint('compareFields', hints.compare_fields)
}

function setWorkflowHint(key: SmartRuleHintKey, value: string | string[] | null | undefined): void {
  if (Array.isArray(value)) {
    workflowHints[key] = value.join(',')
    return
  }
  workflowHints[key] = value ?? ''
}

function clearInput(): void {
  clearAutoFillTimer()
  manuallyEditedHintKeys.clear()
  aiStore.clearPromptOptimizeResult()
  templateWorkflowHints.value = {}
  description.value = ''
  extraHints.value = ''
  selectedVariableTags.value = []
  Object.assign(workflowHints, {
    ruleTypeHint: '',
    targetVariableTag: '',
    referenceVariableTag: '',
    leftVariableTag: '',
    rightVariableTag: '',
    sourceId: '',
    sourceUrl: '',
    sheet: '',
    targetField: '',
    ruleGroupName: AI_RULE_GROUP_NAME,
    filterField: '',
    filterOperator: '',
    filterValue: '',
    assertionField: '',
    assertionOperator: '',
    assertionValue: '',
    operator: '',
    expectedValue: '',
    expectedValueMode: '',
    displayField: '',
    regexPattern: '',
    sequenceDirection: '',
    sequenceStep: '',
    sequenceStartMode: '',
    sequenceStartValue: '',
    keyColumn: '',
    compositeColumns: '',
    leftFilterField: '',
    leftFilterOperator: '',
    leftFilterValue: '',
    rightFilterField: '',
    rightFilterOperator: '',
    rightFilterValue: '',
    leftKeyField: '',
    rightKeyField: '',
    compareFields: '',
  })
  resetPreview()
}

async function copyWorkflowPrompt(): Promise<void> {
  try {
    await globalThis.navigator.clipboard.writeText(COMMON_WORKFLOW_PROMPT)
    ElMessage.success('通用提示词已复制。')
  } catch {
    ElMessage.warning('当前浏览器不支持自动复制，请手动选择提示词。')
  }
}

async function optimizePrompt(): Promise<void> {
  if (!allowAutoComplete.value && !selectedVariableTags.value.length) {
    ElMessage.warning('请先选择一个或多个目标变量。')
    return
  }
  if (!description.value.trim()) {
    ElMessage.warning('请先输入规则描述。')
    return
  }

  clearAutoFillTimer()
  syncRoleHintsFromSelectedVariables()
  try {
    const result = await aiStore.optimizePrompt({
      raw_description: description.value.trim(),
      selected_variable_tags: selectedVariableTags.value,
      allow_auto_complete: allowAutoComplete.value,
      context: {
        page: 'personal_workbench',
        mode: 'smart_rule',
      },
    })
    if (result.status === 'optimized') {
      ElMessage.success('已生成更适合解析的规则描述，请确认后替换原文或继续编辑。')
    } else if (result.status === 'needs_input') {
      ElMessage.warning(result.missing[0] || '请补充规则描述或目标变量后重试。')
    } else {
      ElMessage.warning('暂时无法优化该描述，请补充目标字段、筛选条件、Key 字段或判断关系后重试。')
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '优化规则描述失败。')
  }
}

function applyOptimizedDescription(): void {
  const optimizedDescription = promptOptimizeResult.value?.optimized_description.trim()
  if (!optimizedDescription) {
    ElMessage.warning('当前没有可替换的优化描述。')
    return
  }
  clearAutoFillTimer()
  description.value = optimizedDescription
  applyDescriptionHints()
  syncRoleHintsFromSelectedVariables()
  aiStore.clearPromptOptimizeResult()
  resetPreview()
  ElMessage.success('已应用优化结果。')
}

function closePromptOptimizeResult(): void {
  aiStore.clearPromptOptimizeResult()
}

async function generateDraft(adjustmentHints?: string | Event): Promise<void> {
  const previewAdjustmentHints = typeof adjustmentHints === 'string' ? adjustmentHints : ''
  if (!canGenerate.value) {
    ElMessage.warning(
      !isConfigured.value
        ? '请先配置 AI 模型。'
        : !hasRuleDescription.value
          ? '请先输入规则描述。'
          : '请先选择变量池变量，或开启 AI 自动补齐数据源/变量。',
    )
    return
  }

  clearAutoFillTimer()
  syncRoleHintsFromSelectedVariables()
  applyDescriptionHints()
  syncRoleHintsFromSelectedVariables()
  resetPreview()
  try {
    await workbenchStore.saveConfigNow()
    const draft = await aiStore.generateDraft(
      buildDescriptionPayload(),
      buildExtraHintsPayload(previewAdjustmentHints),
      buildWorkflowHintsPayload(),
      {
        inputMode: 'free_text',
        allowAutoComplete: allowAutoComplete.value,
        selectedVariableTags: selectedVariableTags.value,
      },
    )
    if (draft.verdict === 'ready') {
      ElMessage.success('AI 草稿已生成，开始执行预校验。')
      await previewDraft(draft)
    } else if (draft.verdict === 'needs_input') {
      ElMessage.warning('AI 校验完成，当前输入不足以自动添加，请修改后重试。')
    } else {
      ElMessage.info('AI 校验完成，当前规则暂不可添加。')
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '生成规则草稿失败。')
  }
}

async function regenerateDraftWithPreviewAdvice(): Promise<void> {
  const adjustmentHints = previewExplanation.value.adjustmentHints
  if (!adjustmentHints) {
    ElMessage.warning('当前没有可用于重新生成的预校验调整建议。')
    return
  }
  if (!canRegenerateWithPreviewAdvice.value) {
    ElMessage.warning('请先等待当前操作完成，并确认规则描述和目标变量仍可用于 AI 校验。')
    return
  }

  isRegeneratingWithPreviewAdvice.value = true
  try {
    await generateDraft(adjustmentHints)
  } finally {
    isRegeneratingWithPreviewAdvice.value = false
  }
}

async function autoCompleteAndApply(): Promise<void> {
  if (!canAutoCompleteAndApply.value) {
    ElMessage.warning('请先补充规则描述并开启 AI 自动补齐，或等待当前操作完成。')
    return
  }

  clearAutoFillTimer()
  syncRoleHintsFromSelectedVariables()
  applyDescriptionHints()
  syncRoleHintsFromSelectedVariables()
  resetPreview()
  isAutoCompletingAndApplying.value = true
  try {
    await workbenchStore.saveConfigNow()
    const draft = await aiStore.generateDraft(
      buildDescriptionPayload(),
      buildExtraHintsPayload(),
      buildWorkflowHintsPayload(),
      {
        inputMode: 'free_text',
        allowAutoComplete: true,
        selectedVariableTags: selectedVariableTags.value,
      },
    )
    if (draft.verdict !== 'ready') {
      ElMessage.warning('仍缺少可自动补齐的信息，请补充数据源、Sheet、字段或 Key 后重试。')
      return
    }
    if (!draft.draft.sources_to_add.length && !draft.draft.variables_to_add.length && !draft.draft.rules_to_add.length) {
      ElMessage.warning('本次没有可写入的补齐草稿。')
      return
    }

    ElMessage.success('已补齐草稿，开始预校验。')
    const previewOk = await previewDraft(draft)
    if (!previewOk) {
      ElMessage.warning('预校验未通过，未写入个人校验配置。')
      return
    }
    await applyDraft()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '一键补齐并添加失败。')
  } finally {
    isAutoCompletingAndApplying.value = false
  }
}

async function previewDraft(draft = currentDraft.value): Promise<boolean> {
  if (!draft || draft.verdict !== 'ready') {
    ElMessage.warning('当前没有可预校验的 ready 草稿。')
    return false
  }
  if (!draft.draft.rules_to_add.length) {
    ElMessage.warning('当前草稿没有可执行规则。')
    return false
  }

  isPreviewing.value = true
  previewError.value = ''
  previewResult.value = null
  try {
    previewResult.value = await workbenchStore.previewAiRuleDraft(buildDraftPayloadForWorkflow(draft))
    if (previewFailedSources.value.length) {
      ElMessage.warning('预校验完成，但存在数据源读取失败。')
    } else {
      ElMessage.success('预校验完成，可查看结果后决定是否添加。')
    }
    return previewFailedSources.value.length === 0
  } catch (error) {
    previewError.value = error instanceof Error ? error.message : '预校验失败。'
    ElMessage.error(previewError.value)
    return false
  } finally {
    isPreviewing.value = false
  }
}

async function applyDraft(options?: { execute?: boolean; rule?: FixedRuleDefinition }): Promise<void> {
  const draft = currentDraft.value
  if (!draft || draft.verdict !== 'ready') {
    ElMessage.warning('当前没有可添加的规则草稿。')
    return
  }
  if (!isPreviewSuccessful.value) {
    ElMessage.warning('请先完成预校验，确认数据源和规则可执行后再添加。')
    return
  }
  if (!draft.draft.rules_to_add.length) {
    ElMessage.warning('当前草稿没有规则可添加。')
    return
  }
  const candidateRules = options?.rule ? [options.rule] : draft.draft.rules_to_add
  const rulesToApply = candidateRules.filter((rule) => !duplicateRuleIds.value.has(rule.rule_id))
  const skippedCount = candidateRules.length - rulesToApply.length
  if (!rulesToApply.length) {
    ElMessage.warning('当前规则已存在，无需重复添加。')
    return
  }

  isApplying.value = true
  try {
    const payload = buildDraftPayloadForWorkflow(draft, {
      rules: rulesToApply,
      ensureGroup: true,
    })
    const ruleIds = await workbenchStore.applyAiRuleDraft(payload)
    if (!options?.rule || draft.draft.rules_to_add.length === 1) {
      await aiStore.markApplied(draft.draft_id)
    }
    ElMessage.success(
      skippedCount
        ? `已跳过 ${skippedCount} 条已有规则，新增 ${ruleIds.length} 条规则并保存。`
        : `已添加 ${ruleIds.length} 条规则并保存。`,
    )
    if (options?.execute) {
      emit('applied-and-execute', ruleIds)
    } else {
      emit('applied', ruleIds)
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '添加规则失败。')
  } finally {
    isApplying.value = false
  }
}

function hydrateHintsFromDraft(draft: AiRuleDraft): void {
  manuallyEditedHintKeys.clear()
  const firstSource = draft.draft.sources_to_add[0]
  const firstVariable = draft.draft.variables_to_add[0]
  const firstRule = draft.draft.rules_to_add[0]
  const reusedTags = new Set(draft.draft.reuse_variable_tags)
  draft.draft.rules_to_add.forEach((rule) => {
    if (rule.target_variable_tag) reusedTags.add(rule.target_variable_tag)
    if (rule.reference_variable_tag) reusedTags.add(rule.reference_variable_tag)
  })
  selectedVariableTags.value = Array.from(reusedTags)
  workflowHints.ruleTypeHint = firstRule?.rule_type || workflowHints.ruleTypeHint
  workflowHints.targetVariableTag = firstRule?.target_variable_tag || workflowHints.targetVariableTag
  workflowHints.referenceVariableTag =
    firstRule?.reference_variable_tag || workflowHints.referenceVariableTag
  workflowHints.leftVariableTag = firstRule?.target_variable_tag || workflowHints.leftVariableTag
  workflowHints.rightVariableTag = firstRule?.reference_variable_tag || workflowHints.rightVariableTag
  workflowHints.sourceId = firstVariable?.source_id || firstSource?.id || workflowHints.sourceId
  workflowHints.sourceUrl =
    firstSource?.pathOrUrl || firstSource?.url || firstSource?.path || workflowHints.sourceUrl
  workflowHints.sheet = firstVariable?.sheet || workflowHints.sheet
  workflowHints.targetField =
    firstVariable?.variable_kind === 'composite'
      ? firstVariable.columns?.[0] ?? workflowHints.targetField
      : firstVariable?.column || workflowHints.targetField
  workflowHints.displayField = firstRule?.display_field || workflowHints.displayField
  workflowHints.ruleGroupName = AI_RULE_GROUP_NAME
  workflowHints.keyColumn = firstVariable?.key_column || workflowHints.keyColumn
  workflowHints.compositeColumns =
    firstVariable?.variable_kind === 'composite'
      ? (firstVariable.columns ?? []).join(',')
      : workflowHints.compositeColumns
}

function loadHistoryDraft(draft: AiRuleDraft): void {
  aiStore.setCurrentDraft(draft)
  aiStore.clearPromptOptimizeResult()
  const originalDescription = draft.description?.trim()
  if (originalDescription) {
    description.value = originalDescription
  }
  hydrateHintsFromDraft(draft)
  resetPreview()
}

async function deleteHistoryDraft(draft: AiRuleDraft): Promise<void> {
  if (!draft.draft_id) return
  await aiStore.deleteDraft(draft.draft_id)
  ElMessage.success('草稿已删除。')
}

async function clearHistory(): Promise<void> {
  try {
    await ElMessageBox.confirm('确认清空最近 20 条 AI 草稿历史？', '清空草稿历史', {
      confirmButtonText: '清空',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  await aiStore.clearDraftHistory()
  resetPreview()
  ElMessage.success('草稿历史已清空。')
}

function goProfile(): void {
  void router.push({ name: 'profile' })
}

function handleViewConfig(item: AiRuleResultViewModel): void {
  configDrawerItem.value = item
  configDrawerVisible.value = true
}

function handleMissingAction(missing: AiMissingItem | undefined): void {
  if (!missing) {
    ElMessage.info('请在上方补充 Sheet、列名或数据源线索后重新校验。')
    return
  }
  if (missing.suggested_action === 'open_source_dialog') {
    emit('open-source-prefill', missing.prefill)
    return
  }
  if (missing.suggested_action === 'open_single_variable_dialog') {
    emit('open-single-variable-prefill', missing.prefill)
    return
  }
  if (missing.suggested_action === 'open_composite_variable_dialog') {
    emit('open-composite-variable-prefill', missing.prefill)
    return
  }
  ElMessage.info(missing.message || '请补充规则描述后重新校验。')
}

function rewriteRule(): void {
  const originalDescription = currentDraft.value?.description?.trim()
  if (originalDescription) {
    description.value = originalDescription
  }
  ElMessage.info('请在输入框中改写规则后重新校验。')
}

function formatOptimizeFilters(filters: Array<Record<string, unknown>>): string {
  if (!filters.length) return '未识别'
  return filters
    .map((item) => {
      const side = item.side ? `${String(item.side)}：` : ''
      const field = String(item.field ?? '-')
      const operator = String(item.operator ?? '-')
      const value = String(item.value ?? '-')
      return `${side}${field} ${operator} ${value}`
    })
    .join('；')
}

function formatOptimizeList(values: string[]): string {
  return values.length ? values.join('、') : '未识别'
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-'
  return typeof value === 'string' ? value : JSON.stringify(value)
}
</script>

<template>
  <div class="smart-rule-workspace">
    <main class="smart-rule-workspace__main">
      <SmartRuleInputCard
        v-model:description="description"
        :selected-variable-tags="selectedVariableTags"
        :allow-auto-complete="allowAutoComplete"
        :variables="workbenchStore.variables"
        :provider-label="providerLabel"
        :is-configured="isConfigured"
        :is-generating="aiStore.isDraftGenerating"
        :is-optimizing="aiStore.isPromptOptimizing"
        :can-generate="canGenerate"
        :max-length="DESCRIPTION_MAX_LENGTH"
        :prompt-text="COMMON_WORKFLOW_PROMPT"
        :templates="availableAiRuleTemplates"
        :recommended-templates="recommendedAiRuleTemplates"
        @update:description="resetPreview"
        @update:selected-variable-tags="updateSelectedVariableTags"
        @update:allow-auto-complete="updateAllowAutoComplete"
        @optimize="optimizePrompt"
        @generate="generateDraft"
        @clear="clearInput"
        @refresh-history="aiStore.loadDrafts"
        @model-config="goProfile"
        @load-example="loadBusinessRuleExample"
        @copy-prompt="copyWorkflowPrompt"
        @apply-template="handleApplyRuleTemplate"
      />

      <section
        v-if="promptOptimizeResult"
        class="smart-rule-card prompt-optimize-result"
        :class="{ 'is-fallback': promptOptimizeResult.fallback }"
      >
        <div class="smart-rule-card__header">
          <div>
            <h3>优化后描述</h3>
            <p>
              {{
                promptOptimizeResult.fallback
                  ? '兜底优化结果，仅供参考。'
                  : '请确认后替换原文，或继续编辑当前描述。'
              }}
            </p>
          </div>
          <span class="ai-rule-status-label" :class="`is-${promptOptimizeResult.status}`">
            {{ promptOptimizeResult.status }}
          </span>
        </div>
        <div class="prompt-optimize-result__body">
          <div class="prompt-optimize-result__description">
            <pre>{{ promptOptimizeResult.optimized_description || '暂无优化描述。' }}</pre>
          </div>
          <div class="prompt-optimize-result__clues">
            <h4>识别到的规则线索</h4>
            <dl>
              <dt>规则类型</dt>
              <dd>{{ getAiRuleTypeLabel(promptOptimizeResult.detected_clues.rule_type_hint) }}</dd>
              <dt>涉及变量</dt>
              <dd>{{ formatOptimizeList(promptOptimizeResult.detected_clues.involved_variables) }}</dd>
              <dt>Key 字段</dt>
              <dd>{{ promptOptimizeResult.detected_clues.key_field || '未识别' }}</dd>
              <dt>筛选条件</dt>
              <dd>{{ formatOptimizeFilters(promptOptimizeResult.detected_clues.filters) }}</dd>
              <dt>比较字段</dt>
              <dd>{{ formatOptimizeList(promptOptimizeResult.detected_clues.compare_fields) }}</dd>
            </dl>
            <div v-if="promptOptimizeResult.missing.length" class="prompt-optimize-result__notes">
              <strong>仍需确认/补充</strong>
              <p>{{ promptOptimizeResult.missing.join('；') }}</p>
            </div>
            <div v-if="promptOptimizeResult.warnings.length" class="prompt-optimize-result__notes is-warning">
              <strong>提示</strong>
              <p>{{ promptOptimizeResult.warnings.join('；') }}</p>
            </div>
            <div v-if="promptOptimizeResult.confidence !== null && promptOptimizeResult.confidence !== undefined" class="prompt-optimize-result__confidence">
              置信度：{{ Math.round(promptOptimizeResult.confidence * 100) }}%
            </div>
          </div>
        </div>
        <div class="prompt-optimize-result__actions">
          <PrimaryButton
            :disabled="!promptOptimizeResult.optimized_description"
            @click="applyOptimizedDescription"
          >
            替换原文
          </PrimaryButton>
          <SecondaryButton @click="closePromptOptimizeResult">关闭</SecondaryButton>
        </div>
      </section>

      <AiRuleResultList
        :items="resultItems"
        :summary="resultSummary"
        :loading="aiStore.isDraftGenerating"
        :error="aiStore.error"
        :can-apply="canApplyDraft"
        :can-auto-complete-apply="canAutoCompleteAndApply"
        :auto-complete-apply-loading="isAutoCompletingAndApplying"
        :show-apply-group-select="hasReadyRules && Boolean(addableDraftRules.length)"
        :selected-apply-group-id="selectedApplyGroupId"
        :apply-group-options="applyGroupOptions"
        @update:selected-apply-group-id="selectedApplyGroupId = $event"
        @view-config="handleViewConfig"
        @apply-rule="(item) => applyDraft({ rule: item.rule })"
        @resolve-missing="handleMissingAction"
        @auto-complete-apply="autoCompleteAndApply"
        @rewrite-rule="rewriteRule"
      />

      <section
        v-if="currentDraft?.verdict === 'ready'"
        class="smart-rule-card ai-preview-result"
      >
        <div class="smart-rule-card__header">
          <h3>预校验结果</h3>
          <SecondaryButton
            size="sm"
            :disabled="isPreviewing || currentDraft.applied"
            @click="previewDraft()"
          >
            <template #icon><Refresh /></template>
            {{ isPreviewing ? '预校验中…' : previewResult ? '重新预校验' : '执行预校验' }}
          </SecondaryButton>
        </div>

        <div v-if="isPreviewing" class="ai-rule-result-state">正在读取数据源并执行临时规则，请稍候。</div>
        <div v-else-if="previewError" class="ai-rule-result-state is-error">{{ previewError }}</div>
        <div v-else-if="previewResult" class="ai-preview-result__body">
          <div class="ai-preview-result__stats">
            <div>
              <span>扫描行数</span>
              <strong>{{ previewResult.meta.total_rows_scanned }}</strong>
            </div>
            <div>
              <span>异常数量</span>
              <strong>{{ previewTotal }}</strong>
            </div>
            <div>
              <span>失败数据源</span>
              <strong :class="previewFailedSources.length ? 'text-danger' : 'text-success'">
                {{ previewFailedSources.length }}
              </strong>
            </div>
            <div>
              <span>执行耗时</span>
              <strong>{{ previewResult.meta.execution_time_ms }}ms</strong>
            </div>
          </div>
          <div v-if="previewFailedSources.length" class="ai-preview-result__warning">
            数据源读取失败：{{ previewFailedSources.join('、') }}
          </div>
          <div
            v-if="previewExplanation.hasResult"
            class="ai-preview-explanation"
            :class="{ 'is-passed': previewExplanation.passed, 'is-warning': previewExplanation.hasIssues }"
          >
            <div class="ai-preview-explanation__head">
              <div>
                <h4>{{ previewExplanation.summaryTitle }}</h4>
                <p>{{ previewExplanation.summaryText }}</p>
              </div>
              <span class="ai-preview-explanation__badge">
                {{ previewExplanation.passed ? '可添加' : '需确认' }}
              </span>
            </div>

            <div v-if="previewExplanation.issueGroups.length" class="ai-preview-explanation__groups">
              <article
                v-for="group in previewExplanation.issueGroups"
                :key="group.id"
                class="ai-preview-explanation__group"
              >
                <div class="ai-preview-explanation__group-top">
                  <strong>{{ group.ruleName }}</strong>
                  <span>样例中 {{ group.sampleCount }} 条</span>
                </div>
                <p class="ai-preview-explanation__message">{{ group.message }}</p>
                <div class="ai-preview-explanation__samples">
                  <span
                    v-for="sample in group.sampleRows"
                    :key="`${sample.ruleName}-${sample.location}-${sample.rowIndex}-${sample.rawValue}`"
                  >
                    行 {{ sample.rowIndex }} · {{ sample.location }} · 原始值 {{ sample.rawValue }}
                    <template v-if="sample.displayValue"> · 显示 {{ sample.displayValue }}</template>
                  </span>
                </div>
                <p class="ai-preview-explanation__suggestion">建议：{{ group.suggestion }}</p>
              </article>
            </div>

            <div v-if="previewExplanation.suggestions.length" class="ai-preview-explanation__suggestions">
              <span>修复方向</span>
              <ul>
                <li v-for="suggestion in previewExplanation.suggestions" :key="suggestion">
                  {{ suggestion }}
                </li>
              </ul>
            </div>

            <div v-if="previewExplanation.canRegenerate" class="ai-preview-explanation__actions">
              <SecondaryButton
                size="sm"
                :disabled="!canRegenerateWithPreviewAdvice"
                :loading="isRegeneratingWithPreviewAdvice || aiStore.isDraftGenerating"
                @click="regenerateDraftWithPreviewAdvice"
              >
                <template #icon><MagicStick /></template>
                带调整建议重新生成
              </SecondaryButton>
              <span>只重新生成草稿并再次预校验，不会直接保存规则。</span>
            </div>
          </div>
          <el-table
            v-if="previewRows.length"
            :data="previewRows.slice(0, 5)"
            class="workbench-table"
            size="small"
            max-height="260"
          >
            <el-table-column prop="row_index" label="行号" width="80" />
            <el-table-column label="展示字段" min-width="130">
              <template #default="{ row }">{{ formatValue(row.display_value) }}</template>
            </el-table-column>
            <el-table-column label="原始值" min-width="180">
              <template #default="{ row }">{{ formatValue(row.raw_value) }}</template>
            </el-table-column>
            <el-table-column prop="message" label="说明" min-width="260" />
          </el-table>
          <div v-else class="ai-preview-result__success">
            预校验未发现异常，仍可添加规则用于后续持续检查。
          </div>
        </div>
        <div v-else class="ai-rule-result-state">
          AI 草稿生成后会自动预校验；也可点击右侧按钮手动执行。
        </div>
      </section>

      <PendingConfigPreview :preview="pendingPreview" />

      <div class="smart-rule-bottom-actions">
        <PrimaryButton :disabled="!canApplyDraft" :loading="isApplying" @click="applyDraft()">
          <template #icon><CircleCheck /></template>
          添加可用规则
        </PrimaryButton>
        <PrimaryButton :disabled="!canApplyDraft" :loading="isApplying" @click="applyDraft({ execute: true })">
          <template #icon><VideoPlay /></template>
          添加并执行
        </PrimaryButton>
        <SecondaryButton :disabled="!canGenerate || aiStore.isDraftGenerating" @click="generateDraft">
          <template #icon><MagicStick /></template>
          重新校验
        </SecondaryButton>
        <span v-if="hasReadyRules && !isPreviewSuccessful" class="smart-rule-bottom-actions__hint">
          完成预校验后才可添加。
        </span>
        <span
          v-else-if="hasReadyRules && isPreviewSuccessful && !addableDraftRules.length"
          class="smart-rule-bottom-actions__hint"
        >
          当前规则已存在，无需重复添加。
        </span>
        <span
          v-else-if="duplicateReadyRuleCount"
          class="smart-rule-bottom-actions__hint"
        >
          将跳过 {{ duplicateReadyRuleCount }} 条已有规则。
        </span>
      </div>
    </main>

    <DraftHistoryPanel
      :items="historyItems"
      :loading="aiStore.isDraftHistoryLoading"
      @clear="clearHistory"
      @fill="loadHistoryDraft"
      @delete="deleteHistoryDraft"
    />

    <el-drawer v-model="configDrawerVisible" title="规则配置详情" size="520px">
      <div v-if="configDrawerItem" class="smart-rule-config-drawer">
        <div class="smart-rule-config-drawer__summary">
          <h3>{{ configDrawerItem.title }}</h3>
          <p>{{ getAiRuleTypeLabel(configDrawerItem.rule?.rule_type) }}</p>
        </div>
        <pre>{{ configDrawerPayload }}</pre>
      </div>
    </el-drawer>
  </div>
</template>

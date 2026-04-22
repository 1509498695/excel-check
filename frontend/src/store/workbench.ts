import { defineStore } from 'pinia'

import {
  executeTaskTree,
  fetchColumnPreview,
  fetchCompositePreview,
  fetchExecutionResults,
  fetchSourceCapabilities,
  fetchSourceMetadata,
  fetchWorkbenchConfig,
  saveWorkbenchConfig,
} from '../api/workbench'
import type { FixedRuleDefinition, FixedRuleGroup } from '../types/fixedRules'
import type {
  AbnormalResult,
  DataSource,
  ExecutionMeta,
  SourceMetadata,
  SourceType,
  TaskTree,
  ValidationRule,
  VariablePreviewData,
  VariableTag,
} from '../types/workbench'
import {
  collectVariableTagsBySourceIds,
  createEntityId,
  ensureDefaultGroup,
  isCompositeVariable,
  isSingleVariable,
  isValidCompositeConfig,
  normalizeCompositeConfig,
  normalizeExpectedValue,
  pruneRulesByRemovedTags,
  RULE_ORCHESTRATION_PAGE_SIZE,
  UNGROUPED_GROUP,
} from '../utils/ruleOrchestrationModel'
import { buildTaskTreePayload } from '../utils/taskTree'
import { orchestrationRulesToValidationRules } from '../utils/workbenchOrchestrationRules'
import { SAMPLE_SOURCE_PATH } from '../utils/workbenchMeta'

interface WorkbenchState {
  sources: DataSource[]
  variables: VariableTag[]
  ruleGroups: FixedRuleGroup[]
  orchestrationRules: FixedRuleDefinition[]
  selectedGroupId: string
  groupKeyword: string
  orchestrationCurrentPage: number
  capabilities: SourceType[]
  isExecuting: boolean
  isResultPageLoading: boolean
  pageError: string
  abnormalResults: AbnormalResult[]
  abnormalResultTotal: number
  executionMeta: ExecutionMeta | null
  resultId: number | null
  resultCurrentPage: number
  resultPageSize: number
  activeTag: string | null
  preferredSourceId: string | null
  sourceMetadataMap: Record<string, SourceMetadata>
  variablePreviewMap: Record<string, VariablePreviewData>
}

function createWorkbenchDemoRules(): FixedRuleDefinition[] {
  const gid = UNGROUPED_GROUP.group_id
  return [
    {
      rule_id: createEntityId('wb-rule'),
      group_id: gid,
      rule_name: 'items-ID-非空校验',
      target_variable_tag: '[items-id]',
      rule_type: 'not_null',
    },
    {
      rule_id: createEntityId('wb-rule'),
      group_id: gid,
      rule_name: 'items-ID-唯一校验',
      target_variable_tag: '[items-id]',
      rule_type: 'unique',
    },
    {
      rule_id: createEntityId('wb-rule'),
      group_id: gid,
      rule_name: 'items-ID-大于+0',
      target_variable_tag: '[items-id]',
      rule_type: 'fixed_value_compare',
      operator: 'gt',
      expected_value: '0',
    },
    {
      rule_id: createEntityId('wb-rule'),
      group_id: gid,
      rule_name: 'drops-RefID-大于+0',
      target_variable_tag: '[drops-ref]',
      rule_type: 'fixed_value_compare',
      operator: 'gt',
      expected_value: '0',
    },
  ]
}

function isValidSequenceStep(value: string | undefined): boolean {
  const normalized = value?.trim() ?? ''
  if (!normalized) {
    return false
  }
  const numeric = Number(normalized)
  return Number.isFinite(numeric) && numeric > 0
}

function isValidSequenceStartValue(value: string | undefined): boolean {
  const normalized = value?.trim() ?? ''
  if (!normalized) {
    return false
  }
  return Number.isFinite(Number(normalized))
}

function isValidDualCompositeRule(rule: FixedRuleDefinition, variableMap: Map<string, VariableTag>): boolean {
  const targetTag = rule.target_variable_tag.trim()
  const referenceTag = rule.reference_variable_tag?.trim() ?? ''
  const targetVariable = variableMap.get(targetTag)
  const referenceVariable = variableMap.get(referenceTag)

  if (!targetTag || !referenceTag || targetTag === referenceTag) {
    return false
  }
  if (!isCompositeVariable(targetVariable) || !isCompositeVariable(referenceVariable)) {
    return false
  }
  if (!rule.key_check_mode || !['baseline_only', 'bidirectional'].includes(rule.key_check_mode)) {
    return false
  }
  if (!rule.comparisons?.length) {
    return false
  }

  const leftFields = new Set(['__key__', ...((targetVariable.columns ?? []).filter(Boolean))])
  const rightFields = new Set(['__key__', ...((referenceVariable.columns ?? []).filter(Boolean))])

  return rule.comparisons.every((comparison) => {
    if (!comparison.comparison_id?.trim()) {
      return false
    }
    if (!comparison.left_field?.trim() || !leftFields.has(comparison.left_field.trim())) {
      return false
    }
    if (!comparison.right_field?.trim() || !rightFields.has(comparison.right_field.trim())) {
      return false
    }
    return ['eq', 'ne', 'gt', 'lt', 'not_null'].includes(comparison.operator)
  })
}

export const useWorkbenchStore = defineStore('workbench', {
  state: (): WorkbenchState => ({
    sources: [],
    variables: [],
    ruleGroups: [{ ...UNGROUPED_GROUP }],
    orchestrationRules: [],
    selectedGroupId: UNGROUPED_GROUP.group_id,
    groupKeyword: '',
    orchestrationCurrentPage: 1,
    capabilities: [],
    isExecuting: false,
    isResultPageLoading: false,
    pageError: '',
    abnormalResults: [],
    abnormalResultTotal: 0,
    executionMeta: null,
    resultId: null,
    resultCurrentPage: 1,
    resultPageSize: 20,
    activeTag: null,
    preferredSourceId: null,
    sourceMetadataMap: {},
    variablePreviewMap: {},
  }),

  getters: {
    /** 供引擎执行的 ValidationRule 列表（由编排规则映射）。 */
    engineValidationRules(): ValidationRule[] {
      return orchestrationRulesToValidationRules(this.variables, this.orchestrationRules)
    },

    taskTree(): TaskTree {
      return {
        sources: this.sources,
        variables: this.variables,
        rules: this.engineValidationRules,
      }
    },

    allRuleGroups(): FixedRuleGroup[] {
      return ensureDefaultGroup(this.ruleGroups)
    },

    filteredRuleGroups(): FixedRuleGroup[] {
      const keyword = this.groupKeyword.trim().toLowerCase()
      if (!keyword) {
        return this.allRuleGroups
      }
      return this.allRuleGroups.filter((group) => group.group_name.toLowerCase().includes(keyword))
    },

    selectedRuleGroup(): FixedRuleGroup {
      return (
        this.allRuleGroups.find((group) => group.group_id === this.selectedGroupId) ??
        this.allRuleGroups[0]
      )
    },

    groupOrchestrationCounts(): Record<string, number> {
      return this.orchestrationRules.reduce<Record<string, number>>((accumulator, rule) => {
        accumulator[rule.group_id] = (accumulator[rule.group_id] ?? 0) + 1
        return accumulator
      }, {})
    },

    currentOrchestrationGroupRules(): FixedRuleDefinition[] {
      const groupId = this.selectedRuleGroup.group_id
      return this.orchestrationRules.filter((rule) => rule.group_id === groupId)
    },

    pagedCurrentOrchestrationGroupRules(): FixedRuleDefinition[] {
      const start = (this.orchestrationCurrentPage - 1) * RULE_ORCHESTRATION_PAGE_SIZE
      return this.currentOrchestrationGroupRules.slice(
        start,
        start + RULE_ORCHESTRATION_PAGE_SIZE,
      )
    },

    currentOrchestrationGroupRuleTotal(): number {
      return this.currentOrchestrationGroupRules.length
    },

    currentOrchestrationGroupPageCount(): number {
      return Math.max(
        1,
        Math.ceil(this.currentOrchestrationGroupRuleTotal / RULE_ORCHESTRATION_PAGE_SIZE),
      )
    },

    orchestrationRuleCount(): number {
      return this.orchestrationRules.length
    },

    invalidOrchestrationRuleIds(): string[] {
      const validGroupIds = new Set(this.allRuleGroups.map((group) => group.group_id))
      const variableMap = new Map(this.variables.map((variable) => [variable.tag, variable] as const))

      return this.orchestrationRules
        .filter((rule) => {
          if (!validGroupIds.has(rule.group_id)) {
            return true
          }
          if (!rule.rule_name.trim()) {
            return true
          }

          const targetTag = rule.target_variable_tag.trim()
          const variable = variableMap.get(targetTag)
          if (!targetTag || !variable) {
            return true
          }

          if (isSingleVariable(variable)) {
            if (rule.rule_type === 'composite_condition_check' || rule.rule_type === 'dual_composite_compare') {
              return true
            }

            if (rule.rule_type === 'cross_table_mapping') {
              const referenceTag = rule.reference_variable_tag?.trim() ?? ''
              if (!referenceTag) {
                return true
              }

              const referenceVariable = variableMap.get(referenceTag)
              return !isSingleVariable(referenceVariable)
            }

            if (rule.rule_type === 'sequence_order_check') {
              if (!rule.sequence_direction || !['asc', 'desc'].includes(rule.sequence_direction)) {
                return true
              }
              if (!rule.sequence_start_mode || !['auto', 'manual'].includes(rule.sequence_start_mode)) {
                return true
              }
              if (!isValidSequenceStep(rule.sequence_step)) {
                return true
              }
              if (rule.sequence_start_mode === 'manual' && !isValidSequenceStartValue(rule.sequence_start_value)) {
                return true
              }
              return false
            }

            if (rule.rule_type !== 'fixed_value_compare') {
              return false
            }

            if (!rule.operator) {
              return true
            }

            const expectedValue = normalizeExpectedValue(rule.expected_value)
            if (!expectedValue) {
              return true
            }

            if (
              (rule.operator === 'gt' || rule.operator === 'lt') &&
              Number.isNaN(Number(expectedValue))
            ) {
              return true
            }

            return false
          }

          if (!isCompositeVariable(variable)) {
            return true
          }

          if (rule.rule_type === 'composite_condition_check') {
            return !isValidCompositeConfig(rule.composite_config)
          }
          if (rule.rule_type === 'dual_composite_compare') {
            return !isValidDualCompositeRule(rule, variableMap)
          }
          return true
        })
        .map((rule) => rule.rule_id)
    },

    invalidOrchestrationGroupIds(): string[] {
      const invalidRuleIds = new Set(this.invalidOrchestrationRuleIds)
      const invalidGroupIds = new Set<string>()
      this.orchestrationRules.forEach((rule) => {
        if (invalidRuleIds.has(rule.rule_id)) {
          invalidGroupIds.add(rule.group_id)
        }
      })
      return [...invalidGroupIds]
    },

    canExecuteOrchestration(): boolean {
      return (
        this.orchestrationRules.length > 0 && this.invalidOrchestrationRuleIds.length === 0
      )
    },

    singleVariables(state): VariableTag[] {
      return state.variables.filter((variable) => (variable.variable_kind ?? 'single') === 'single')
    },

    resultCount(state): number {
      return state.abnormalResultTotal
    },

    resultPageCount(state): number {
      return Math.max(1, Math.ceil(state.abnormalResultTotal / state.resultPageSize))
    },
  },

  actions: {
    clearPageError(): void {
      this.pageError = ''
    },

    setActiveTag(tag: string | null): void {
      this.activeTag = tag
    },

    clearSourceMetadata(sourceId: string): void {
      delete this.sourceMetadataMap[sourceId]
    },

    clearVariablePreview(tag: string): void {
      delete this.variablePreviewMap[tag]
    },

    invalidateSourceArtifacts(sourceIds: string[]): void {
      const normalizedIds = new Set(sourceIds.filter(Boolean))
      if (!normalizedIds.size) {
        return
      }

      normalizedIds.forEach((sourceId) => {
        delete this.sourceMetadataMap[sourceId]
      })

      const affectedTags = collectVariableTagsBySourceIds(this.variables, normalizedIds)
      affectedTags.forEach((tag) => {
        delete this.variablePreviewMap[tag]
      })
    },

    async loadCapabilities(): Promise<void> {
      try {
        const response = await fetchSourceCapabilities()
        this.capabilities = response.data.source_types
      } catch (error) {
        this.pageError = error instanceof Error ? error.message : '获取数据源能力失败。'
      }
    },

    async loadSourceMetadata(sourceId: string): Promise<SourceMetadata> {
      const cached = this.sourceMetadataMap[sourceId]
      if (cached) {
        return cached
      }

      const source = this.sources.find((item) => item.id === sourceId)
      if (!source) {
        throw new Error(`未找到数据源 "${sourceId}"。`)
      }

      const response = await fetchSourceMetadata(source)
      this.sourceMetadataMap[sourceId] = response.data
      return response.data
    },

    async loadVariablePreview(
      variable: VariableTag,
      limit?: number,
      forceRefresh = false,
    ): Promise<VariablePreviewData> {
      const cached = this.variablePreviewMap[variable.tag]
      const wantsAllRows = limit === undefined || limit === null

      if (cached && !forceRefresh) {
        const cachedLoadsAllRows =
          cached.variable_kind === 'single'
            ? cached.loaded_all_rows ?? cached.preview_rows.length === cached.total_rows
            : cached.loaded_all_rows ?? (cached.loaded_rows ?? 0) === cached.total_rows

        const cachedMatchesLimit =
          cached.variable_kind === 'single'
            ? cached.preview_limit === limit
            : wantsAllRows

        if ((wantsAllRows && cachedLoadsAllRows) || (!wantsAllRows && cachedMatchesLimit)) {
          return cached
        }
      }

      const source = this.sources.find((item) => item.id === variable.source_id)
      if (!source) {
        throw new Error(`变量 "${variable.tag}" 引用了不存在的数据源 "${variable.source_id}"。`)
      }

      const response =
        (variable.variable_kind ?? 'single') === 'composite'
          ? await fetchCompositePreview({
              source,
              sheet: variable.sheet,
              columns: variable.columns ?? [],
              key_column: variable.key_column ?? '',
              append_index_to_key: variable.append_index_to_key ?? false,
            })
          : await fetchColumnPreview({
              source,
              sheet: variable.sheet,
              column: variable.column ?? '',
              limit,
            })
      this.variablePreviewMap[variable.tag] = response.data
      return response.data
    },

    upsertSource(source: DataSource, originalId?: string): void {
      const sourceCopy = { ...source }
      const affectedSourceIds = new Set<string>([sourceCopy.id])

      if (originalId) {
        affectedSourceIds.add(originalId)
      }

      if (originalId && originalId !== source.id) {
        const index = this.sources.findIndex((item) => item.id === originalId)
        if (index >= 0) {
          this.sources.splice(index, 1, sourceCopy)
          this.variables = this.variables.map((variable) =>
            variable.source_id === originalId ? { ...variable, source_id: source.id } : variable,
          )
          this.preferredSourceId = sourceCopy.id
          this.invalidateSourceArtifacts([...affectedSourceIds])
          return
        }
      }

      const index = this.sources.findIndex((item) => item.id === source.id)

      if (index >= 0) {
        this.sources.splice(index, 1, sourceCopy)
        this.preferredSourceId = sourceCopy.id
        this.invalidateSourceArtifacts([...affectedSourceIds])
        return
      }

      this.sources.unshift(sourceCopy)
      this.preferredSourceId = sourceCopy.id
      this.invalidateSourceArtifacts([...affectedSourceIds])
    },

    removeSource(sourceId: string): void {
      const removedTags = new Set(
        this.variables
          .filter((variable) => variable.source_id === sourceId)
          .map((variable) => variable.tag),
      )

      this.sources = this.sources.filter((source) => source.id !== sourceId)
      this.variables = this.variables.filter((variable) => variable.source_id !== sourceId)
      this.orchestrationRules = pruneRulesByRemovedTags(this.orchestrationRules, removedTags)
      this.invalidateSourceArtifacts([sourceId])

      const pageCount = Math.max(
        1,
        Math.ceil(this.currentOrchestrationGroupRuleTotal / RULE_ORCHESTRATION_PAGE_SIZE),
      )
      if (this.orchestrationCurrentPage > pageCount) {
        this.orchestrationCurrentPage = pageCount
      }

      removedTags.forEach((tag) => {
        delete this.variablePreviewMap[tag]
      })

      if (this.activeTag && removedTags.has(this.activeTag)) {
        this.activeTag = null
      }

      if (this.preferredSourceId === sourceId) {
        this.preferredSourceId = this.sources[0]?.id ?? null
      }
    },

    useSampleSource(): void {
      this.upsertSource({
        id: 'src_demo',
        type: 'local_excel',
        pathOrUrl: SAMPLE_SOURCE_PATH,
      })
    },

    upsertVariable(variable: VariableTag, originalTag?: string): void {
      const variableCopy = {
        ...variable,
        append_index_to_key: variable.append_index_to_key ?? false,
      }

      if (originalTag) {
        const index = this.variables.findIndex((item) => item.tag === originalTag)
        if (index >= 0) {
          this.variables.splice(index, 1, variableCopy)
          delete this.variablePreviewMap[originalTag]
          delete this.variablePreviewMap[variableCopy.tag]

          if (originalTag !== variable.tag) {
            this.replaceTagInOrchestrationRules(originalTag, variable.tag)
            if (this.activeTag === originalTag) {
              this.activeTag = variable.tag
            }
          }
          this.activeTag = variableCopy.tag
          return
        }
      }

      const index = this.variables.findIndex((item) => item.tag === variable.tag)
      if (index >= 0) {
        this.variables.splice(index, 1, variableCopy)
        delete this.variablePreviewMap[variableCopy.tag]
        this.activeTag = variableCopy.tag
        return
      }

      this.variables.push(variableCopy)
      delete this.variablePreviewMap[variableCopy.tag]
      this.activeTag = variableCopy.tag
    },

    removeVariable(tag: string): void {
      this.variables = this.variables.filter((variable) => variable.tag !== tag)
      this.orchestrationRules = pruneRulesByRemovedTags(this.orchestrationRules, new Set([tag]))
      delete this.variablePreviewMap[tag]

      if (this.activeTag === tag) {
        this.activeTag = null
      }

      const pageCount = Math.max(
        1,
        Math.ceil(this.currentOrchestrationGroupRuleTotal / RULE_ORCHESTRATION_PAGE_SIZE),
      )
      if (this.orchestrationCurrentPage > pageCount) {
        this.orchestrationCurrentPage = pageCount
      }
    },

    useSampleVariables(): void {
      if (!this.sources.length) {
        this.useSampleSource()
      }

      const sourceId =
        this.sources.find((source) => source.id === 'src_demo')?.id ??
        this.sources[0]?.id ??
        'src_demo'

      this.upsertVariable({
        tag: '[items-id]',
        source_id: sourceId,
        sheet: 'items',
        variable_kind: 'single',
        column: 'ID',
        expected_type: 'str',
      })
      this.upsertVariable({
        tag: '[drops-ref]',
        source_id: sourceId,
        sheet: 'drops',
        variable_kind: 'single',
        column: 'RefID',
        expected_type: 'str',
      })
    },

    applyDemoScenario(): void {
      this.pageError = ''
      this.executionMeta = null
      this.resultId = null
      this.resultCurrentPage = 1
      this.abnormalResultTotal = 0
      this.isResultPageLoading = false
      this.abnormalResults = []
      this.activeTag = '[items-id]'
      this.sourceMetadataMap = {}
      this.variablePreviewMap = {}

      this.sources = []
      this.variables = []

      this.useSampleSource()
      this.useSampleVariables()

      this.ruleGroups = [{ ...UNGROUPED_GROUP }]
      this.selectedGroupId = UNGROUPED_GROUP.group_id
      this.groupKeyword = ''
      this.orchestrationCurrentPage = 1
      this.orchestrationRules = createWorkbenchDemoRules()
    },

    setSelectedOrchestrationGroup(groupId: string): void {
      this.selectedGroupId = groupId
      this.orchestrationCurrentPage = 1
    },

    setOrchestrationCurrentPage(page: number): void {
      this.orchestrationCurrentPage = page
    },

    createOrchestrationGroup(groupName: string): void {
      this.ruleGroups = ensureDefaultGroup([
        ...this.ruleGroups,
        {
          group_id: createEntityId('group'),
          group_name: groupName.trim(),
          builtin: false,
        },
      ])
    },

    renameOrchestrationGroup(groupId: string, groupName: string): void {
      this.ruleGroups = ensureDefaultGroup(
        this.ruleGroups.map((group) =>
          group.group_id === groupId && !group.builtin
            ? { ...group, group_name: groupName.trim() }
            : group,
        ),
      )
    },

    removeOrchestrationGroup(groupId: string): void {
      if (groupId === UNGROUPED_GROUP.group_id) {
        return
      }
      this.ruleGroups = ensureDefaultGroup(
        this.ruleGroups.filter((group) => group.group_id !== groupId),
      )
      this.orchestrationRules = this.orchestrationRules.map((rule) =>
        rule.group_id === groupId ? { ...rule, group_id: UNGROUPED_GROUP.group_id } : rule,
      )
      this.selectedGroupId = this.ruleGroups[0]?.group_id ?? UNGROUPED_GROUP.group_id
      this.orchestrationCurrentPage = 1
    },

    upsertOrchestrationRule(
      rule: Omit<FixedRuleDefinition, 'rule_id'> & { rule_id?: string },
    ): void {
      const normalizedCompositeConfig =
        rule.rule_type === 'composite_condition_check'
          ? normalizeCompositeConfig(rule.composite_config)
          : undefined

      const nextRule: FixedRuleDefinition = {
        rule_id: rule.rule_id ?? createEntityId('wb-rule'),
        group_id: rule.group_id,
        rule_name: rule.rule_name.trim(),
        target_variable_tag: rule.target_variable_tag.trim(),
        rule_type: rule.rule_type,
        operator: rule.rule_type === 'fixed_value_compare' ? rule.operator : undefined,
        expected_value:
          rule.rule_type === 'fixed_value_compare'
            ? normalizeExpectedValue(rule.expected_value)
            : undefined,
        reference_variable_tag:
          rule.rule_type === 'cross_table_mapping' || rule.rule_type === 'dual_composite_compare'
            ? rule.reference_variable_tag?.trim() || undefined
            : undefined,
        sequence_direction:
          rule.rule_type === 'sequence_order_check' ? rule.sequence_direction ?? 'asc' : undefined,
        sequence_step:
          rule.rule_type === 'sequence_order_check' ? rule.sequence_step?.trim() || '1' : undefined,
        sequence_start_mode:
          rule.rule_type === 'sequence_order_check'
            ? rule.sequence_start_mode ?? 'auto'
            : undefined,
        sequence_start_value:
          rule.rule_type === 'sequence_order_check' && rule.sequence_start_mode === 'manual'
            ? rule.sequence_start_value?.trim() || undefined
            : undefined,
        composite_config: normalizedCompositeConfig,
        key_check_mode:
          rule.rule_type === 'dual_composite_compare'
            ? rule.key_check_mode ?? 'baseline_only'
            : undefined,
        comparisons:
          rule.rule_type === 'dual_composite_compare'
            ? (rule.comparisons ?? []).map((comparison) => ({
                comparison_id: comparison.comparison_id,
                left_field: comparison.left_field.trim(),
                operator: comparison.operator,
                right_field: comparison.right_field.trim(),
              }))
            : [],
      }

      const index = this.orchestrationRules.findIndex((item) => item.rule_id === nextRule.rule_id)
      if (index >= 0) {
        this.orchestrationRules.splice(index, 1, nextRule)
      } else {
        this.orchestrationRules.push(nextRule)
      }
    },

    removeOrchestrationRule(ruleId: string): void {
      this.orchestrationRules = this.orchestrationRules.filter((rule) => rule.rule_id !== ruleId)
      const pageCount = Math.max(
        1,
        Math.ceil(this.currentOrchestrationGroupRuleTotal / RULE_ORCHESTRATION_PAGE_SIZE),
      )
      if (this.orchestrationCurrentPage > pageCount) {
        this.orchestrationCurrentPage = pageCount
      }
    },

    replaceTagInOrchestrationRules(previousTag: string, nextTag: string): void {
      this.orchestrationRules = this.orchestrationRules.map((rule) =>
        rule.target_variable_tag === previousTag ||
        rule.reference_variable_tag === previousTag
          ? {
              ...rule,
              target_variable_tag:
                rule.target_variable_tag === previousTag
                  ? nextTag
                  : rule.target_variable_tag,
              reference_variable_tag:
                rule.reference_variable_tag === previousTag
                  ? nextTag
                  : rule.reference_variable_tag,
            }
          : rule,
      )
    },

    buildTaskTreePayload(
      selectedRuleIds?: string[],
      page?: number,
      size?: number,
    ): TaskTree {
      return buildTaskTreePayload(
        this.sources,
        this.variables,
        this.engineValidationRules,
        selectedRuleIds,
        page,
        size,
      )
    },

    async executeValidation(selectedRuleIds?: string[]): Promise<void> {
      this.pageError = ''
      if (!this.orchestrationRules.length) {
        this.pageError = '请先在步骤 3 添加至少一条规则。'
        return
      }
      if (this.invalidOrchestrationRuleIds.length) {
        this.pageError = '存在未配置完整的规则，请按步骤 3 顶部提示修复后再执行。'
        return
      }

      this.isExecuting = true

      try {
        const payload = this.buildTaskTreePayload(
          selectedRuleIds,
          1,
          this.resultPageSize,
        )
        const response = await executeTaskTree(payload)
        this.executionMeta = response.meta
        this.resultId = response.meta.result_id ?? null
        this.resultCurrentPage = response.data.page ?? 1
        this.abnormalResultTotal =
          response.data.total ?? response.data.abnormal_results.length
        this.abnormalResults = response.data.list ?? response.data.abnormal_results
      } catch (error) {
        this.executionMeta = null
        this.resultId = null
        this.resultCurrentPage = 1
        this.abnormalResultTotal = 0
        this.abnormalResults = []
        this.pageError = error instanceof Error ? error.message : '执行校验失败。'
        throw error
      } finally {
        this.isExecuting = false
      }
    },

    async loadResultPage(page: number): Promise<void> {
      if (!this.resultId || !this.executionMeta) {
        return
      }

      this.isResultPageLoading = true
      this.pageError = ''
      try {
        const response = await fetchExecutionResults(
          this.resultId,
          page,
          this.resultPageSize,
        )
        this.executionMeta = response.meta
        this.resultCurrentPage = response.data.page ?? page
        this.abnormalResultTotal =
          response.data.total ?? response.data.abnormal_results.length
        this.abnormalResults = response.data.list ?? response.data.abnormal_results
      } catch (error) {
        this.pageError = error instanceof Error ? error.message : '读取结果分页失败。'
        throw error
      } finally {
        this.isResultPageLoading = false
      }
    },

    _getAutoSavePayload(): Record<string, unknown> {
      return {
        sources: this.sources,
        variables: this.variables,
        ruleGroups: this.ruleGroups,
        orchestrationRules: this.orchestrationRules,
      }
    },

    _scheduleAutoSave(): void {
      if ((this as any)._autoSaveTimer) {
        clearTimeout((this as any)._autoSaveTimer)
      }
      (this as any)._autoSaveTimer = setTimeout(() => {
        saveWorkbenchConfig(this._getAutoSavePayload()).catch(() => {
          /* 静默失败 */
        })
      }, 2000)
    },

    triggerAutoSave(): void {
      this._scheduleAutoSave()
    },

    async loadFromServer(): Promise<void> {
      try {
        const response = await fetchWorkbenchConfig()
        const data = response.data

        this.sources = []
        this.variables = []
        this.ruleGroups = [{ ...UNGROUPED_GROUP }]
        this.orchestrationRules = []
        this.abnormalResults = []
        this.abnormalResultTotal = 0
        this.executionMeta = null
        this.resultId = null
        this.resultCurrentPage = 1
        this.isResultPageLoading = false
        this.sourceMetadataMap = {}
        this.variablePreviewMap = {}
        this.activeTag = null
        this.preferredSourceId = null

        if (data && typeof data === 'object') {
          if (Array.isArray(data.sources)) this.sources = data.sources as DataSource[]
          if (Array.isArray(data.variables)) this.variables = data.variables as VariableTag[]
          if (Array.isArray(data.ruleGroups))
            this.ruleGroups = data.ruleGroups as FixedRuleGroup[]
          if (Array.isArray(data.orchestrationRules))
            this.orchestrationRules = data.orchestrationRules as FixedRuleDefinition[]
        }
      } catch {
        /* 首次加载无数据正常 */
      }
    },
  },
})

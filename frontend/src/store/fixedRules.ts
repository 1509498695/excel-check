import { defineStore } from 'pinia'

import {
  executeFixedRules,
  fetchFixedRulesResults,
  fetchFixedRulesConfig,
  saveFixedRulesConfig,
  triggerFixedRulesSvnUpdate,
} from '../api/fixedRules'
import {
  fetchColumnPreview,
  fetchCompositePreview,
  fetchSourceCapabilities,
  fetchSourceMetadata,
} from '../api/workbench'
import type {
  FixedRuleDefinition,
  FixedRuleGroup,
  FixedRulesConfig,
  FixedRulesConfigIssue,
  FixedRulesSvnUpdateItem,
} from '../types/fixedRules'
import type {
  AbnormalResult,
  DataSource,
  ExecutionMeta,
  SourceMetadata,
  SourceType,
  VariablePreviewData,
  VariableTag,
} from '../types/workbench'
import {
  collectVariableTagsBySourceIds,
  createEntityId,
  ensureDefaultGroup,
  isCompositeVariable,
  isValidMultiCompositePipelineConfig,
  isSingleVariable,
  isValidCompositeConfig,
  normalizeCompositeConfig,
  normalizeMultiCompositePipelineConfig,
  normalizeExpectedValue,
  pruneRulesByRemovedTags,
  RULE_ORCHESTRATION_PAGE_SIZE,
  UNGROUPED_GROUP,
} from '../utils/ruleOrchestrationModel'
import {
  extractSourceBasename,
  getSourceLocator,
  isAffectedVariable,
  isLocalFileSource,
  joinDirectoryAndBasename,
  normalizeReplacementPreset,
} from '../utils/sourcePathReplacement'
import { SAMPLE_SOURCE_PATH } from '../utils/workbenchMeta'

const FIXED_RULES_PAGE_SIZE = RULE_ORCHESTRATION_PAGE_SIZE

interface FixedRulesState {
  config: FixedRulesConfig
  capabilities: SourceType[]
  activeTag: string | null
  preferredSourceId: string | null
  sourceMetadataMap: Record<string, SourceMetadata>
  variablePreviewMap: Record<string, VariablePreviewData>
  selectedGroupId: string
  groupKeyword: string
  currentPage: number
  isLoading: boolean
  isSaving: boolean
  isExecuting: boolean
  isResultPageLoading: boolean
  isUpdatingSvn: boolean
  pageError: string
  configIssues: FixedRulesConfigIssue[]
  executionMeta: ExecutionMeta | null
  abnormalResults: AbnormalResult[]
  abnormalResultTotal: number
  resultId: number | null
  resultCurrentPage: number
  resultPageSize: number
  svnUpdateResults: FixedRulesSvnUpdateItem[]
  svnUpdateSummary: string
}

function createDefaultConfig(): FixedRulesConfig {
  return {
    version: 5,
    configured: false,
    sources: [],
    variables: [],
    groups: [{ ...UNGROUPED_GROUP }],
    rules: [],
    path_replacement_presets: [],
    selected_path_replacement_preset: null,
  }
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

function resolveFieldAgainstAvailable(
  requestedField: string | undefined,
  availableFields: string[],
): string | null {
  const rawField = requestedField ?? ''
  if (availableFields.includes(rawField)) {
    return rawField
  }

  const normalizedField = rawField.trim()
  if (!normalizedField) {
    return null
  }

  const matchedFields = availableFields.filter((field) => field.trim() === normalizedField)
  return matchedFields.length === 1 ? matchedFields[0] : null
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
    if (!resolveFieldAgainstAvailable(comparison.left_field, [...leftFields])) {
      return false
    }
    if (!resolveFieldAgainstAvailable(comparison.right_field, [...rightFields])) {
      return false
    }
    return ['eq', 'ne', 'gt', 'lt', 'not_null'].includes(comparison.operator)
  })
}

export const useFixedRulesStore = defineStore('fixed-rules', {
  state: (): FixedRulesState => ({
    config: createDefaultConfig(),
    capabilities: [],
    activeTag: null,
    preferredSourceId: null,
    sourceMetadataMap: {},
    variablePreviewMap: {},
    selectedGroupId: UNGROUPED_GROUP.group_id,
    groupKeyword: '',
    currentPage: 1,
    isLoading: false,
    isSaving: false,
    isExecuting: false,
    isResultPageLoading: false,
    isUpdatingSvn: false,
    pageError: '',
    configIssues: [],
    executionMeta: null,
    abnormalResults: [],
    abnormalResultTotal: 0,
    resultId: null,
    resultCurrentPage: 1,
    resultPageSize: 20,
    svnUpdateResults: [],
    svnUpdateSummary: '',
  }),

  getters: {
    sources(state): DataSource[] {
      return state.config.sources
    },

    pathReplacementPresets(state): string[] {
      return state.config.path_replacement_presets
    },

    selectedPathReplacementPreset(state): string | null {
      return state.config.selected_path_replacement_preset ?? null
    },

    variables(state): VariableTag[] {
      return state.config.variables
    },

    rules(state): FixedRuleDefinition[] {
      return state.config.rules
    },

    singleVariables(): VariableTag[] {
      return this.variables.filter((variable) => (variable.variable_kind ?? 'single') === 'single')
    },

    compositeVariables(): VariableTag[] {
      return this.variables.filter((variable) => (variable.variable_kind ?? 'single') === 'composite')
    },

    allGroups(state): FixedRuleGroup[] {
      return ensureDefaultGroup(state.config.groups)
    },

    filteredGroups(): FixedRuleGroup[] {
      const keyword = this.groupKeyword.trim().toLowerCase()
      if (!keyword) {
        return this.allGroups
      }

      return this.allGroups.filter((group) => group.group_name.toLowerCase().includes(keyword))
    },

    selectedGroup(): FixedRuleGroup {
      return (
        this.allGroups.find((group) => group.group_id === this.selectedGroupId) ??
        this.allGroups[0]
      )
    },

    groupRuleCounts(): Record<string, number> {
      return this.rules.reduce<Record<string, number>>((accumulator, rule) => {
        accumulator[rule.group_id] = (accumulator[rule.group_id] ?? 0) + 1
        return accumulator
      }, {})
    },

    currentGroupRules(): FixedRuleDefinition[] {
      const groupId = this.selectedGroup.group_id
      return this.rules.filter((rule) => rule.group_id === groupId)
    },

    pagedCurrentGroupRules(): FixedRuleDefinition[] {
      const start = (this.currentPage - 1) * FIXED_RULES_PAGE_SIZE
      return this.currentGroupRules.slice(start, start + FIXED_RULES_PAGE_SIZE)
    },

    currentGroupRuleTotal(): number {
      return this.currentGroupRules.length
    },

    currentGroupPageCount(): number {
      return Math.max(1, Math.ceil(this.currentGroupRuleTotal / FIXED_RULES_PAGE_SIZE))
    },

    totalRuleCount(): number {
      return this.rules.length
    },

    resultPageCount(state): number {
      return Math.max(1, Math.ceil(state.abnormalResultTotal / state.resultPageSize))
    },

    sourceCount(): number {
      return this.sources.length
    },

    variableCount(): number {
      return this.variables.length
    },

    invalidRuleIds(): string[] {
      const validGroupIds = new Set(this.allGroups.map((group) => group.group_id))
      const variableMap = new Map(this.variables.map((variable) => [variable.tag, variable] as const))

      return this.rules
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
            if (
              rule.rule_type === 'composite_condition_check' ||
              rule.rule_type === 'dual_composite_compare' ||
              rule.rule_type === 'multi_composite_pipeline_check'
            ) {
              return true
            }

            if (rule.rule_type === 'cross_table_mapping') {
              const referenceTag = rule.reference_variable_tag?.trim() ?? ''
              if (!referenceTag || referenceTag === targetTag) {
                return true
              }
              const referenceVariable = variableMap.get(referenceTag)
              if (!referenceVariable || !isSingleVariable(referenceVariable)) {
                return true
              }
              return false
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

            if (rule.rule_type === 'regex_check') {
              return !normalizeExpectedValue(rule.expected_value)
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

            if ((rule.operator === 'gt' || rule.operator === 'lt') && Number.isNaN(Number(expectedValue))) {
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
          if (rule.rule_type === 'multi_composite_pipeline_check') {
            return !isValidMultiCompositePipelineConfig(rule.pipeline_config, variableMap)
          }
          return true
        })
        .map((rule) => rule.rule_id)
    },

    invalidGroupIds(): string[] {
      const invalidRuleIds = new Set(this.invalidRuleIds)
      const invalidGroupIds = new Set<string>()

      this.rules.forEach((rule) => {
        if (invalidRuleIds.has(rule.rule_id)) {
          invalidGroupIds.add(rule.group_id)
        }
      })

      return [...invalidGroupIds]
    },

    canRunSvnUpdate(): boolean {
      return this.sources.length > 0
    },

    hasBlockingConfigIssues(): boolean {
      return this.configIssues.length > 0
    },

    canExecute(): boolean {
      return (
        this.rules.length > 0 &&
        this.invalidRuleIds.length === 0 &&
        !this.hasBlockingConfigIssues
      )
    },
  },

  actions: {
    resetState(): void {
      this.config = createDefaultConfig()
      this.activeTag = null
      this.preferredSourceId = null
      this.sourceMetadataMap = {}
      this.variablePreviewMap = {}
      this.selectedGroupId = UNGROUPED_GROUP.group_id
      this.groupKeyword = ''
      this.currentPage = 1
      this.isLoading = false
      this.isSaving = false
      this.isExecuting = false
      this.isResultPageLoading = false
      this.isUpdatingSvn = false
      this.pageError = ''
      this.configIssues = []
      this.executionMeta = null
      this.abnormalResults = []
      this.abnormalResultTotal = 0
      this.resultId = null
      this.resultCurrentPage = 1
      this.svnUpdateResults = []
      this.svnUpdateSummary = ''
    },

    clearPageError(): void {
      this.pageError = ''
    },

    clearExecutionResult(): void {
      this.executionMeta = null
      this.abnormalResults = []
      this.abnormalResultTotal = 0
      this.resultId = null
      this.resultCurrentPage = 1
      this.isResultPageLoading = false
    },

    setSelectedGroup(groupId: string): void {
      this.selectedGroupId = groupId
      this.currentPage = 1
    },

    setCurrentPage(page: number): void {
      this.currentPage = page
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

    reconcileRuntimeCaches(): void {
      const validSourceIds = new Set(this.sources.map((source) => source.id))
      const validTags = new Set(this.variables.map((variable) => variable.tag))

      this.sourceMetadataMap = Object.fromEntries(
        Object.entries(this.sourceMetadataMap).filter(([sourceId]) => validSourceIds.has(sourceId)),
      )
      this.variablePreviewMap = Object.fromEntries(
        Object.entries(this.variablePreviewMap).filter(([tag]) => validTags.has(tag)),
      )

      if (this.preferredSourceId && !validSourceIds.has(this.preferredSourceId)) {
        this.preferredSourceId = this.sources[0]?.id ?? null
      }
      if (!this.preferredSourceId) {
        this.preferredSourceId = this.sources[0]?.id ?? null
      }

      if (this.activeTag && !validTags.has(this.activeTag)) {
        this.activeTag = null
      }
    },

    applyConfig(config: FixedRulesConfig): void {
      const pathReplacementPresetMap = new Map<string, string>()
      ;(config.path_replacement_presets ?? []).forEach((preset) => {
        const normalizedPreset = normalizeReplacementPreset(preset)
        if (normalizedPreset && !pathReplacementPresetMap.has(normalizedPreset.toLowerCase())) {
          pathReplacementPresetMap.set(normalizedPreset.toLowerCase(), normalizedPreset)
        }
      })
      const normalizedSelectedPreset = config.selected_path_replacement_preset
        ? normalizeReplacementPreset(config.selected_path_replacement_preset)
        : null

      this.config = {
        ...config,
        version: 5,
        groups: ensureDefaultGroup(config.groups),
        path_replacement_presets: [...pathReplacementPresetMap.values()],
        selected_path_replacement_preset:
          normalizedSelectedPreset &&
          pathReplacementPresetMap.has(normalizedSelectedPreset.toLowerCase())
            ? pathReplacementPresetMap.get(normalizedSelectedPreset.toLowerCase()) ?? null
            : null,
      }

      if (!this.config.groups.some((group) => group.group_id === this.selectedGroupId)) {
        this.selectedGroupId = this.config.groups[0]?.group_id ?? UNGROUPED_GROUP.group_id
      }

      this.currentPage = 1
      this.reconcileRuntimeCaches()
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
        throw new Error(`未找到数据源“${sourceId}”。`)
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
        throw new Error(`变量“${variable.tag}”引用了不存在的数据源“${variable.source_id}”。`)
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

    async loadConfig(): Promise<void> {
      this.isLoading = true
      this.pageError = ''
      this.configIssues = []

      try {
        const response = await fetchFixedRulesConfig()
        this.applyConfig(response.data)
        this.configIssues = response.meta?.config_issues ?? []
      } catch (error) {
        this.configIssues = []
        this.pageError = error instanceof Error ? error.message : '读取项目校验配置失败。'
        throw error
      } finally {
        this.isLoading = false
      }
    },

    async saveConfig(): Promise<FixedRulesConfig> {
      this.isSaving = true
      this.pageError = ''

      try {
        const response = await saveFixedRulesConfig({
          ...this.config,
          version: 5,
          groups: ensureDefaultGroup(this.config.groups),
        })
        this.applyConfig(response.data)
        this.configIssues = response.meta?.config_issues ?? []
        return response.data
      } catch (error) {
        this.pageError = error instanceof Error ? error.message : '保存项目校验配置失败。'
        throw error
      } finally {
        this.isSaving = false
      }
    },

    async saveConfigNow(): Promise<void> {
      await this.saveConfig()
    },

    async executeConfig(selectedRuleIds?: string[]): Promise<void> {
      this.isExecuting = true
      this.pageError = ''

      try {
        if (this.hasBlockingConfigIssues) {
          this.pageError = '当前存在读取失败的数据源，请先修复路径替换或重新接入数据源后再执行校验。'
          throw new Error(this.pageError)
        }
        await this.saveConfig()
        const response = await executeFixedRules(
          {
            selected_rule_ids: selectedRuleIds,
            page: 1,
            size: this.resultPageSize,
          },
        )
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
        this.pageError = error instanceof Error ? error.message : '执行项目校验失败。'
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
        const response = await fetchFixedRulesResults(
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

    async runSvnUpdate(): Promise<void> {
      this.isUpdatingSvn = true
      this.pageError = ''

      try {
        await this.saveConfig()
        const response = await triggerFixedRulesSvnUpdate()
        this.svnUpdateResults = response.data.results
        this.svnUpdateSummary = `已处理 ${response.data.total_paths} 个路径，成功更新 ${response.data.updated_paths} 个。`
      } catch (error) {
        this.pageError = error instanceof Error ? error.message : 'SVN 更新失败。'
        throw error
      } finally {
        this.isUpdatingSvn = false
      }
    },

    createGroup(groupName: string): void {
      this.config.groups = ensureDefaultGroup([
        ...this.config.groups,
        {
          group_id: createEntityId('group'),
          group_name: groupName.trim(),
          builtin: false,
        },
      ])
    },

    renameGroup(groupId: string, groupName: string): void {
      this.config.groups = ensureDefaultGroup(
        this.config.groups.map((group) =>
          group.group_id === groupId && !group.builtin
            ? { ...group, group_name: groupName.trim() }
            : group,
        ),
      )
    },

    removeGroup(groupId: string): void {
      if (groupId === UNGROUPED_GROUP.group_id) {
        return
      }

      this.config.groups = ensureDefaultGroup(
        this.config.groups.filter((group) => group.group_id !== groupId),
      )
      this.config.rules = this.config.rules.map((rule) =>
        rule.group_id === groupId ? { ...rule, group_id: UNGROUPED_GROUP.group_id } : rule,
      )
      this.selectedGroupId = this.config.groups[0]?.group_id ?? UNGROUPED_GROUP.group_id
      this.currentPage = 1
    },

    upsertSource(source: DataSource, originalId?: string): void {
      const sourceCopy = { ...source, id: source.id.trim(), pathOrUrl: source.pathOrUrl?.trim() }
      const affectedSourceIds = new Set<string>([sourceCopy.id])

      if (originalId) {
        affectedSourceIds.add(originalId)
      }

      if (originalId && originalId !== sourceCopy.id) {
        const index = this.config.sources.findIndex((item) => item.id === originalId)
        if (index >= 0) {
          this.config.sources.splice(index, 1, sourceCopy)
          this.config.variables = this.config.variables.map((variable) =>
            variable.source_id === originalId ? { ...variable, source_id: sourceCopy.id } : variable,
          )
          this.preferredSourceId = sourceCopy.id
          this.invalidateSourceArtifacts([...affectedSourceIds])
          return
        }
      }

      const index = this.config.sources.findIndex((item) => item.id === sourceCopy.id)
      if (index >= 0) {
        this.config.sources.splice(index, 1, sourceCopy)
      } else {
        this.config.sources.unshift(sourceCopy)
      }

      this.preferredSourceId = sourceCopy.id
      this.invalidateSourceArtifacts([...affectedSourceIds])
    },

    removeSource(sourceId: string): void {
      const removedTags = new Set(
        this.config.variables
          .filter((variable) => variable.source_id === sourceId)
          .map((variable) => variable.tag),
      )

      this.config.sources = this.config.sources.filter((source) => source.id !== sourceId)
      this.config.variables = this.config.variables.filter((variable) => variable.source_id !== sourceId)
      this.config.rules = pruneRulesByRemovedTags(this.config.rules, removedTags)
      this.invalidateSourceArtifacts([sourceId])

      removedTags.forEach((tag) => {
        delete this.variablePreviewMap[tag]
      })

      if (this.activeTag && removedTags.has(this.activeTag)) {
        this.activeTag = null
      }

      if (this.preferredSourceId === sourceId) {
        this.preferredSourceId = this.config.sources[0]?.id ?? null
      }

      const pageCount = Math.max(1, Math.ceil(this.currentGroupRuleTotal / FIXED_RULES_PAGE_SIZE))
      if (this.currentPage > pageCount) {
        this.currentPage = pageCount
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
      const nextTag = variable.tag.trim()
      const variableCopy: VariableTag = {
        ...variable,
        tag: nextTag,
        source_id: variable.source_id.trim(),
        sheet: variable.sheet,
        column: variable.column,
        columns: variable.columns ? [...variable.columns] : undefined,
        key_column: variable.key_column,
        append_index_to_key: variable.append_index_to_key ?? false,
      }

      if (originalTag && originalTag !== nextTag) {
        const index = this.config.variables.findIndex((item) => item.tag === originalTag)
        if (index >= 0) {
          this.config.variables.splice(index, 1, variableCopy)
          this.config.rules = this.config.rules.map((rule) =>
            rule.target_variable_tag === originalTag
              ? { ...rule, target_variable_tag: nextTag }
              : rule,
          )
          delete this.variablePreviewMap[originalTag]
          if (this.activeTag === originalTag) {
            this.activeTag = nextTag
          }
          return
        }
      }

      const index = this.config.variables.findIndex((item) => item.tag === nextTag)
      if (index >= 0) {
        this.config.variables.splice(index, 1, variableCopy)
      } else {
        this.config.variables.push(variableCopy)
      }
    },

    removeVariable(tag: string): void {
      const removedTags = new Set([tag])
      this.config.variables = this.config.variables.filter((variable) => variable.tag !== tag)
      this.config.rules = pruneRulesByRemovedTags(this.config.rules, removedTags)
      delete this.variablePreviewMap[tag]

      if (this.activeTag === tag) {
        this.activeTag = null
      }

      const pageCount = Math.max(1, Math.ceil(this.currentGroupRuleTotal / FIXED_RULES_PAGE_SIZE))
      if (this.currentPage > pageCount) {
        this.currentPage = pageCount
      }
    },

    upsertRule(rule: Omit<FixedRuleDefinition, 'rule_id'> & { rule_id?: string }): void {
      const normalizedCompositeConfig =
        rule.rule_type === 'composite_condition_check'
          ? normalizeCompositeConfig(rule.composite_config)
          : undefined
      const normalizedPipelineConfig =
        rule.rule_type === 'multi_composite_pipeline_check'
          ? normalizeMultiCompositePipelineConfig(rule.pipeline_config)
          : undefined
      const variableMap = new Map(this.config.variables.map((variable) => [variable.tag, variable] as const))
      const targetVariable = variableMap.get(rule.target_variable_tag.trim())
      const referenceVariable =
        rule.rule_type === 'dual_composite_compare'
          ? variableMap.get(rule.reference_variable_tag?.trim() ?? '')
          : undefined
      const targetFields = [
        '__key__',
        ...((targetVariable?.columns ?? []).filter((column) => Boolean(column && column.trim()))),
      ]
      const referenceFields = [
        '__key__',
        ...((referenceVariable?.columns ?? []).filter((column) => Boolean(column && column.trim()))),
      ]

      const nextRule: FixedRuleDefinition = {
        rule_id: rule.rule_id ?? createEntityId('fixed-rule'),
        group_id: rule.group_id,
        rule_name: rule.rule_name.trim(),
        target_variable_tag: rule.target_variable_tag.trim(),
        rule_type: rule.rule_type,
        operator: rule.rule_type === 'fixed_value_compare' ? rule.operator : undefined,
        expected_value:
          rule.rule_type === 'fixed_value_compare' || rule.rule_type === 'regex_check'
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
        pipeline_config: normalizedPipelineConfig,
        key_check_mode:
          rule.rule_type === 'dual_composite_compare'
            ? rule.key_check_mode ?? 'baseline_only'
            : undefined,
        comparisons:
          rule.rule_type === 'dual_composite_compare'
            ? (rule.comparisons ?? []).map((comparison) => ({
                comparison_id: comparison.comparison_id,
                left_field:
                  resolveFieldAgainstAvailable(comparison.left_field, targetFields) ??
                  comparison.left_field.trim(),
                operator: comparison.operator,
                right_field:
                  resolveFieldAgainstAvailable(comparison.right_field, referenceFields) ??
                  comparison.right_field.trim(),
              }))
            : [],
      }

      const index = this.config.rules.findIndex((item) => item.rule_id === nextRule.rule_id)
      if (index >= 0) {
        this.config.rules.splice(index, 1, nextRule)
      } else {
        this.config.rules.push(nextRule)
      }
    },

    removeRule(ruleId: string): void {
      this.config.rules = this.config.rules.filter((rule) => rule.rule_id !== ruleId)
      const pageCount = Math.max(1, Math.ceil(this.currentGroupRuleTotal / FIXED_RULES_PAGE_SIZE))
      if (this.currentPage > pageCount) {
        this.currentPage = pageCount
      }
    },

    setSelectedPathReplacementPreset(path: string | null): void {
      this.config.selected_path_replacement_preset = path
        ? normalizeReplacementPreset(path)
        : null
    },

    addPathReplacementPreset(path: string): void {
      const normalizedPath = normalizeReplacementPreset(path)
      if (!normalizedPath) {
        return
      }

      const presetMap = new Map(
        this.config.path_replacement_presets.map((preset) => [preset.toLowerCase(), preset] as const),
      )
      if (!presetMap.has(normalizedPath.toLowerCase())) {
        presetMap.set(normalizedPath.toLowerCase(), normalizedPath)
        this.config.path_replacement_presets = [...presetMap.values()]
      }
    },

    async replaceSourceBasePath(baseDirectory: string): Promise<{
      updatedCount: number
      skippedCount: number
      failedCount: number
      affectedSourceIds: string[]
    }> {
      const normalizedBaseDirectory = normalizeReplacementPreset(baseDirectory)
      const candidateSources: Array<{
        sourceId: string
        source: DataSource
        nextSource: DataSource
        nextPath: string
      }> = []
      const affectedSourceIds = new Set<string>()
      let updatedCount = 0
      let skippedCount = 0

      this.sources.slice().forEach((source) => {
        if (!isLocalFileSource(source)) {
          skippedCount += 1
          return
        }

        const basename = extractSourceBasename(getSourceLocator(source))
        if (!basename) {
          skippedCount += 1
          return
        }

        const nextPath = joinDirectoryAndBasename(normalizedBaseDirectory, basename)
        candidateSources.push({
          sourceId: source.id,
          source,
          nextSource: {
            ...source,
            path: nextPath,
            pathOrUrl: nextPath,
          },
          nextPath,
        })
      })

      if (!candidateSources.length) {
        return {
          updatedCount,
          skippedCount,
          failedCount: 0,
          affectedSourceIds: [],
        }
      }

      const validationFailures: string[] = []
      const metadataValidatedSourceIds = new Set<string>()
      for (const candidate of candidateSources) {
        try {
          await fetchSourceMetadata(candidate.nextSource)
          metadataValidatedSourceIds.add(candidate.sourceId)
        } catch (error) {
          const reason =
            error instanceof Error ? error.message : '读取数据源元数据失败。'
          validationFailures.push(
            `- ${candidate.sourceId} -> ${candidate.nextPath}：${reason}`,
          )
        }
      }

      for (const candidate of candidateSources) {
        if (!metadataValidatedSourceIds.has(candidate.sourceId)) {
          continue
        }
        const affectedVariables = this.variables.filter(
          (variable) => variable.source_id === candidate.sourceId,
        )

        for (const variable of affectedVariables) {
          const isComposite = (variable.variable_kind ?? 'single') === 'composite'
          try {
            if (isComposite) {
              await fetchCompositePreview({
                source: candidate.nextSource,
                sheet: variable.sheet,
                columns: variable.columns ?? [],
                key_column: variable.key_column ?? '',
                append_index_to_key: variable.append_index_to_key ?? false,
              })
            } else {
              await fetchColumnPreview({
                source: candidate.nextSource,
                sheet: variable.sheet,
                column: variable.column ?? '',
              })
            }
          } catch (error) {
            const reason =
              error instanceof Error ? error.message : '变量预览校验失败。'
            validationFailures.push(
              `- ${candidate.sourceId} / ${variable.tag}：${reason}`,
            )
          }
        }
      }

      if (validationFailures.length) {
        throw new Error(
          [
            '以下数据源路径替换失败，本次未生效：',
            ...validationFailures,
          ].join('\n'),
        )
      }

      candidateSources.forEach((candidate) => {
        this.upsertSource(candidate.nextSource, candidate.sourceId)
        affectedSourceIds.add(candidate.sourceId)
        updatedCount += 1
      })

      this.addPathReplacementPreset(normalizedBaseDirectory)
      this.setSelectedPathReplacementPreset(normalizedBaseDirectory)
      await this.saveConfig()

      let failedCount = 0
      for (const sourceId of affectedSourceIds) {
        try {
          await this.loadSourceMetadata(sourceId)
        } catch {
          failedCount += 1
        }
      }

      const activeVariable = this.variables.find((variable) => variable.tag === this.activeTag)
      if (isAffectedVariable(activeVariable, affectedSourceIds)) {
        try {
          await this.loadVariablePreview(activeVariable, undefined, true)
        } catch {
          // 具体问题会由 configIssues 和数据源行提示呈现，这里只保持交互不中断。
        }
      }

      this.clearExecutionResult()
      this.clearPageError()

      return {
        updatedCount,
        skippedCount,
        failedCount,
        affectedSourceIds: [...affectedSourceIds],
      }
    },
  },
})

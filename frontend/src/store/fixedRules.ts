import { defineStore } from 'pinia'

import {
  executeFixedRules,
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
  CompositeBranch,
  CompositeCondition,
  CompositeRuleConfig,
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
import { SAMPLE_SOURCE_PATH } from '../utils/workbenchMeta'

const UNGROUPED_GROUP: FixedRuleGroup = {
  group_id: 'ungrouped',
  group_name: '未分组',
  builtin: true,
}

const FIXED_RULES_PAGE_SIZE = 20

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
  isUpdatingSvn: boolean
  pageError: string
  configIssues: FixedRulesConfigIssue[]
  executionMeta: ExecutionMeta | null
  abnormalResults: AbnormalResult[]
  svnUpdateResults: FixedRulesSvnUpdateItem[]
  svnUpdateSummary: string
}

function createDefaultConfig(): FixedRulesConfig {
  return {
    version: 4,
    configured: false,
    sources: [],
    variables: [],
    groups: [{ ...UNGROUPED_GROUP }],
    rules: [],
  }
}

function createEntityId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function ensureDefaultGroup(groups: FixedRuleGroup[]): FixedRuleGroup[] {
  const normalized = groups.filter((group) => group.group_id !== UNGROUPED_GROUP.group_id)
  return [{ ...UNGROUPED_GROUP }, ...normalized]
}

function normalizeExpectedValue(value: string | undefined): string | undefined {
  const normalized = value?.trim() ?? ''
  return normalized ? normalized : undefined
}

function isCompareOperator(value: string | undefined): value is FixedRuleDefinition['operator'] {
  return value === 'eq' || value === 'ne' || value === 'gt' || value === 'lt'
}

function isSingleVariable(variable: VariableTag | undefined | null): variable is VariableTag {
  return variable != null && (variable.variable_kind ?? 'single') === 'single'
}

function isCompositeVariable(variable: VariableTag | undefined | null): variable is VariableTag {
  return variable != null && (variable.variable_kind ?? 'single') === 'composite'
}

function createConditionId(): string {
  return createEntityId('condition')
}

function createBranchId(): string {
  return createEntityId('branch')
}

function normalizeCompositeCondition(condition: CompositeCondition): CompositeCondition {
  const operator = condition.operator
  const normalizedField = condition.field.trim()
  const normalizedConditionId = condition.condition_id.trim() || createConditionId()

  if (isCompareOperator(operator)) {
    const valueSource = condition.value_source === 'field' ? 'field' : 'literal'
    return {
      condition_id: normalizedConditionId,
      field: normalizedField,
      operator,
      value_source: valueSource,
      expected_value:
        valueSource === 'literal' ? normalizeExpectedValue(condition.expected_value) : undefined,
      expected_field: valueSource === 'field' ? condition.expected_field?.trim() : undefined,
    }
  }

  return {
    condition_id: normalizedConditionId,
    field: normalizedField,
    operator,
  }
}

function normalizeCompositeBranch(branch: CompositeBranch): CompositeBranch {
  return {
    branch_id: branch.branch_id.trim() || createBranchId(),
    filters: branch.filters.map(normalizeCompositeCondition),
    assertions: branch.assertions.map(normalizeCompositeCondition),
  }
}

function normalizeCompositeConfig(
  config: CompositeRuleConfig | undefined,
): CompositeRuleConfig | undefined {
  if (!config) {
    return undefined
  }

  return {
    global_filters: config.global_filters.map(normalizeCompositeCondition),
    branches: config.branches.map(normalizeCompositeBranch),
  }
}

function isValidCompositeCondition(
  condition: CompositeCondition,
  section: 'filter' | 'assertion',
): boolean {
  const normalizedField = condition.field.trim()
  const normalizedConditionId = condition.condition_id.trim()
  if (!normalizedConditionId || !normalizedField) {
    return false
  }

  const operator = condition.operator
  if (section === 'filter' && (operator === 'unique' || operator === 'duplicate_required')) {
    return false
  }

  if (operator === 'not_null' || operator === 'unique' || operator === 'duplicate_required') {
    return true
  }

  if (!isCompareOperator(operator)) {
    return false
  }

  if (condition.value_source === 'field') {
    return Boolean(condition.expected_field?.trim())
  }

  return Boolean(normalizeExpectedValue(condition.expected_value))
}

function isValidCompositeConfig(config: CompositeRuleConfig | undefined): boolean {
  if (!config) {
    return false
  }

  if (!config.global_filters.every((condition) => isValidCompositeCondition(condition, 'filter'))) {
    return false
  }

  if (!config.branches.length) {
    return false
  }

  return config.branches.every(
    (branch) =>
      Boolean(branch.branch_id.trim()) &&
      branch.filters.every((condition) => isValidCompositeCondition(condition, 'filter')) &&
      branch.assertions.length > 0 &&
      branch.assertions.every((condition) => isValidCompositeCondition(condition, 'assertion')),
  )
}

function collectVariableTagsBySourceIds(
  variables: VariableTag[],
  sourceIds: Set<string>,
): string[] {
  return variables
    .filter((variable) => sourceIds.has(variable.source_id))
    .map((variable) => variable.tag)
}

function pruneRulesByRemovedTags(
  rules: FixedRuleDefinition[],
  removedTags: Set<string>,
): FixedRuleDefinition[] {
  if (!removedTags.size) {
    return rules
  }

  return rules.filter((rule) => !removedTags.has(rule.target_variable_tag))
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
    isUpdatingSvn: false,
    pageError: '',
    configIssues: [],
    executionMeta: null,
    abnormalResults: [],
    svnUpdateResults: [],
    svnUpdateSummary: '',
  }),

  getters: {
    sources(state): DataSource[] {
      return state.config.sources
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
            if (rule.rule_type === 'composite_condition_check') {
              return true
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

          if (rule.rule_type !== 'composite_condition_check') {
            return true
          }

          return !isValidCompositeConfig(rule.composite_config)
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
    clearPageError(): void {
      this.pageError = ''
    },

    clearExecutionResult(): void {
      this.executionMeta = null
      this.abnormalResults = []
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
      this.config = {
        ...config,
        version: 4,
        groups: ensureDefaultGroup(config.groups),
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
        this.pageError = error instanceof Error ? error.message : '读取固定规则配置失败。'
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
          version: 4,
          groups: ensureDefaultGroup(this.config.groups),
        })
        this.applyConfig(response.data)
        this.configIssues = []
        return response.data
      } catch (error) {
        this.pageError = error instanceof Error ? error.message : '保存固定规则配置失败。'
        throw error
      } finally {
        this.isSaving = false
      }
    },

    async executeConfig(): Promise<void> {
      this.isExecuting = true
      this.pageError = ''

      try {
        await this.saveConfig()
        const response = await executeFixedRules()
        this.executionMeta = response.meta
        this.abnormalResults = response.data.abnormal_results
      } catch (error) {
        this.executionMeta = null
        this.abnormalResults = []
        this.pageError = error instanceof Error ? error.message : '执行固定规则失败。'
        throw error
      } finally {
        this.isExecuting = false
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
        sheet: variable.sheet.trim(),
        column: variable.column?.trim(),
        columns: variable.columns ? [...variable.columns] : undefined,
        key_column: variable.key_column?.trim(),
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

      const nextRule: FixedRuleDefinition = {
        rule_id: rule.rule_id ?? createEntityId('fixed-rule'),
        group_id: rule.group_id,
        rule_name: rule.rule_name.trim(),
        target_variable_tag: rule.target_variable_tag.trim(),
        rule_type: rule.rule_type,
        operator: rule.rule_type === 'fixed_value_compare' ? rule.operator : undefined,
        expected_value:
          rule.rule_type === 'fixed_value_compare'
            ? normalizeExpectedValue(rule.expected_value)
            : undefined,
        composite_config: normalizedCompositeConfig,
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
  },
})

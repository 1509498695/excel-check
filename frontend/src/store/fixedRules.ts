import { defineStore } from 'pinia'

import {
  executeFixedRules,
  fetchFixedRulesConfig,
  saveFixedRulesConfig,
  triggerFixedRulesSvnUpdate,
} from '../api/fixedRules'
import { fetchSourceMetadata } from '../api/workbench'
import type {
  FixedRuleBinding,
  FixedRuleDefinition,
  FixedRuleGroup,
  FixedRulesConfig,
  FixedRulesSvnUpdateItem,
} from '../types/fixedRules'
import type { AbnormalResult, ExecutionMeta, SourceMetadata } from '../types/workbench'

const UNGROUPED_GROUP: FixedRuleGroup = {
  group_id: 'ungrouped',
  group_name: '未分组',
  builtin: true,
}

const FIXED_RULES_SOURCE_ID = 'fixed_rules_meta'
const FIXED_RULES_PAGE_SIZE = 20

interface FixedRulesState {
  config: FixedRulesConfig
  metadataCache: Record<string, SourceMetadata>
  selectedGroupId: string
  groupKeyword: string
  currentPage: number
  isLoading: boolean
  isSaving: boolean
  isExecuting: boolean
  isUpdatingSvn: boolean
  pageError: string
  executionMeta: ExecutionMeta | null
  abnormalResults: AbnormalResult[]
  svnUpdateResults: FixedRulesSvnUpdateItem[]
  svnUpdateSummary: string
}

function createDefaultConfig(): FixedRulesConfig {
  return {
    version: 2,
    configured: false,
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

function normalizePathCacheKey(filePath: string): string {
  return filePath.trim()
}

function buildMetadataSource(filePath: string) {
  return {
    id: FIXED_RULES_SOURCE_ID,
    type: 'local_excel' as const,
    path: filePath,
    pathOrUrl: filePath,
  }
}

function normalizeBinding(binding: FixedRuleBinding): FixedRuleBinding {
  return {
    file_path: binding.file_path.trim(),
    sheet: binding.sheet.trim(),
    column: binding.column.trim(),
  }
}

export const useFixedRulesStore = defineStore('fixed-rules', {
  state: (): FixedRulesState => ({
    config: createDefaultConfig(),
    metadataCache: {},
    selectedGroupId: UNGROUPED_GROUP.group_id,
    groupKeyword: '',
    currentPage: 1,
    isLoading: false,
    isSaving: false,
    isExecuting: false,
    isUpdatingSvn: false,
    pageError: '',
    executionMeta: null,
    abnormalResults: [],
    svnUpdateResults: [],
    svnUpdateSummary: '',
  }),

  getters: {
    allGroups(state): FixedRuleGroup[] {
      return ensureDefaultGroup(state.config.groups)
    },

    filteredGroups(): FixedRuleGroup[] {
      const keyword = this.groupKeyword.trim().toLowerCase()
      if (!keyword) {
        return this.allGroups
      }

      return this.allGroups.filter((group) =>
        group.group_name.toLowerCase().includes(keyword),
      )
    },

    selectedGroup(): FixedRuleGroup {
      return (
        this.allGroups.find((group) => group.group_id === this.selectedGroupId) ??
        this.allGroups[0]
      )
    },

    groupRuleCounts(state): Record<string, number> {
      return state.config.rules.reduce<Record<string, number>>((accumulator, rule) => {
        accumulator[rule.group_id] = (accumulator[rule.group_id] ?? 0) + 1
        return accumulator
      }, {})
    },

    configuredPaths(state): string[] {
      const seen = new Set<string>()
      const paths: string[] = []
      state.config.rules.forEach((rule) => {
        const filePath = rule.binding.file_path.trim()
        if (!filePath || seen.has(filePath)) {
          return
        }
        seen.add(filePath)
        paths.push(filePath)
      })
      return paths
    },

    pathCount(): number {
      return this.configuredPaths.length
    },

    invalidRuleIds(state): string[] {
      const validGroupIds = new Set(ensureDefaultGroup(state.config.groups).map((group) => group.group_id))

      return state.config.rules
        .filter((rule) => {
          if (!validGroupIds.has(rule.group_id)) {
            return true
          }
          if (!rule.rule_name.trim()) {
            return true
          }
          if (!rule.binding.file_path.trim() || !rule.binding.sheet.trim() || !rule.binding.column.trim()) {
            return true
          }
          if (!rule.expected_value.trim()) {
            return true
          }
          if (!/\.xlsx?$/i.test(rule.binding.file_path.trim())) {
            return true
          }
          if ((rule.operator === 'gt' || rule.operator === 'lt') && Number.isNaN(Number(rule.expected_value))) {
            return true
          }
          return false
        })
        .map((rule) => rule.rule_id)
    },

    currentGroupRules(state): FixedRuleDefinition[] {
      const groupId = this.selectedGroup.group_id
      return state.config.rules.filter((rule) => rule.group_id === groupId)
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

    totalRuleCount(state): number {
      return state.config.rules.length
    },

    invalidGroupIds(): string[] {
      const invalidRuleIds = new Set(this.invalidRuleIds)
      const invalidGroupIds = new Set<string>()

      this.config.rules.forEach((rule) => {
        if (invalidRuleIds.has(rule.rule_id)) {
          invalidGroupIds.add(rule.group_id)
        }
      })

      return [...invalidGroupIds]
    },

    canRunSvnUpdate(): boolean {
      return this.pathCount > 0
    },

    canExecute(): boolean {
      return this.config.rules.length > 0 && this.invalidRuleIds.length === 0
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

    getMetadataByPath(filePath: string): SourceMetadata | null {
      const cacheKey = normalizePathCacheKey(filePath)
      return this.metadataCache[cacheKey] ?? null
    },

    applyConfig(config: FixedRulesConfig): void {
      this.config = {
        ...config,
        groups: ensureDefaultGroup(config.groups),
      }

      if (!this.config.groups.some((group) => group.group_id === this.selectedGroupId)) {
        this.selectedGroupId = this.config.groups[0]?.group_id ?? UNGROUPED_GROUP.group_id
      }

      this.currentPage = 1
    },

    async loadMetadataForPath(filePath: string): Promise<SourceMetadata | null> {
      const normalizedPath = normalizePathCacheKey(filePath)
      if (!normalizedPath) {
        return null
      }

      const cached = this.metadataCache[normalizedPath]
      if (cached) {
        return cached
      }

      const response = await fetchSourceMetadata(buildMetadataSource(normalizedPath))
      this.metadataCache = {
        ...this.metadataCache,
        [normalizedPath]: response.data,
      }
      return response.data
    },

    async loadConfig(): Promise<void> {
      this.isLoading = true
      this.pageError = ''

      try {
        const response = await fetchFixedRulesConfig()
        this.applyConfig(response.data)
      } catch (error) {
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
          groups: ensureDefaultGroup(this.config.groups),
        })
        this.applyConfig(response.data)
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

    upsertRule(rule: Omit<FixedRuleDefinition, 'rule_id'> & { rule_id?: string }): void {
      const nextRule: FixedRuleDefinition = {
        rule_id: rule.rule_id ?? createEntityId('fixed-rule'),
        group_id: rule.group_id,
        rule_name: rule.rule_name.trim(),
        binding: normalizeBinding(rule.binding),
        operator: rule.operator,
        expected_value: rule.expected_value.trim(),
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

import { defineStore } from 'pinia'

import {
  executeTaskTree,
  fetchColumnPreview,
  fetchCompositePreview,
  fetchSourceCapabilities,
  fetchSourceMetadata,
} from '../api/workbench'
import type {
  AbnormalResult,
  DataSource,
  ExecutionMeta,
  RuleMode,
  SourceMetadata,
  SourceType,
  TaskTree,
  ValidationRule,
  VariablePreviewData,
  VariableTag,
} from '../types/workbench'
import { buildTaskTreePayload, createRuleId } from '../utils/taskTree'
import { SAMPLE_SOURCE_PATH } from '../utils/workbenchMeta'

interface WorkbenchState {
  sources: DataSource[]
  variables: VariableTag[]
  rules: ValidationRule[]
  capabilities: SourceType[]
  isExecuting: boolean
  pageError: string
  abnormalResults: AbnormalResult[]
  executionMeta: ExecutionMeta | null
  activeTag: string | null
  preferredSourceId: string | null
  sourceMetadataMap: Record<string, SourceMetadata>
  variablePreviewMap: Record<string, VariablePreviewData>
}

function pruneRules(rules: ValidationRule[], removedTags: Set<string>): ValidationRule[] {
  return rules.flatMap((rule) => {
    if (rule.rule_type === 'not_null' || rule.rule_type === 'unique') {
      const targetTags = Array.isArray(rule.params.target_tags)
        ? rule.params.target_tags.filter(
            (item): item is string => typeof item === 'string' && !removedTags.has(item),
          )
        : []

      if (targetTags.length === 0) {
        return []
      }

      return [{ ...rule, params: { target_tags: targetTags } }]
    }

    if (rule.rule_type === 'cross_table_mapping') {
      const dictTag = typeof rule.params.dict_tag === 'string' ? rule.params.dict_tag : ''
      const targetTag = typeof rule.params.target_tag === 'string' ? rule.params.target_tag : ''

      if (removedTags.has(dictTag) || removedTags.has(targetTag)) {
        return []
      }
    }

    return [rule]
  })
}

function createStaticRule(ruleType: string): ValidationRule {
  if (ruleType === 'cross_table_mapping') {
    return {
      rule_id: createRuleId('rule'),
      rule_type: ruleType,
      params: {
        dict_tag: '',
        target_tag: '',
      },
      mode: 'static',
    }
  }

  return {
    rule_id: createRuleId('rule'),
    rule_type: ruleType,
    params: {
      target_tags: [],
    },
    mode: 'static',
  }
}

function createDynamicRule(): ValidationRule {
  return {
    rule_id: createRuleId('rule'),
    rule_type: '',
    params: {},
    mode: 'dynamic',
    draftState: {
      paramsText: '{\n  \n}',
    },
  }
}

function createSampleStaticRules(): ValidationRule[] {
  return [
    {
      rule_id: createRuleId('rule'),
      rule_type: 'not_null',
      params: {
        target_tags: ['[items-id]'],
      },
      mode: 'static',
    },
    {
      rule_id: createRuleId('rule'),
      rule_type: 'unique',
      params: {
        target_tags: ['[items-id]'],
      },
      mode: 'static',
    },
    {
      rule_id: createRuleId('rule'),
      rule_type: 'cross_table_mapping',
      params: {
        dict_tag: '[items-id]',
        target_tag: '[drops-ref]',
      },
      mode: 'static',
    },
  ]
}

function collectVariableTagsBySourceIds(
  variables: VariableTag[],
  sourceIds: Set<string>,
): string[] {
  return variables
    .filter((variable) => sourceIds.has(variable.source_id))
    .map((variable) => variable.tag)
}

export const useWorkbenchStore = defineStore('workbench', {
  state: (): WorkbenchState => ({
    sources: [],
    variables: [],
    rules: [],
    capabilities: [],
    isExecuting: false,
    pageError: '',
    abnormalResults: [],
    executionMeta: null,
    activeTag: null,
    preferredSourceId: null,
    sourceMetadataMap: {},
    variablePreviewMap: {},
  }),

  getters: {
    taskTree(state): TaskTree {
      return {
        sources: state.sources,
        variables: state.variables,
        rules: state.rules.filter((rule) => rule.mode !== 'dynamic'),
      }
    },

    staticRules(state): ValidationRule[] {
      return state.rules.filter((rule) => rule.mode !== 'dynamic')
    },

    dynamicRules(state): ValidationRule[] {
      return state.rules.filter((rule) => rule.mode === 'dynamic')
    },

    singleVariables(state): VariableTag[] {
      return state.variables.filter((variable) => (variable.variable_kind ?? 'single') === 'single')
    },

    resultCount(state): number {
      return state.abnormalResults.length
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
      this.rules = pruneRules(this.rules, removedTags)
      this.invalidateSourceArtifacts([sourceId])

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
      const variableCopy = { ...variable }

      if (originalTag) {
        const index = this.variables.findIndex((item) => item.tag === originalTag)
        if (index >= 0) {
          this.variables.splice(index, 1, variableCopy)
          delete this.variablePreviewMap[originalTag]
          delete this.variablePreviewMap[variableCopy.tag]

          if (originalTag !== variable.tag) {
            this.replaceTagInRules(originalTag, variable.tag)
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
      this.rules = pruneRules(this.rules, new Set([tag]))
      delete this.variablePreviewMap[tag]

      if (this.activeTag === tag) {
        this.activeTag = null
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
      this.abnormalResults = []
      this.activeTag = '[items-id]'
      this.sourceMetadataMap = {}
      this.variablePreviewMap = {}

      this.sources = []
      this.variables = []

      this.useSampleSource()
      this.useSampleVariables()

      const dynamicRules = this.rules.filter((rule) => rule.mode === 'dynamic')
      this.rules = [...createSampleStaticRules(), ...dynamicRules]
    },

    addStaticRule(ruleType: string): void {
      this.rules.push(createStaticRule(ruleType))
    },

    addDynamicRule(): void {
      this.rules.push(createDynamicRule())
    },

    removeRule(ruleId?: string): void {
      this.rules = this.rules.filter((rule) => rule.rule_id !== ruleId)
    },

    updateRuleMode(ruleId: string, mode: RuleMode): void {
      const target = this.rules.find((rule) => rule.rule_id === ruleId)
      if (!target) {
        return
      }

      target.mode = mode
    },

    updateRuleType(ruleId: string, ruleType: string): void {
      const target = this.rules.find((rule) => rule.rule_id === ruleId)
      if (!target) {
        return
      }

      target.rule_type = ruleType
    },

    updateRuleParams(ruleId: string, params: Record<string, unknown>): void {
      const target = this.rules.find((rule) => rule.rule_id === ruleId)
      if (!target) {
        return
      }

      target.params = { ...params }
    },

    updateRuleDraftText(ruleId: string, paramsText: string): void {
      const target = this.rules.find((rule) => rule.rule_id === ruleId)
      if (!target) {
        return
      }

      target.draftState = {
        ...target.draftState,
        paramsText,
      }
    },

    replaceTagInRules(previousTag: string, nextTag: string): void {
      this.rules = this.rules.map((rule) => {
        if (rule.rule_type === 'not_null' || rule.rule_type === 'unique') {
          const targetTags = Array.isArray(rule.params.target_tags)
            ? rule.params.target_tags.map((item) => (item === previousTag ? nextTag : item))
            : []

          return {
            ...rule,
            params: {
              target_tags: targetTags,
            },
          }
        }

        if (rule.rule_type === 'cross_table_mapping') {
          const dictTag = rule.params.dict_tag === previousTag ? nextTag : rule.params.dict_tag
          const targetTag =
            rule.params.target_tag === previousTag ? nextTag : rule.params.target_tag

          return {
            ...rule,
            params: {
              dict_tag: dictTag,
              target_tag: targetTag,
            },
          }
        }

        return rule
      })
    },

    buildTaskTreePayload(): TaskTree {
      return buildTaskTreePayload(this.sources, this.variables, this.staticRules)
    },

    async executeValidation(): Promise<void> {
      this.pageError = ''
      this.isExecuting = true

      try {
        const payload = this.buildTaskTreePayload()
        const response = await executeTaskTree(payload)
        this.executionMeta = response.meta
        this.abnormalResults = response.data.abnormal_results
      } catch (error) {
        this.executionMeta = null
        this.abnormalResults = []
        this.pageError = error instanceof Error ? error.message : '执行校验失败。'
        throw error
      } finally {
        this.isExecuting = false
      }
    },
  },
})

import { computed, reactive, ref } from 'vue'
import { commitWorkbenchImport, fetchWorkbenchImportDraft, previewWorkbenchImport } from './api'
import type {
  DataSource,
} from '../../types/workbench'
import type {
  DuplicateRuleAction,
  ImportConflictResolutions,
  ImportScopeMode,
  SourceMapping,
  WorkbenchImportDraft,
  WorkbenchImportPreview,
  WorkbenchImportPreviewRequest,
} from './types'

export interface UsePersonalRulesImportOptions {
  initialRuleIds?: (() => string[]) | string[]
  initialGroupIds?: (() => string[]) | string[]
  defaultScopeMode?: ImportScopeMode
}

function resolveArrayOption(option?: (() => string[]) | string[]): string[] {
  if (!option) {
    return []
  }
  return [...(typeof option === 'function' ? option() : option)]
}

function cloneSourceMappingFromDraft(draft: WorkbenchImportDraft): SourceMapping[] {
  return draft.source_mappings.map((mapping) => ({
    personal_source_id: mapping.personal_source.id,
    action: mapping.recommended_action,
    project_source_id: mapping.project_source_id ?? null,
    next_source: mapping.next_source ? { ...mapping.next_source } : { ...mapping.personal_source },
    confirmed: true,
  }))
}

function sourceLocator(source?: DataSource | null): string {
  return (source?.pathOrUrl || source?.path || source?.url || '').trim()
}

function normalizeSourceWithLocator(source: DataSource, locator: string): DataSource {
  const nextSource = { ...source, pathOrUrl: locator }
  if (source.type === 'feishu') {
    nextSource.url = locator
    return nextSource
  }
  nextSource.path = locator
  return nextSource
}

export function usePersonalRulesImport(options: UsePersonalRulesImportOptions = {}) {
  const isLoading = ref(false)
  const isPreviewing = ref(false)
  const isCommitting = ref(false)
  const errorMessage = ref('')
  const draft = ref<WorkbenchImportDraft | null>(null)
  const preview = ref<WorkbenchImportPreview | null>(null)
  const scope = reactive<{
    mode: ImportScopeMode
    group_ids: string[]
    rule_ids: string[]
  }>({
    mode: options.defaultScopeMode ?? 'groups',
    group_ids: [],
    rule_ids: [],
  })
  const sourceMappings = ref<SourceMapping[]>([])
  const duplicateRuleActions = reactive<Record<string, DuplicateRuleAction>>({})
  const conflictResolutions = reactive<Required<ImportConflictResolutions>>({
    variable_tags: {},
    rule_names: {},
    group_names: {},
  })
  const isPreviewStale = ref(false)
  let previewRefreshTimer: ReturnType<typeof setTimeout> | null = null

  const scopeError = computed(() => {
    if (!draft.value?.importable_rules.length) {
      return '当前个人校验没有可导入规则。'
    }
    if (scope.mode === 'groups' && !scope.group_ids.length) {
      return '请至少选择一个规则组。'
    }
    if (scope.mode === 'rules' && !scope.rule_ids.length) {
      return '请至少选择一条规则。'
    }
    return ''
  })
  const sourceMappingError = computed(() => {
    const riskyDrafts = draft.value?.source_mappings.filter((mapping) => mapping.requires_confirmation) ?? []
    for (const riskyDraft of riskyDrafts) {
      const mapping = sourceMappings.value.find(
        (item) => item.personal_source_id === riskyDraft.personal_source.id,
      )
      if (!mapping?.confirmed) {
        return `请确认高风险数据源“${riskyDraft.personal_source.id}”的映射方式。`
      }
    }
    return ''
  })
  const canPreview = computed(() => !scopeError.value && !sourceMappingError.value)
  const canCommit = computed(
    () => Boolean(preview.value && !preview.value.blocking_errors.length && !isPreviewStale.value),
  )
  const nextDisabledReason = computed(() => scopeError.value || sourceMappingError.value)

  function buildRequest(): WorkbenchImportPreviewRequest {
    const selectedRuleIds = scope.mode === 'rules' ? scope.rule_ids : null
    const selectedGroupIds = scope.mode === 'groups' ? scope.group_ids : null
    return {
      scope: {
        mode: scope.mode,
        group_ids: scope.group_ids,
        rule_ids: scope.rule_ids,
      },
      selected_rule_ids: selectedRuleIds,
      selected_group_ids: selectedGroupIds,
      source_mappings: sourceMappings.value,
      conflict_resolutions: conflictResolutions,
      duplicate_rule_actions: duplicateRuleActions,
    }
  }

  async function loadDraft(): Promise<void> {
    isLoading.value = true
    errorMessage.value = ''
    preview.value = null
    const initialRuleIds = resolveArrayOption(options.initialRuleIds)
    const initialGroupIds = resolveArrayOption(options.initialGroupIds)
    try {
      const response = await fetchWorkbenchImportDraft({
        selected_rule_ids: initialRuleIds.length ? initialRuleIds : undefined,
        selected_group_ids: !initialRuleIds.length && initialGroupIds.length ? initialGroupIds : undefined,
      })
      draft.value = response.data
      sourceMappings.value = cloneSourceMappingFromDraft(response.data)
      clearConflictResolutions()
      clearDuplicateRuleActions()
      scope.mode = initialRuleIds.length
        ? 'rules'
        : initialGroupIds.length
          ? 'groups'
          : options.defaultScopeMode ?? 'groups'
      scope.group_ids = initialGroupIds
      scope.rule_ids = initialRuleIds
      isPreviewStale.value = false
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '读取个人校验配置失败。'
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function runPreview(): Promise<void> {
    isPreviewing.value = true
    errorMessage.value = ''
    try {
      const response = await previewWorkbenchImport(buildRequest())
      preview.value = response.data
      isPreviewStale.value = false
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '导入预览失败。'
      throw error
    } finally {
      isPreviewing.value = false
    }
  }

  async function prepareSummary(): Promise<void> {
    if (!draft.value) {
      await loadDraft()
    }
    sourceMappings.value = sourceMappings.value.map((mapping) => ({
      ...mapping,
      confirmed: true,
    }))
    await runPreview()
  }

  async function commit(): Promise<void> {
    isCommitting.value = true
    errorMessage.value = ''
    try {
      await commitWorkbenchImport(buildRequest())
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '导入提交失败。'
      throw error
    } finally {
      isCommitting.value = false
    }
  }

  function reset(): void {
    draft.value = null
    preview.value = null
    sourceMappings.value = []
    errorMessage.value = ''
    clearConflictResolutions()
    clearDuplicateRuleActions()
    isPreviewStale.value = false
    clearPreviewRefreshTimer()
    scope.mode = options.defaultScopeMode ?? 'groups'
    scope.group_ids = []
    scope.rule_ids = []
  }

  function markPreviewStale(): void {
    isPreviewStale.value = true
  }

  function clearPreviewRefreshTimer(): void {
    if (!previewRefreshTimer) {
      return
    }
    clearTimeout(previewRefreshTimer)
    previewRefreshTimer = null
  }

  function schedulePreviewRefresh(): void {
    markPreviewStale()
    clearPreviewRefreshTimer()
    if (!preview.value || !canPreview.value) {
      return
    }
    previewRefreshTimer = setTimeout(() => {
      void runPreview()
    }, 500)
  }

  function updateSourceLocator(personalSourceId: string, locator: string): void {
    const mappingIndex = sourceMappings.value.findIndex(
      (mapping) => mapping.personal_source_id === personalSourceId,
    )
    if (mappingIndex < 0) {
      return
    }
    const mapping = sourceMappings.value[mappingIndex]
    const draftMapping = draft.value?.source_mappings.find(
      (item) => item.personal_source.id === personalSourceId,
    )
    const baseSource = mapping.next_source ?? draftMapping?.next_source ?? draftMapping?.personal_source
    if (!baseSource) {
      return
    }
    sourceMappings.value[mappingIndex] = {
      ...mapping,
      action: mapping.action === 'reuse' ? 'replace' : mapping.action,
      next_source: normalizeSourceWithLocator(baseSource, locator),
      confirmed: true,
    }
    schedulePreviewRefresh()
  }

  function updateDuplicateRuleAction(ruleId: string, action: DuplicateRuleAction): void {
    duplicateRuleActions[ruleId] = action
    schedulePreviewRefresh()
  }

  function clearConflictResolutions(): void {
    Object.keys(conflictResolutions.variable_tags).forEach((key) => {
      delete conflictResolutions.variable_tags[key]
    })
    Object.keys(conflictResolutions.rule_names).forEach((key) => {
      delete conflictResolutions.rule_names[key]
    })
    Object.keys(conflictResolutions.group_names).forEach((key) => {
      delete conflictResolutions.group_names[key]
    })
  }

  function clearDuplicateRuleActions(): void {
    Object.keys(duplicateRuleActions).forEach((key) => {
      delete duplicateRuleActions[key]
    })
  }

  return {
    isLoading,
    isPreviewing,
    isCommitting,
    errorMessage,
    draft,
    preview,
    scope,
    sourceMappings,
    duplicateRuleActions,
    conflictResolutions,
    isPreviewStale,
    canPreview,
    canCommit,
    nextDisabledReason,
    loadDraft,
    runPreview,
    prepareSummary,
    commit,
    reset,
    markPreviewStale,
    schedulePreviewRefresh,
    updateSourceLocator,
    updateDuplicateRuleAction,
    sourceLocator,
  }
}

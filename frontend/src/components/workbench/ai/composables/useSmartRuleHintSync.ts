import { ref, type Ref } from 'vue'

import { dryRunRulePromptOptimize } from '../../../../api/ai'
import type { AiRuleWorkflowHints, RulePromptOptimizeClues } from '../../../../types/ai'
import {
  extractSmartRuleWorkflowHints,
  type ExtractedSmartRuleHints,
} from '../../../../utils/aiRuleHintExtractor'

const HINT_SYNC_CACHE_LIMIT = 5

interface UseSmartRuleHintSyncOptions {
  description: Ref<string>
  selectedVariableTags: Ref<string[]>
  allowAutoComplete: Ref<boolean>
}

interface CachedHintSync {
  inputHints: ExtractedSmartRuleHints
  workflowHints: AiRuleWorkflowHints
}

export function useSmartRuleHintSync(options: UseSmartRuleHintSyncOptions) {
  const dryRunWorkflowHints = ref<AiRuleWorkflowHints>({})
  const hintSyncCache = new Map<string, CachedHintSync>()

  async function resolveDescriptionHints(): Promise<ExtractedSmartRuleHints> {
    const rawDescription = options.description.value.trim()
    const localHints = extractSmartRuleWorkflowHints(rawDescription)
    if (!rawDescription) {
      clearDryRunWorkflowHints()
      return localHints
    }

    const cacheKey = JSON.stringify({
      rawDescription,
      selectedVariableTags: options.selectedVariableTags.value,
      allowAutoComplete: options.allowAutoComplete.value,
    })
    const cached = hintSyncCache.get(cacheKey)
    if (cached) {
      hintSyncCache.delete(cacheKey)
      hintSyncCache.set(cacheKey, cached)
      dryRunWorkflowHints.value = cloneWorkflowHints(cached.workflowHints)
      return { ...localHints, ...cached.inputHints }
    }

    try {
      const response = await dryRunRulePromptOptimize({
        raw_description: rawDescription,
        selected_variable_tags: options.selectedVariableTags.value,
        allow_auto_complete: options.allowAutoComplete.value,
        context: { page: 'personal_workbench', mode: 'smart_rule_hint_sync' },
      })
      const remoteHints = mapPromptOptimizeCluesToInputHints(response.data.detected_clues)
      const workflowHintPatch = mapPromptOptimizeCluesToWorkflowHints(response.data.detected_clues)
      dryRunWorkflowHints.value = cloneWorkflowHints(workflowHintPatch)
      hintSyncCache.set(cacheKey, {
        inputHints: remoteHints,
        workflowHints: workflowHintPatch,
      })
      while (hintSyncCache.size > HINT_SYNC_CACHE_LIMIT) {
        const oldestKey = hintSyncCache.keys().next().value
        if (!oldestKey) break
        hintSyncCache.delete(oldestKey)
      }
      return { ...localHints, ...remoteHints }
    } catch {
      clearDryRunWorkflowHints()
      return localHints
    }
  }

  function clearDryRunWorkflowHints(): void {
    dryRunWorkflowHints.value = {}
  }

  return {
    dryRunWorkflowHints,
    resolveDescriptionHints,
    clearDryRunWorkflowHints,
  }
}

function mapPromptOptimizeCluesToInputHints(clues: RulePromptOptimizeClues): ExtractedSmartRuleHints {
  const firstFilter = firstPromptOptimizeFilter(clues.filters, 'global')
  return {
    ruleTypeHint: clues.rule_type_hint || undefined,
    targetField: clues.target_field || undefined,
    keyColumn: clues.key_field || undefined,
    filterField: typeof firstFilter?.field === 'string' ? firstFilter.field : undefined,
    filterOperator: typeof firstFilter?.operator === 'string' ? firstFilter.operator : undefined,
    filterValue: typeof firstFilter?.value === 'string' ? firstFilter.value : undefined,
    compareFields: clues.compare_fields.join(','),
    compareOperator: clues.compare_operator || undefined,
  }
}

function mapPromptOptimizeCluesToWorkflowHints(clues: RulePromptOptimizeClues): AiRuleWorkflowHints {
  const globalFilters = clues.filters
    .filter((item) => !item.side || item.side === 'global')
    .map((item) => ({
      field: String(item.field ?? '').trim(),
      operator: normalizePromptOptimizeFilterOperator(item.operator),
      value: String(item.value ?? '').trim(),
    }))
    .filter((item) => item.field && (item.value || item.operator === 'not_null'))
  const leftFilter = firstPromptOptimizeFilter(clues.filters, 'left')
  const rightFilter = firstPromptOptimizeFilter(clues.filters, 'right')
  const patch: AiRuleWorkflowHints = {
    rule_type_hint: clues.rule_type_hint || undefined,
    target_field: clues.target_field || undefined,
    key_column: clues.key_field || undefined,
    compare_fields: clues.compare_fields.length ? [...clues.compare_fields] : undefined,
    compare_operator: clues.compare_operator || undefined,
  }
  if (globalFilters.length) {
    patch.filters = globalFilters
    patch.filter_field = globalFilters[0].field
    patch.filter_operator = globalFilters[0].operator
    patch.filter_value = globalFilters[0].value
  }
  if (leftFilter) {
    patch.left_filter_field = String(leftFilter.field ?? '').trim() || undefined
    patch.left_filter_operator = normalizePromptOptimizeFilterOperator(leftFilter.operator)
    patch.left_filter_value = String(leftFilter.value ?? '').trim() || undefined
  }
  if (rightFilter) {
    patch.right_filter_field = String(rightFilter.field ?? '').trim() || undefined
    patch.right_filter_operator = normalizePromptOptimizeFilterOperator(rightFilter.operator)
    patch.right_filter_value = String(rightFilter.value ?? '').trim() || undefined
  }
  return patch
}

function firstPromptOptimizeFilter(
  filters: Array<Record<string, unknown>>,
  side: 'global' | 'left' | 'right',
): Record<string, unknown> | undefined {
  return filters.find((item) => (side === 'global' ? !item.side || item.side === 'global' : item.side === side))
}

function normalizePromptOptimizeFilterOperator(
  value: unknown,
): NonNullable<AiRuleWorkflowHints['filter_operator']> {
  const operator = typeof value === 'string' ? value : 'eq'
  return ['eq', 'ne', 'gt', 'lt', 'not_null', 'contains', 'not_contains'].includes(operator)
    ? (operator as NonNullable<AiRuleWorkflowHints['filter_operator']>)
    : 'eq'
}

function cloneWorkflowHints(hints: AiRuleWorkflowHints): AiRuleWorkflowHints {
  return JSON.parse(JSON.stringify(hints)) as AiRuleWorkflowHints
}

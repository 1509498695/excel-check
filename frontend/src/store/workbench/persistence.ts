import type { WorkbenchState } from './state'

export function hasSavedWorkbenchContent(state: WorkbenchState): boolean {
  return Boolean(
    state.sources.length ||
      state.variables.length ||
      state.ruleGroups.length > 1 ||
      state.orchestrationRules.length,
  )
}

import type { VariableTag } from '../../types/workbench'

export function normalizeStoredVariable(variable: VariableTag): VariableTag {
  return {
    ...variable,
    append_index_to_key: variable.append_index_to_key ?? false,
  }
}

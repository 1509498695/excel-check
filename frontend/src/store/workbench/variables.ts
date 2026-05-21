import type { VariableTag } from '../../types/workbench'

export function collectTagsBySourceId(variables: VariableTag[], sourceId: string): Set<string> {
  return new Set(
    variables.filter((variable) => variable.source_id === sourceId).map((variable) => variable.tag),
  )
}

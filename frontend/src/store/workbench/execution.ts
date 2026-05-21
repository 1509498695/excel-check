import type { ExecutionMeta } from '../../types/workbench'

export function hasExecutionResult(meta: ExecutionMeta | null, resultId: number | null): boolean {
  return Boolean(meta && resultId)
}

import type { ExecutionMeta } from '../../types/workbench'

export function resetExecutionState(): {
  executionMeta: ExecutionMeta | null
  abnormalResults: []
  abnormalResultTotal: number
  resultId: number | null
  resultCurrentPage: number
  isResultPageLoading: boolean
  isResultExporting: boolean
} {
  return {
    executionMeta: null,
    abnormalResults: [],
    abnormalResultTotal: 0,
    resultId: null,
    resultCurrentPage: 1,
    isResultPageLoading: false,
    isResultExporting: false,
  }
}

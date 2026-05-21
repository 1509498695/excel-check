import type { DataSource } from '../../types/workbench'

export function collectAffectedSourceIds(source: DataSource, originalId?: string): Set<string> {
  const affectedSourceIds = new Set<string>([source.id])
  if (originalId) {
    affectedSourceIds.add(originalId)
  }
  return affectedSourceIds
}

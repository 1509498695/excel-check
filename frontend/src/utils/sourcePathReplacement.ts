import type { DataSource, VariableTag } from '../types/workbench'

const LOCAL_FILE_SOURCE_TYPES = new Set(['local_excel', 'local_csv'])

export function isLocalFileSource(source: DataSource): boolean {
  return LOCAL_FILE_SOURCE_TYPES.has(source.type)
}

export function getSourceLocator(source: DataSource): string {
  return source.pathOrUrl ?? source.path ?? source.url ?? ''
}

export function extractSourceBasename(pathText: string): string {
  const normalizedPath = pathText.trim().replace(/[\\/]+$/, '')
  if (!normalizedPath) {
    return ''
  }
  const segments = normalizedPath.split(/[\\/]/)
  return segments[segments.length - 1] ?? ''
}

export function joinDirectoryAndBasename(directoryPath: string, basename: string): string {
  const normalizedDirectory = directoryPath.trim().replace(/[\\/]+$/, '')
  const separator =
    normalizedDirectory.includes('\\') || /^[A-Za-z]:/.test(normalizedDirectory) ? '\\' : '/'
  return `${normalizedDirectory}${separator}${basename}`
}

export function normalizeReplacementPreset(pathText: string): string {
  return pathText.trim()
}

export function isAffectedVariable(
  variable: VariableTag | undefined | null,
  affectedSourceIds: Set<string>,
): variable is VariableTag {
  return Boolean(variable && affectedSourceIds.has(variable.source_id))
}

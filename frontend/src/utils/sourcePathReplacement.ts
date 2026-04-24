import type { DataSource, VariableTag } from '../types/workbench'

export type SourcePathReplacementGroup = 'local' | 'svn'

const LOCAL_FILE_SOURCE_TYPES = new Set(['local_excel', 'local_csv'])
const REMOTE_SVN_PROTOCOL = /^https?:\/\//i

export function isRemoteSvnSource(source: DataSource): boolean {
  if (source.type !== 'svn') {
    return false
  }
  return REMOTE_SVN_PROTOCOL.test(getSourceLocator(source).trim())
}

export function isLocalFileSource(source: DataSource): boolean {
  return LOCAL_FILE_SOURCE_TYPES.has(source.type) || (source.type === 'svn' && !isRemoteSvnSource(source))
}

export function isLocalPathManagedSource(source: DataSource): boolean {
  return isLocalFileSource(source)
}

export function isSvnPathManagedSource(source: DataSource): boolean {
  return isRemoteSvnSource(source)
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

export function joinSvnDirectoryAndBasename(directoryUrl: string, basename: string): string {
  const normalizedDirectory = normalizeReplacementPreset(directoryUrl, 'svn')
  return `${normalizedDirectory}${basename}`
}

export function normalizeReplacementPreset(
  pathText: string,
  group: SourcePathReplacementGroup = 'local',
): string {
  const normalized = pathText.trim()
  if (!normalized) {
    return ''
  }
  if (group === 'svn') {
    return normalized.endsWith('/') ? normalized : `${normalized}/`
  }
  return normalized
}

export function isAffectedVariable(
  variable: VariableTag | undefined | null,
  affectedSourceIds: Set<string>,
): variable is VariableTag {
  return Boolean(variable && affectedSourceIds.has(variable.source_id))
}

import type { DataSource } from '../../types/workbench'
import {
  extractSourceBasename,
  getSourceLocator,
  isLocalPathManagedSource,
  isSvnPathManagedSource,
  joinDirectoryAndBasename,
  joinSvnDirectoryAndBasename,
  normalizeReplacementPreset,
  type SourcePathReplacementGroup,
} from '../../utils/sourcePathReplacement'

export {
  extractSourceBasename,
  getSourceLocator,
  isLocalPathManagedSource,
  isSvnPathManagedSource,
  joinDirectoryAndBasename,
  joinSvnDirectoryAndBasename,
  normalizeReplacementPreset,
  type SourcePathReplacementGroup,
}

export function isManagedSourceForReplacement(
  source: DataSource,
  group: SourcePathReplacementGroup,
): boolean {
  return group === 'svn' ? isSvnPathManagedSource(source) : isLocalPathManagedSource(source)
}

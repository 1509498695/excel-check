import type {
  DataSource,
  SourceMetadata,
  SourceType,
  VariablePreviewData,
  VariableTag,
} from './workbench'

export interface SourceManagementStoreLike {
  sources: DataSource[]
  capabilities: SourceType[]
  preferredSourceId: string | null
  upsertSource(source: DataSource, originalId?: string): void
  removeSource(sourceId: string): void
  useSampleSource(): void
}

export interface VariablePoolStoreLike extends SourceManagementStoreLike {
  variables: VariableTag[]
  activeTag: string | null
  sourceMetadataMap: Record<string, SourceMetadata>
  variablePreviewMap: Record<string, VariablePreviewData>
  setActiveTag(tag: string | null): void
  loadSourceMetadata(sourceId: string): Promise<SourceMetadata>
  loadVariablePreview(
    variable: VariableTag,
    limit?: number,
    forceRefresh?: boolean,
  ): Promise<VariablePreviewData>
  upsertVariable(variable: VariableTag, originalTag?: string): void
  removeVariable(tag: string): void
}

export interface SourcePathReplacementResult {
  updatedCount: number
  skippedCount: number
  failedCount: number
  affectedSourceIds: string[]
}

export interface SourcePathReplacementStoreLike extends SourceManagementStoreLike {
  variables: VariableTag[]
  activeTag: string | null
  pathReplacementPresets: string[]
  selectedPathReplacementPreset: string | null
  saveConfigNow(): Promise<void>
  setSelectedPathReplacementPreset(path: string | null): void
  addPathReplacementPreset(path: string): void
  replaceSourceBasePath(baseDirectory: string): Promise<SourcePathReplacementResult>
}

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { saveWorkbenchConfig } from '../../src/api/workbench'
import { useWorkbenchStore } from '../../src/store/workbench'
import type { FixedRuleDefinition } from '../../src/types/fixedRules'
import type { DataSource, VariableTag } from '../../src/types/workbench'

vi.mock('../../src/api/workbench', () => ({
  executeTaskTree: vi.fn(),
  exportExecutionResults: vi.fn(),
  fetchColumnPreview: vi.fn(),
  fetchCompositePreview: vi.fn(),
  fetchExecutionResults: vi.fn(),
  fetchSourceCapabilities: vi.fn(),
  fetchSourceMetadata: vi.fn(),
  fetchWorkbenchConfig: vi.fn(),
  saveWorkbenchConfig: vi.fn(),
  triggerWorkbenchSvnUpdate: vi.fn(),
}))

const saveWorkbenchConfigMock = vi.mocked(saveWorkbenchConfig)

const source: DataSource = {
  id: 'src_items',
  type: 'local_excel',
  pathOrUrl: 'C:/data/items.xlsx',
}

const variable: VariableTag = {
  tag: '[items-id]',
  source_id: 'src_items',
  sheet: 'items',
  variable_kind: 'single',
  column: 'ID',
  expected_type: 'int',
}

const rule: FixedRuleDefinition = {
  rule_id: 'rule-not-null',
  group_id: 'ungrouped',
  rule_name: 'ID 非空',
  target_variable_tag: '[items-id]',
  rule_type: 'not_null',
}

function createStoreWithConfig() {
  const store = useWorkbenchStore()
  store.sources = [source]
  store.variables = [variable]
  store.orchestrationRules = [rule]
  store.localPathReplacementPresets = ['C:/data']
  store.selectedLocalPathReplacementPreset = 'C:/data'
  return store
}

describe('workbench autosave state', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-05-14T10:00:00+08:00'))
    vi.clearAllMocks()
    saveWorkbenchConfigMock.mockResolvedValue({ code: 0, msg: 'ok' })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('marks manual save as saving then saved and keeps the existing config payload shape', async () => {
    const store = createStoreWithConfig()

    const savePromise = store.saveConfigNow()

    expect(store.autoSaveStatus).toBe('saving')
    await savePromise

    expect(saveWorkbenchConfigMock).toHaveBeenCalledWith({
      sources: [source],
      variables: [variable],
      ruleGroups: store.ruleGroups,
      orchestrationRules: [rule],
      local_path_replacement_presets: ['C:/data'],
      selected_local_path_replacement_preset: 'C:/data',
      svn_path_replacement_presets: [],
      selected_svn_path_replacement_preset: null,
    })
    expect(store.autoSaveStatus).toBe('saved')
    expect(store.autoSaveError).toBe('')
    expect(store.autoSaveSavedAt).toBe(new Date('2026-05-14T10:00:00+08:00').getTime())
  })

  it('records failed save state and exposes the error message', async () => {
    const store = createStoreWithConfig()
    saveWorkbenchConfigMock.mockRejectedValueOnce(new Error('network down'))

    await expect(store.saveConfigNow()).rejects.toThrow('network down')

    expect(store.autoSaveStatus).toBe('failed')
    expect(store.autoSaveError).toBe('network down')
  })

  it('retries a failed save through the same save path', async () => {
    const store = createStoreWithConfig()
    saveWorkbenchConfigMock
      .mockRejectedValueOnce(new Error('network down'))
      .mockResolvedValueOnce({ code: 0, msg: 'ok' })

    await expect(store.saveConfigNow()).rejects.toThrow('network down')
    await store.retryAutoSave()

    expect(saveWorkbenchConfigMock).toHaveBeenCalledTimes(2)
    expect(store.autoSaveStatus).toBe('saved')
    expect(store.autoSaveError).toBe('')
  })

  it('debounces automatic saves and only persists the latest trigger', async () => {
    const store = createStoreWithConfig()

    store.triggerAutoSave()
    store.triggerAutoSave()
    store.triggerAutoSave()

    expect(store.autoSaveStatus).toBe('idle')
    expect(saveWorkbenchConfigMock).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(1999)
    expect(saveWorkbenchConfigMock).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(1)

    expect(saveWorkbenchConfigMock).toHaveBeenCalledTimes(1)
    expect(store.autoSaveStatus).toBe('saved')
  })
})

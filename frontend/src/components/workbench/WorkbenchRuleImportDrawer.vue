<script setup lang="ts">
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import {
  importWorkbenchRules,
  previewWorkbenchRuleImport,
} from '../../api/fixedRules'
import type {
  FixedRulesImportPreview,
  FixedRulesImportRulePreview,
  FixedRulesImportSourcePreview,
  FixedRulesImportVariablePreview,
} from '../../types/fixedRules'
import type { DataSource, SourceType } from '../../types/workbench'
import type { SourceManagementStoreLike } from '../../types/panelStores'
import DataSourcePanel from './DataSourcePanel.vue'

interface DataSourceDialogPrefill {
  id?: string
  type?: SourceType
  pathOrUrl?: string
  token?: string
}

const props = defineProps<{
  visible: boolean
  selectedRuleIds: string[]
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'imported', preview: FixedRulesImportPreview): void
}>()

const drawerVisible = computed({
  get: () => props.visible,
  set: (value: boolean) => emit('update:visible', value),
})

const preview = ref<FixedRulesImportPreview | null>(null)
const pageError = ref('')
const isPreviewLoading = ref(false)
const isImporting = ref(false)
const needsPreviewRefresh = ref(false)
const activeOverrideSourceId = ref<string | null>(null)
const sourcePanelRef = ref<{
  openCreateDialog: (prefill?: DataSourceDialogPrefill) => void
  openEditDialog: (source: DataSource) => void
} | null>(null)
const sourceOverrides = reactive<Record<string, DataSource>>({})
const overrideOwnerBySourceId = reactive<Record<string, string>>({})
const variableTagOverrides = reactive<Record<string, string>>({})

const scratchSourceStore = reactive<SourceManagementStoreLike>({
  sources: [],
  capabilities: ['local_excel', 'svn'],
  preferredSourceId: null,
  svnPathReplacementPresets: [],
  selectedSvnPathReplacementPreset: null,
  upsertSource(source: DataSource, originalId?: string): void {
    const nextSource = { ...source }
    if (originalId && originalId !== nextSource.id) {
      const index = this.sources.findIndex((item) => item.id === originalId)
      if (index >= 0) {
        this.sources.splice(index, 1, nextSource)
      } else {
        this.sources.push(nextSource)
      }
      const owner = overrideOwnerBySourceId[originalId]
      if (owner) {
        delete overrideOwnerBySourceId[originalId]
        overrideOwnerBySourceId[nextSource.id] = owner
      }
    } else {
      const index = this.sources.findIndex((item) => item.id === nextSource.id)
      if (index >= 0) {
        this.sources.splice(index, 1, nextSource)
      } else {
        this.sources.push(nextSource)
      }
    }
    this.preferredSourceId = nextSource.id
  },
  removeSource(sourceId: string): void {
    this.sources = this.sources.filter((source) => source.id !== sourceId)
    if (this.preferredSourceId === sourceId) {
      this.preferredSourceId = this.sources[0]?.id ?? null
    }
  },
  useSampleSource(): void {},
})

const canImport = computed(
  () =>
    Boolean(preview.value?.summary.ready) &&
    !needsPreviewRefresh.value &&
    !isPreviewLoading.value &&
    !isImporting.value,
)

watch(
  () => props.visible,
  (visible) => {
    if (!visible) {
      return
    }
    resetDraft()
    void loadPreview()
  },
)

function resetDraft(): void {
  preview.value = null
  pageError.value = ''
  needsPreviewRefresh.value = false
  activeOverrideSourceId.value = null
  Object.keys(sourceOverrides).forEach((key) => delete sourceOverrides[key])
  Object.keys(overrideOwnerBySourceId).forEach((key) => delete overrideOwnerBySourceId[key])
  Object.keys(variableTagOverrides).forEach((key) => delete variableTagOverrides[key])
  scratchSourceStore.sources = []
  scratchSourceStore.preferredSourceId = null
}

function buildVariableTagOverrides(): Record<string, string> {
  return Object.fromEntries(
    Object.entries(variableTagOverrides)
      .map(([key, value]) => [key, value.trim()])
      .filter(([, value]) => value),
  )
}

function buildPayload() {
  return {
    selected_rule_ids: props.selectedRuleIds,
    preview_token: preview.value?.preview_token ?? null,
    source_overrides: Object.fromEntries(
      Object.entries(sourceOverrides).map(([key, source]) => [key, { ...source }]),
    ),
    variable_tag_overrides: buildVariableTagOverrides(),
  }
}

async function loadPreview(): Promise<void> {
  if (!props.selectedRuleIds.length) {
    pageError.value = '请先勾选需要导入项目校验的规则。'
    preview.value = null
    return
  }

  isPreviewLoading.value = true
  pageError.value = ''
  try {
    const response = await previewWorkbenchRuleImport(buildPayload())
    preview.value = response.data
    needsPreviewRefresh.value = false
  } catch (error) {
    pageError.value = error instanceof Error ? error.message : '导入预检失败。'
    preview.value = null
  } finally {
    isPreviewLoading.value = false
  }
}

async function confirmImport(): Promise<void> {
  if (!preview.value || !canImport.value) {
    return
  }
  isImporting.value = true
  pageError.value = ''
  try {
    const response = await importWorkbenchRules(buildPayload())
    const result = response.meta?.import_result ?? preview.value
    preview.value = result
    emit('imported', result)
    ElMessage.success(`已导入 ${result.summary.ready} 条规则到项目校验。`)
    drawerVisible.value = false
  } catch (error) {
    pageError.value = error instanceof Error ? error.message : '导入项目校验失败。'
  } finally {
    isImporting.value = false
  }
}

function openCreateOverride(row: FixedRulesImportSourcePreview): void {
  const base = row.personal_source ?? row.final_source
  if (!base) {
    ElMessage.warning('当前数据源无法创建草稿。')
    return
  }
  const fallbackId = `${row.personal_source_id}_import`
  activeOverrideSourceId.value = row.personal_source_id
  syncScratchSources()
  void nextTick(() => {
    sourcePanelRef.value?.openCreateDialog({
      id: fallbackId,
      type: base.type,
      pathOrUrl: base.pathOrUrl ?? base.path ?? base.url ?? '',
      token: base.token ?? '',
    })
  })
}

function openEditOverride(row: FixedRulesImportSourcePreview): void {
  const override = sourceOverrides[row.personal_source_id]
  if (!override) {
    openCreateOverride(row)
    return
  }
  activeOverrideSourceId.value = row.personal_source_id
  syncScratchSources()
  void nextTick(() => {
    sourcePanelRef.value?.openEditDialog(override)
  })
}

function handleOverrideSaved(sourceId: string): void {
  const owner = activeOverrideSourceId.value
  const source = scratchSourceStore.sources.find((item) => item.id === sourceId)
  if (!owner || !source) {
    return
  }
  sourceOverrides[owner] = { ...source }
  overrideOwnerBySourceId[source.id] = owner
  markDraftChanged()
}

function handleOverrideChanged(): void {
  const validSourceIds = new Set(scratchSourceStore.sources.map((source) => source.id))
  Object.entries(overrideOwnerBySourceId).forEach(([sourceId, owner]) => {
    if (!validSourceIds.has(sourceId)) {
      delete overrideOwnerBySourceId[sourceId]
      delete sourceOverrides[owner]
      markDraftChanged()
    }
  })
}

function syncScratchSources(): void {
  scratchSourceStore.sources = Object.values(sourceOverrides).map((source) => ({ ...source }))
  Object.keys(overrideOwnerBySourceId).forEach((key) => delete overrideOwnerBySourceId[key])
  Object.entries(sourceOverrides).forEach(([owner, source]) => {
    overrideOwnerBySourceId[source.id] = owner
  })
}

function getSourceModeLabel(row: FixedRulesImportSourcePreview): string {
  if (sourceOverrides[row.personal_source_id]) return '自定义草稿'
  if (row.mode === 'project') return '复用项目源'
  if (row.mode === 'new') return '新增项目源'
  if (row.mode === 'custom') return '自定义草稿'
  return '不可用'
}

function getVariableModeLabel(row: FixedRulesImportVariablePreview): string {
  if (row.mode === 'project') return '复用变量'
  if (row.mode === 'new') return '新增变量'
  return '不可用'
}

function getVariableDraftTag(row: FixedRulesImportVariablePreview): string {
  return variableTagOverrides[row.personal_tag] ?? row.override_tag ?? row.final_tag ?? row.personal_tag
}

function handleVariableTagInput(row: FixedRulesImportVariablePreview, value: unknown): void {
  const nextTag = String(value ?? '').trim()
  const currentTag = variableTagOverrides[row.personal_tag] ?? ''
  if (nextTag === currentTag) {
    return
  }
  if (!nextTag || nextTag === row.personal_tag) {
    delete variableTagOverrides[row.personal_tag]
  } else {
    variableTagOverrides[row.personal_tag] = nextTag
  }
  markDraftChanged()
}

function applySuggestedTag(row: FixedRulesImportVariablePreview): void {
  if (!row.suggested_tag) {
    return
  }
  handleVariableTagInput(row, row.suggested_tag)
}

function getRuleStatusLabel(row: FixedRulesImportRulePreview): string {
  if (row.status === 'ready') return '可导入'
  if (row.status === 'duplicate') return '已存在'
  return '不兼容'
}

function getStatusTagType(status: string): 'success' | 'warning' | 'info' | 'danger' {
  if (status === 'ready') return 'success'
  if (status === 'duplicate') return 'info'
  if (status === 'skipped') return 'warning'
  return 'info'
}

function getSourcePath(source: DataSource | null | undefined): string {
  return source?.pathOrUrl ?? source?.path ?? source?.url ?? '-'
}

function shouldShowTooltip(value: string | null | undefined): boolean {
  return Boolean(value && value.length > 36)
}

function markDraftChanged(): void {
  needsPreviewRefresh.value = true
}
</script>

<template>
  <el-drawer
    v-model="drawerVisible"
    title="导入项目校验"
    size="min(1180px, 92vw)"
    destroy-on-close
    class="rule-import-drawer"
  >
    <div class="flex h-full flex-col gap-4">
      <div
        v-if="pageError"
        role="alert"
        class="rounded-card border border-line border-l-4 border-l-danger bg-danger-soft/40 px-4 py-3 text-[13px] text-ink-700"
      >
        {{ pageError }}
      </div>

      <div
        v-if="needsPreviewRefresh"
        role="alert"
        class="rounded-card border border-line border-l-4 border-l-warning bg-warning-soft/40 px-4 py-3 text-[13px] text-ink-700"
      >
        导入草稿已变更，请重新预检。
      </div>

      <section class="grid grid-cols-4 gap-3">
        <div class="rounded-field border border-line bg-subtle px-3 py-2">
          <div class="text-[12px] text-ink-500">已选择</div>
          <div class="mt-1 font-mono text-[18px] font-semibold text-ink-900">{{ selectedRuleIds.length }}</div>
        </div>
        <div class="rounded-field border border-line bg-subtle px-3 py-2">
          <div class="text-[12px] text-ink-500">可导入</div>
          <div class="mt-1 font-mono text-[18px] font-semibold text-success">{{ preview?.summary.ready ?? 0 }}</div>
        </div>
        <div class="rounded-field border border-line bg-subtle px-3 py-2">
          <div class="text-[12px] text-ink-500">已存在</div>
          <div class="mt-1 font-mono text-[18px] font-semibold text-ink-700">{{ preview?.summary.duplicate ?? 0 }}</div>
        </div>
        <div class="rounded-field border border-line bg-subtle px-3 py-2">
          <div class="text-[12px] text-ink-500">跳过</div>
          <div class="mt-1 font-mono text-[18px] font-semibold text-warning-ink">{{ preview?.summary.skipped ?? 0 }}</div>
        </div>
      </section>

      <div v-loading="isPreviewLoading" class="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto pr-1">
        <section class="flex flex-col gap-2">
          <div class="text-[14px] font-semibold text-ink-900">数据源</div>
          <el-table :data="preview?.sources ?? []" :fit="false" class="workbench-table import-preview-table">
            <el-table-column label="个人源" width="160">
              <template #default="{ row }">
                <span class="mono-chip">{{ row.personal_source_id }}</span>
              </template>
            </el-table-column>
            <el-table-column label="导入方式" width="140">
              <template #default="{ row }">
                <el-tag :type="row.status === 'ready' ? 'success' : 'warning'" effect="light" round>
                  {{ getSourceModeLabel(row) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="目标路径" width="560">
              <template #default="{ row }">
                <el-tooltip
                  :content="getSourcePath(sourceOverrides[row.personal_source_id] ?? row.final_source)"
                  placement="top"
                  :disabled="!shouldShowTooltip(getSourcePath(sourceOverrides[row.personal_source_id] ?? row.final_source))"
                >
                  <div class="break-all text-[12px] leading-5 text-ink-700">
                    {{ getSourcePath(sourceOverrides[row.personal_source_id] ?? row.final_source) }}
                  </div>
                </el-tooltip>
                <div v-if="row.issue" class="mt-1 break-words text-[12px] text-warning-ink">{{ row.issue }}</div>
              </template>
            </el-table-column>
            <el-table-column label="Sheet" width="100">
              <template #default="{ row }">
                {{ row.metadata?.sheets?.length ?? 0 }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <button
                  v-if="sourceOverrides[row.personal_source_id]"
                  type="button"
                  class="ec-action-link"
                  @click="openEditOverride(row)"
                >
                  编辑草稿
                </button>
                <button
                  v-else
                  type="button"
                  class="ec-action-link"
                  @click="openCreateOverride(row)"
                >
                  自定义源
                </button>
              </template>
            </el-table-column>
          </el-table>
        </section>

        <section v-if="scratchSourceStore.sources.length" class="flex flex-col gap-2">
          <div class="text-[14px] font-semibold text-ink-900">自定义导入源</div>
          <DataSourcePanel
            ref="sourcePanelRef"
            :store="scratchSourceStore"
            variant="fixed-rules"
            toolbar-mode="hidden"
            @saved="handleOverrideSaved"
            @changed="handleOverrideChanged"
          />
        </section>
        <DataSourcePanel
          v-else
          ref="sourcePanelRef"
          :store="scratchSourceStore"
          variant="fixed-rules"
          toolbar-mode="hidden"
          class="hidden"
          @saved="handleOverrideSaved"
          @changed="handleOverrideChanged"
        />

        <section class="flex flex-col gap-2">
          <div class="text-[14px] font-semibold text-ink-900">变量映射</div>
          <el-table :data="preview?.variables ?? []" :fit="false" class="workbench-table import-preview-table">
            <el-table-column label="个人变量" width="240">
              <template #default="{ row }">
                <span class="mono-chip">{{ row.personal_tag }}</span>
              </template>
            </el-table-column>
            <el-table-column label="目标变量标签" width="320">
              <template #default="{ row }">
                <div class="flex flex-col gap-1.5">
                  <el-input
                    :model-value="getVariableDraftTag(row)"
                    size="small"
                    clearable
                    placeholder="输入导入后的项目变量标签"
                    @update:model-value="handleVariableTagInput(row, $event)"
                  />
                  <div v-if="row.can_rename && row.suggested_tag" class="flex flex-wrap items-center gap-2 text-[12px] text-ink-500">
                    <span>建议：</span>
                    <button type="button" class="ec-action-link" @click="applySuggestedTag(row)">
                      {{ row.suggested_tag }}
                    </button>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="预检结果" width="150">
              <template #default="{ row }">
                <el-tag :type="row.status === 'ready' ? 'success' : 'warning'" effect="light" round>
                  {{ getVariableModeLabel(row) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="最终项目变量" width="240">
              <template #default="{ row }">
                <span class="mono-chip">{{ row.final_tag ?? '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="说明" width="420">
              <template #default="{ row }">
                <span class="break-words text-[12px] leading-5 text-ink-500">{{ row.issue ?? '-' }}</span>
              </template>
            </el-table-column>
          </el-table>
        </section>

        <section class="flex flex-col gap-2">
          <div class="text-[14px] font-semibold text-ink-900">规则</div>
          <el-table :data="preview?.rules ?? []" :fit="false" class="workbench-table import-preview-table">
            <el-table-column label="规则名称" width="420">
              <template #default="{ row }">
                <div class="break-words text-[13px] font-medium text-ink-900">{{ row.rule_name }}</div>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="130">
              <template #default="{ row }">
                <el-tag :type="getStatusTagType(row.status)" effect="light" round>
                  {{ getRuleStatusLabel(row) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="说明" width="520">
              <template #default="{ row }">
                <span class="break-words text-[12px] leading-5 text-ink-500">{{ row.reason ?? '-' }}</span>
              </template>
            </el-table-column>
          </el-table>
        </section>
      </div>
    </div>

    <template #footer>
      <div class="flex justify-end gap-2">
        <button type="button" class="ec-btn ec-btn-secondary" @click="drawerVisible = false">
          取消
        </button>
        <button
          type="button"
          class="ec-btn ec-btn-secondary"
          :disabled="isPreviewLoading || isImporting"
          @click="loadPreview"
        >
          {{ isPreviewLoading ? '预检中…' : '重新预检' }}
        </button>
        <button
          type="button"
          class="ec-btn ec-btn-primary"
          :disabled="!canImport"
          @click="confirmImport"
        >
          {{ isImporting ? '导入中…' : '确认导入' }}
        </button>
      </div>
    </template>
  </el-drawer>
</template>

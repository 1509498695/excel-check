<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { useWorkbenchStore } from '../../store/workbench'
import type { DataSource, VariableTag } from '../../types/workbench'
import { EXPECTED_TYPE_OPTIONS } from '../../utils/workbenchMeta'

const store = useWorkbenchStore()
const emit = defineEmits<{
  saved: [tag: string]
}>()

const activeTab = ref('summary')
const editorVisible = ref(false)
const editingTag = ref<string | null>(null)
const isMetadataLoading = ref(false)
const metadataError = ref('')
const tagTouched = ref(false)

const detailDialogVisible = ref(false)
const detailDialogTag = ref<string | null>(null)
const detailLoading = ref(false)
const detailError = ref('')

const draft = reactive<VariableTag>({
  tag: '',
  source_id: '',
  sheet: '',
  column: '',
  expected_type: 'str',
})

const draftErrors = reactive({
  source_id: '',
  sheet: '',
  column: '',
  tag: '',
  expected_type: '',
})

const sourceOptions = computed<DataSource[]>(() => store.sources)
const currentSource = computed<DataSource | null>(
  () => sourceOptions.value.find((source) => source.id === draft.source_id) ?? null,
)
const currentSourceMetadata = computed(() =>
  draft.source_id ? store.sourceMetadataMap[draft.source_id] ?? null : null,
)
const sheetOptions = computed(() => currentSourceMetadata.value?.sheets ?? [])
const columnOptions = computed(
  () => sheetOptions.value.find((sheet) => sheet.name === draft.sheet)?.columns ?? [],
)
const detailVariable = computed<VariableTag | null>(() =>
  detailDialogTag.value
    ? store.variables.find((variable) => variable.tag === detailDialogTag.value) ?? null
    : null,
)
const detailSource = computed<DataSource | null>(() =>
  detailVariable.value
    ? store.sources.find((source) => source.id === detailVariable.value?.source_id) ?? null
    : null,
)
const detailPreview = computed(() =>
  detailVariable.value ? store.variablePreviewMap[detailVariable.value.tag] ?? null : null,
)
const detailSourcePath = computed(
  () =>
    detailPreview.value?.source_path ??
    detailSource.value?.pathOrUrl ??
    detailSource.value?.path ??
    detailSource.value?.url ??
    '',
)
const detailLoadedRows = computed(
  () => detailPreview.value?.loaded_rows ?? detailPreview.value?.preview_rows.length ?? 0,
)
const detailHasEmptyPreview = computed(
  () => Boolean(detailPreview.value) && (detailPreview.value?.total_rows ?? 0) === 0,
)
const canUseExcelMetadata = computed(() => currentSource.value?.type === 'local_excel')
const canSaveVariable = computed(
  () =>
    !isMetadataLoading.value &&
    canUseExcelMetadata.value &&
    draft.tag.trim().length > 0 &&
    draft.source_id.trim().length > 0 &&
    draft.sheet.trim().length > 0 &&
    draft.column.trim().length > 0 &&
    Boolean(draft.expected_type),
)

const variableGuide = computed(() => {
  if (!store.sources.length) {
    return {
      type: 'warning' as const,
      title: '请先完成步骤 1 的数据源接入',
      description: '先保存至少一个数据源，再在这里按来源数据、Sheet 和列名逐级构建变量池。',
    }
  }

  if (!store.variables.length) {
    const preferredSource = store.preferredSourceId ?? store.sources[0]?.id ?? '未选择'
    return {
      type: 'info' as const,
      title: '数据源已就绪，建议先提取首个变量',
      description: `当前默认来源为 ${preferredSource}。建议先选择真实 Sheet 和列名，保存后变量会进入下方变量池。`,
    }
  }

  return {
    type: 'success' as const,
    title: '变量池已可复用',
    description: `当前已配置 ${store.variables.length} 个变量标签。点击变量池按钮或列表中的“查看详情”，可弹出详情窗口查看列预览并确认映射。`,
  }
})

function createSuggestedTag(sourceId: string, sheet: string, column: string): string {
  return `[${sourceId || 'source'}-${sheet || 'sheet'}-${column || 'column'}]`
}

function syncSuggestedTag(): void {
  if (!tagTouched.value) {
    draft.tag = createSuggestedTag(draft.source_id.trim(), draft.sheet.trim(), draft.column.trim())
  }
}

function clearDraftErrors(): void {
  draftErrors.source_id = ''
  draftErrors.sheet = ''
  draftErrors.column = ''
  draftErrors.tag = ''
  draftErrors.expected_type = ''
}

function resetDraft(): void {
  draft.tag = ''
  draft.source_id = store.preferredSourceId ?? store.sources[0]?.id ?? ''
  draft.sheet = ''
  draft.column = ''
  draft.expected_type = 'str'
  tagTouched.value = false
  metadataError.value = ''
  clearDraftErrors()
  syncSuggestedTag()
}

function closeEditorTab(): void {
  editorVisible.value = false
  editingTag.value = null
  activeTab.value = 'summary'
  clearDraftErrors()
  metadataError.value = ''
}

async function prepareEditorForSource(sourceId: string, preserveSelection = false): Promise<void> {
  if (!sourceId) {
    metadataError.value = ''
    return
  }

  const source = sourceOptions.value.find((item) => item.id === sourceId)
  if (!source) {
    metadataError.value = '未找到当前选择的数据源。'
    return
  }

  if (source.type !== 'local_excel') {
    metadataError.value = '变量池下拉提取第一版仅支持 Excel 数据源。'
    if (!preserveSelection) {
      draft.sheet = ''
      draft.column = ''
    }
    syncSuggestedTag()
    return
  }

  isMetadataLoading.value = true
  metadataError.value = ''
  try {
    const metadata = await store.loadSourceMetadata(sourceId)
    const matchedSheet = metadata.sheets.find((sheet) => sheet.name === draft.sheet)

    if (!preserveSelection || !matchedSheet) {
      draft.sheet = ''
      draft.column = ''
    } else if (!matchedSheet.columns.includes(draft.column)) {
      draft.column = ''
    }

    if (!metadata.sheets.length) {
      metadataError.value = '当前 Excel 数据源未读取到可用的 Sheet。'
    }

    syncSuggestedTag()
  } catch (error) {
    metadataError.value = error instanceof Error ? error.message : '读取数据源结构失败。'
    if (!preserveSelection) {
      draft.sheet = ''
      draft.column = ''
    }
    ElMessage.error(metadataError.value)
  } finally {
    isMetadataLoading.value = false
  }
}

async function openCreateTab(): Promise<void> {
  editingTag.value = null
  resetDraft()
  editorVisible.value = true
  activeTab.value = 'editor'
  await prepareEditorForSource(draft.source_id, false)
}

async function openEditTab(variable: VariableTag): Promise<void> {
  editingTag.value = variable.tag
  draft.tag = variable.tag
  draft.source_id = variable.source_id
  draft.sheet = variable.sheet
  draft.column = variable.column
  draft.expected_type = variable.expected_type ?? 'str'
  tagTouched.value =
    variable.tag.trim() !==
    createSuggestedTag(variable.source_id.trim(), variable.sheet.trim(), variable.column.trim())
  metadataError.value = ''
  clearDraftErrors()
  editorVisible.value = true
  activeTab.value = 'editor'
  await prepareEditorForSource(variable.source_id, true)
}

async function handleSourceChange(nextSourceId: string): Promise<void> {
  draft.source_id = nextSourceId
  draft.sheet = ''
  draft.column = ''
  draftErrors.source_id = ''
  draftErrors.sheet = ''
  draftErrors.column = ''
  syncSuggestedTag()

  if (!nextSourceId) {
    metadataError.value = ''
    return
  }

  const source = sourceOptions.value.find((item) => item.id === nextSourceId)
  if (source?.type !== 'local_excel') {
    metadataError.value = '变量池下拉提取第一版仅支持 Excel 数据源。'
    ElMessage.warning(metadataError.value)
    return
  }

  await prepareEditorForSource(nextSourceId, false)
}

function handleSheetChange(nextSheet: string): void {
  draft.sheet = nextSheet
  draft.column = ''
  draftErrors.sheet = ''
  draftErrors.column = ''
  syncSuggestedTag()
}

function handleColumnChange(nextColumn: string): void {
  draft.column = nextColumn
  draftErrors.column = ''
  syncSuggestedTag()
}

function handleTagInput(value: string): void {
  draft.tag = value
  draftErrors.tag = ''
  tagTouched.value = true
}

function getExpectedTypeLabel(expectedType?: string | null): string {
  return EXPECTED_TYPE_OPTIONS.find((option) => option.value === expectedType)?.label ?? '未指定'
}

function formatPreviewValue(value: unknown): string {
  if (value === null || value === undefined) {
    return '空值'
  }

  if (typeof value === 'string') {
    if (!value.length) {
      return '(空字符串)'
    }

    if (!value.trim().length) {
      return JSON.stringify(value)
    }

    return value
  }

  if (typeof value === 'object') {
    try {
      return JSON.stringify(value)
    } catch {
      return '[复杂对象]'
    }
  }

  return String(value)
}

function validateDraft(): boolean {
  clearDraftErrors()

  if (!draft.source_id.trim()) {
    draftErrors.source_id = '请选择来源数据。'
  } else if (!canUseExcelMetadata.value) {
    draftErrors.source_id = '变量池下拉提取第一版仅支持 Excel 数据源。'
  }

  if (!draft.sheet.trim()) {
    draftErrors.sheet = '请选择 Sheet。'
  }

  if (!draft.column.trim()) {
    draftErrors.column = '请选择列名。'
  }

  if (!draft.tag.trim()) {
    draftErrors.tag = '请输入变量标签。'
  }

  if (
    draft.tag.trim() &&
    store.variables.some(
      (variable) =>
        variable.tag === draft.tag.trim() &&
        (!editingTag.value || variable.tag !== editingTag.value),
    )
  ) {
    draftErrors.tag = '变量标签已存在，请保持全局唯一。'
  }

  if (!draft.expected_type) {
    draftErrors.expected_type = '请选择期望类型。'
  }

  return !Object.values(draftErrors).some(Boolean)
}

async function ensureDetailPreview(variable: VariableTag, forceRefresh = false): Promise<void> {
  detailLoading.value = true
  detailError.value = ''

  try {
    await store.loadVariablePreview(variable, undefined, forceRefresh)
  } catch (error) {
    detailError.value = error instanceof Error ? error.message : '读取变量详情失败。'
    ElMessage.error(detailError.value)
  } finally {
    detailLoading.value = false
  }
}

async function openDetailDialog(variable: VariableTag, forceRefresh = false): Promise<void> {
  detailDialogTag.value = variable.tag
  detailDialogVisible.value = true
  store.setActiveTag(variable.tag)
  await ensureDetailPreview(variable, forceRefresh)
}

async function saveVariable(): Promise<void> {
  if (!validateDraft()) {
    ElMessage.warning('请先完整填写来源数据、Sheet、列名、变量标签和期望类型。')
    return
  }

  const nextTag = draft.tag.trim()
  const nextVariable: VariableTag = {
    tag: nextTag,
    source_id: draft.source_id.trim(),
    sheet: draft.sheet.trim(),
    column: draft.column.trim(),
    expected_type: draft.expected_type ?? null,
  }
  const previousTag = editingTag.value

  store.upsertVariable(nextVariable, previousTag ?? undefined)

  if (detailDialogTag.value && previousTag && detailDialogTag.value === previousTag) {
    detailDialogTag.value = nextTag
    detailError.value = ''
  }

  emit('saved', nextTag)
  closeEditorTab()
  ElMessage.success(previousTag ? '变量已更新。' : '变量已添加。')
}

function removeVariable(tag: string): void {
  store.removeVariable(tag)

  if (detailDialogTag.value === tag) {
    detailDialogVisible.value = false
    detailDialogTag.value = null
    detailError.value = ''
    detailLoading.value = false
  }

  ElMessage.success('变量已移除。')
}

function useSampleVariables(): void {
  store.useSampleVariables()
  emit('saved', '[items-id]')
  ElMessage.success('示例变量已插入。')
}

async function chooseTag(tag: string): Promise<void> {
  const variable = store.variables.find((item) => item.tag === tag)
  if (!variable) {
    return
  }

  await openDetailDialog(variable)
}

function handleTabRemove(name: string | number): void {
  if (name === 'editor') {
    closeEditorTab()
  }
}

function handleDetailDialogClosed(): void {
  detailDialogTag.value = null
  detailLoading.value = false
  detailError.value = ''
}
</script>

<template>
  <div class="variable-layout">
    <div class="variable-config-panel">
      <div class="panel-toolbar">
        <div class="toolbar-copy">
          <strong>配置变量与后端字段映射</strong>
          <span>按照来源数据、Sheet 和列名逐级选择，标签名会直接用于规则编排、结果定位和变量详情查看。</span>
        </div>
        <div class="toolbar-actions">
          <el-button plain @click="useSampleVariables">加载示例变量</el-button>
          <el-button type="primary" :disabled="!store.sources.length" @click="openCreateTab">
            {{ store.variables.length ? '新增变量页签' : '添加首个变量' }}
          </el-button>
        </div>
      </div>

      <el-alert
        :title="variableGuide.title"
        :description="variableGuide.description"
        :type="variableGuide.type"
        :closable="false"
        show-icon
      />

      <el-tabs
        v-model="activeTab"
        class="variable-workspace-tabs"
        type="card"
        @tab-remove="handleTabRemove"
      >
        <el-tab-pane label="变量列表" name="summary">
          <el-table
            :data="store.variables"
            class="workbench-table"
            empty-text="先完成数据源接入，再添加变量抽取配置。"
          >
            <el-table-column label="变量标签" min-width="180">
              <template #default="{ row }">
                <button class="tag-button" type="button" @click="chooseTag(row.tag)">
                  {{ row.tag }}
                </button>
              </template>
            </el-table-column>
            <el-table-column prop="source_id" label="来源" min-width="120" />
            <el-table-column prop="sheet" label="Sheet" min-width="140" />
            <el-table-column prop="column" label="列名" min-width="140" />
            <el-table-column label="期望类型" min-width="120">
              <template #default="{ row }">
                {{ getExpectedTypeLabel(row.expected_type) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" align="right">
              <template #default="{ row }">
                <div class="table-actions">
                  <el-button link type="primary" @click="chooseTag(row.tag)">查看详情</el-button>
                  <el-button link type="primary" @click="openEditTab(row)">编辑</el-button>
                  <el-button link type="danger" @click="removeVariable(row.tag)">删除</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane
          v-if="editorVisible"
          :label="editingTag ? '编辑变量' : '新增变量'"
          name="editor"
          closable
        >
          <div class="variable-editor-panel">
            <el-alert
              v-if="metadataError"
              :title="metadataError"
              type="warning"
              :closable="false"
              show-icon
            />

            <el-form label-position="top">
              <el-form-item label="来源数据" :error="draftErrors.source_id">
                <el-select
                  :model-value="draft.source_id"
                  class="full-width"
                  filterable
                  placeholder="请选择已保存的数据源"
                  @update:model-value="handleSourceChange"
                >
                  <el-option
                    v-for="source in sourceOptions"
                    :key="source.id"
                    :label="source.id"
                    :value="source.id"
                  />
                </el-select>
              </el-form-item>

              <div class="dual-field">
                <el-form-item label="Sheet" :error="draftErrors.sheet">
                  <el-select
                    :model-value="draft.sheet"
                    class="full-width"
                    filterable
                    placeholder="请选择来源数据中的 Sheet"
                    :loading="isMetadataLoading"
                    :disabled="!draft.source_id || !canUseExcelMetadata || !sheetOptions.length"
                    no-data-text="当前没有可选 Sheet"
                    @update:model-value="handleSheetChange"
                  >
                    <el-option
                      v-for="sheet in sheetOptions"
                      :key="sheet.name"
                      :label="sheet.name"
                      :value="sheet.name"
                    />
                  </el-select>
                </el-form-item>

                <el-form-item label="列名" :error="draftErrors.column">
                  <el-select
                    :model-value="draft.column"
                    class="full-width"
                    filterable
                    placeholder="请选择当前 Sheet 中的列名"
                    :disabled="!draft.sheet || !columnOptions.length"
                    no-data-text="请先选择 Sheet"
                    @update:model-value="handleColumnChange"
                  >
                    <el-option
                      v-for="column in columnOptions"
                      :key="column"
                      :label="column"
                      :value="column"
                    />
                  </el-select>
                </el-form-item>
              </div>

              <el-form-item label="变量标签" :error="draftErrors.tag">
                <el-input
                  :model-value="draft.tag"
                  placeholder="[source-sheet-column]"
                  @input="handleTagInput"
                />
              </el-form-item>

              <el-form-item label="期望类型" :error="draftErrors.expected_type">
                <el-select
                  v-model="draft.expected_type"
                  class="full-width"
                  placeholder="请选择字符串或 JSON"
                >
                  <el-option
                    v-for="option in EXPECTED_TYPE_OPTIONS"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
              </el-form-item>
            </el-form>

            <div class="editor-footbar">
              <el-button plain @click="closeEditorTab">取消</el-button>
              <el-button type="primary" :disabled="!canSaveVariable" @click="saveVariable">
                保存变量
              </el-button>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <aside class="variable-pool-panel">
      <div class="pool-heading">
        <div>
          <h3>当前变量池</h3>
          <p>保存变量后，下方会形成可直接用于规则编排的标签池；点击标签或“查看详情”可快速核对映射。</p>
        </div>
        <el-tag v-if="store.activeTag" type="warning" round effect="light">高亮中</el-tag>
      </div>

      <div class="tag-pool">
        <button
          v-for="variable in store.variables"
          :key="variable.tag"
          type="button"
          class="pool-tag"
          :class="{ 'is-active': store.activeTag === variable.tag }"
          @click="chooseTag(variable.tag)"
        >
          <span>{{ variable.tag }}</span>
          <small>{{ variable.source_id }} / {{ variable.sheet }} / {{ variable.column }}</small>
        </button>

        <div v-if="!store.variables.length" class="empty-pool">
          变量保存后，下方会形成可直接用于规则编排的标签池；点击任意标签可弹出变量详情窗口。
        </div>
      </div>
    </aside>
  </div>

  <el-dialog
    v-model="detailDialogVisible"
    width="min(1200px, calc(100vw - 24px))"
    top="4vh"
    class="variable-detail-dialog"
    destroy-on-close
    @closed="handleDetailDialogClosed"
  >
    <template #header>
      <div class="detail-dialog-header">
        <strong>{{ detailVariable?.tag ?? '变量详情' }}</strong>
        <p>在当前窗口内查看变量映射信息和预览数据，确认无误后再继续进入规则编排。</p>
      </div>
    </template>

    <div v-if="detailVariable" class="detail-dialog-shell variable-detail-panel">
      <div class="detail-topbar">
        <div class="detail-copy">
          <strong>变量详情</strong>
          <span>详情窗口保持只读，会尽量加载当前列的完整预览数据，并在下方表格中滚动查看。</span>
        </div>
        <el-button plain @click="openDetailDialog(detailVariable, true)">刷新预览</el-button>
      </div>

      <div class="detail-meta-grid">
        <article class="detail-meta-item">
          <span>来源数据</span>
          <strong>{{ detailVariable.source_id }}</strong>
        </article>
        <article class="detail-meta-item">
          <span>Sheet</span>
          <strong>{{ detailVariable.sheet }}</strong>
        </article>
        <article class="detail-meta-item">
          <span>列名</span>
          <strong>{{ detailVariable.column }}</strong>
        </article>
        <article class="detail-meta-item">
          <span>期望类型</span>
          <strong>{{ getExpectedTypeLabel(detailVariable.expected_type) }}</strong>
        </article>
      </div>

      <div class="preview-summary preview-source-summary">
        <span>当前来源文件</span>
        <strong class="source-path-text">{{ detailSourcePath || '当前未记录来源路径。' }}</strong>
        <small>如果这里不是你预期的文件，请先回到步骤 1 检查数据源路径后再刷新预览。</small>
      </div>

      <el-alert
        v-if="detailError"
        :title="detailError"
        type="warning"
        :closable="false"
        show-icon
      />

      <div v-else-if="detailLoading" class="empty-pool">
        正在读取变量详情与列预览，请稍候。
      </div>

      <template v-else>
        <div class="preview-summary">
          <span>变量标签</span>
          <strong>{{ detailVariable.tag }}</strong>
          <small>
            已读取 {{ detailLoadedRows }} / {{ detailPreview?.total_rows ?? 0 }} 行预览数据
            <template v-if="detailPreview?.loaded_all_rows">，当前已加载完整列预览。</template>
          </small>
        </div>

        <el-alert
          v-if="detailHasEmptyPreview"
          title="当前列没有读取到任何数据。"
          type="info"
          :closable="false"
          show-icon
          description="请确认当前来源文件、Sheet 和列名是否与你预期的一致；如果文件本身没有数据，详情窗口会明确显示 0 / 0。"
        />

        <div class="detail-table-shell">
          <el-table
            :data="detailPreview?.preview_rows ?? []"
            class="workbench-table preview-table"
            max-height="560"
            empty-text="当前列没有可展示的预览数据；请先确认来源文件、Sheet 与列名是否正确。"
          >
            <el-table-column prop="row_index" label="原始行号" width="120" />
            <el-table-column label="预览值" min-width="260">
              <template #default="{ row }">
                <span class="preview-value">{{ formatPreviewValue(row.value) }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </template>
    </div>
  </el-dialog>
</template>

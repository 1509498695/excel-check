<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { fetchCompositePreview } from '../../api/workbench'
import { useWorkbenchStore } from '../../store/workbench'
import type { VariablePoolStoreLike } from '../../types/panelStores'
import type {
  CompositeVariablePreviewData,
  DataSource,
  VariableTag,
  VariablePreviewData,
} from '../../types/workbench'
import { EXPECTED_TYPE_OPTIONS } from '../../utils/workbenchMeta'

const props = withDefaults(
  defineProps<{
    store?: VariablePoolStoreLike
    variant?: 'workbench' | 'fixed-rules'
  }>(),
  {
    variant: 'workbench',
  },
)
const emit = defineEmits<{ saved: [tag: string]; changed: [] }>()

const defaultStore = useWorkbenchStore()
const store = props.store ?? defaultStore

const singleDialogVisible = ref(false)
const compositeDialogVisible = ref(false)
const singleEditingTag = ref<string | null>(null)
const compositeEditingTag = ref<string | null>(null)
const singleTagTouched = ref(false)
const compositeTagTouched = ref(false)
const singleMetadataLoading = ref(false)
const compositeMetadataLoading = ref(false)
const singleMetadataError = ref('')
const compositeMetadataError = ref('')
const compositePreviewLoading = ref(false)
const compositePreviewError = ref('')
const compositePreview = ref<CompositeVariablePreviewData | null>(null)

const detailDialogVisible = ref(false)
const detailDialogTag = ref<string | null>(null)
const detailLoading = ref(false)
const detailError = ref('')

const singleDraft = reactive<VariableTag>({
  tag: '',
  source_id: '',
  sheet: '',
  variable_kind: 'single',
  column: '',
  expected_type: 'str',
})
const compositeDraft = reactive<VariableTag>({
  tag: '',
  source_id: '',
  sheet: '',
  variable_kind: 'composite',
  columns: [],
  key_column: '',
  expected_type: 'json',
})
const singleErrors = reactive({ source_id: '', sheet: '', column: '', tag: '', expected_type: '' })
const compositeErrors = reactive({
  source_id: '',
  sheet: '',
  columns: '',
  key_column: '',
  tag: '',
})

const sourceOptions = computed<DataSource[]>(() => store.sources)
const singleDialogTitle = computed(() =>
  singleEditingTag.value ? '编辑单个变量' : '新增单个变量',
)
const compositeDialogTitle = computed(() =>
  compositeEditingTag.value ? '编辑组合变量' : '新增组合变量',
)
const isFixedRulesVariant = computed(() => props.variant === 'fixed-rules')
const panelCopy = computed(() => ({
  heading: isFixedRulesVariant.value ? '变量池' : '配置变量与后端字段映射',
  description: isFixedRulesVariant.value
    ? '维护本页变量。'
    : '点击上方按钮会在步骤 2 内打开独立子页签。保存后自动关闭当前页签，并回到变量列表。',
  emptySourceTitle: isFixedRulesVariant.value ? '请先接入数据源' : '请先完成步骤 1 的数据源接入',
  emptySourceDescription: isFixedRulesVariant.value
    ? '先保存数据源，再添加变量。'
    : '先保存至少一个数据源，再在这里添加单个变量或组合变量。',
  readyTitle: isFixedRulesVariant.value ? '可开始配置变量' : '数据源已就绪，可以开始构建变量池',
  readyDescription: isFixedRulesVariant.value
    ? '支持单变量和组合变量。'
    : '点击上方按钮会打开独立的变量编辑对话框。保存后会自动关闭当前对话框，并把变量写回下方列表和变量池。',
  poolTitle: isFixedRulesVariant.value ? '变量池已就绪' : '变量池已可复用',
  poolDescription: isFixedRulesVariant.value
    ? `已配置 ${store.variables.length} 个变量。`
    : `当前已配置 ${store.variables.length} 个变量。点击变量标签或“查看详情”可继续核对映射与预览。`,
  sourceTypeError: isFixedRulesVariant.value
    ? '当前固定规则页的字段映射提取先支持本地 Excel。'
    : '当前步骤 2 的字段映射提取先支持本地 Excel。',
  compositeTypeError: isFixedRulesVariant.value
    ? '当前固定规则页的组合变量提取先支持本地 Excel。'
    : '当前步骤 2 的组合变量提取先支持本地 Excel。',
  poolHeading: isFixedRulesVariant.value ? '当前变量池' : '当前变量池',
  poolDescriptionSecondary: isFixedRulesVariant.value
    ? '点击标签查看详情。'
    : '保存变量后，下方会形成可直接用于规则编排的标签池；点击标签可查看详情。',
  emptyPool: isFixedRulesVariant.value
    ? '保存后显示在这里。'
    : '变量保存后，下方会形成可直接用于规则编排的标签池；点击任意标签可弹出变量详情窗口。',
  singleDialogDescription: isFixedRulesVariant.value
    ? '选择来源、Sheet 和列。'
    : '按来源数据、Sheet 和列名提取一个可复用字段，用于后续静态规则编排。',
}))
const singleSource = computed<DataSource | null>(
  () => sourceOptions.value.find((item) => item.id === singleDraft.source_id) ?? null,
)
const compositeSource = computed<DataSource | null>(
  () => sourceOptions.value.find((item) => item.id === compositeDraft.source_id) ?? null,
)
const singleMetadata = computed(() => store.sourceMetadataMap[singleDraft.source_id] ?? null)
const compositeMetadata = computed(() => store.sourceMetadataMap[compositeDraft.source_id] ?? null)
const singleSheetOptions = computed(() => singleMetadata.value?.sheets ?? [])
const compositeSheetOptions = computed(() => compositeMetadata.value?.sheets ?? [])
const singleColumnOptions = computed(
  () => singleSheetOptions.value.find((sheet) => sheet.name === singleDraft.sheet)?.columns ?? [],
)
const compositeColumnOptions = computed(
  () =>
    compositeSheetOptions.value.find((sheet) => sheet.name === compositeDraft.sheet)?.columns ?? [],
)
const compositeKeyOptions = computed(() =>
  compositeDraft.columns?.filter((item): item is string => typeof item === 'string' && !!item) ?? [],
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
const detailPreview = computed<VariablePreviewData | null>(() =>
  detailVariable.value ? store.variablePreviewMap[detailVariable.value.tag] ?? null : null,
)
const detailLoadedRows = computed(() => {
  const preview = detailPreview.value
  if (!preview) return 0
  return preview.variable_kind === 'single'
    ? preview.preview_rows.length
    : preview.loaded_rows ?? Object.keys(preview.mapping).length
})
const detailSourcePath = computed(
  () =>
    detailPreview.value?.source_path ??
    detailSource.value?.pathOrUrl ??
    detailSource.value?.path ??
    detailSource.value?.url ??
    '',
)
const canSaveSingle = computed(
  () =>
    !singleMetadataLoading.value &&
    singleSource.value?.type === 'local_excel' &&
    !!singleDraft.source_id.trim() &&
    !!singleDraft.sheet.trim() &&
    !!singleDraft.column?.trim() &&
    !!singleDraft.tag.trim() &&
    !!singleDraft.expected_type,
)
const canSaveComposite = computed(
  () =>
    !compositeMetadataLoading.value &&
    !compositePreviewLoading.value &&
    compositeSource.value?.type === 'local_excel' &&
    !!compositeDraft.source_id.trim() &&
    !!compositeDraft.sheet.trim() &&
    !!compositeDraft.tag.trim() &&
    (compositeDraft.columns?.length ?? 0) >= 2 &&
    !!compositeDraft.key_column?.trim() &&
    compositeDraft.columns?.includes(compositeDraft.key_column ?? ''),
)
const variableGuide = computed(() => {
  if (!store.sources.length) {
    return {
      type: 'warning' as const,
      title: panelCopy.value.emptySourceTitle,
      description: panelCopy.value.emptySourceDescription,
    }
  }

  if (!store.variables.length) {
    return {
      type: 'info' as const,
      title: panelCopy.value.readyTitle,
      description: panelCopy.value.readyDescription,
    }
  }

  return {
    type: 'success' as const,
    title: panelCopy.value.poolTitle,
    description: panelCopy.value.poolDescription,
  }
})

function getSingleSuggestion(sourceId: string, sheet: string, column: string): string {
  return `[${sourceId || 'source'}-${sheet || 'sheet'}-${column || 'column'}]`
}

function getCompositeSuggestion(sourceId: string, sheet: string, keyColumn: string): string {
  return `[${sourceId || 'source'}-${sheet || 'sheet'}-${keyColumn || 'key'}-mapping]`
}

function syncSingleTag(): void {
  if (!singleTagTouched.value) {
    singleDraft.tag = getSingleSuggestion(
      singleDraft.source_id.trim(),
      singleDraft.sheet.trim(),
      singleDraft.column?.trim() ?? '',
    )
  }
}

function syncCompositeTag(): void {
  if (!compositeTagTouched.value) {
    compositeDraft.tag = getCompositeSuggestion(
      compositeDraft.source_id.trim(),
      compositeDraft.sheet.trim(),
      compositeDraft.key_column?.trim() ?? '',
    )
  }
}

function clearSingleErrors(): void {
  singleErrors.source_id = ''
  singleErrors.sheet = ''
  singleErrors.column = ''
  singleErrors.tag = ''
  singleErrors.expected_type = ''
}

function clearCompositeErrors(): void {
  compositeErrors.source_id = ''
  compositeErrors.sheet = ''
  compositeErrors.columns = ''
  compositeErrors.key_column = ''
  compositeErrors.tag = ''
}

function resetSingleDraft(): void {
  singleDraft.tag = ''
  singleDraft.source_id = store.preferredSourceId ?? store.sources[0]?.id ?? ''
  singleDraft.sheet = ''
  singleDraft.column = ''
  singleDraft.variable_kind = 'single'
  singleDraft.expected_type = 'str'
  singleTagTouched.value = false
  singleMetadataError.value = ''
  clearSingleErrors()
  syncSingleTag()
}

function resetCompositeDraft(): void {
  compositeDraft.tag = ''
  compositeDraft.source_id = store.preferredSourceId ?? store.sources[0]?.id ?? ''
  compositeDraft.sheet = ''
  compositeDraft.columns = []
  compositeDraft.key_column = ''
  compositeDraft.variable_kind = 'composite'
  compositeDraft.expected_type = 'json'
  compositeTagTouched.value = false
  compositeMetadataError.value = ''
  compositePreviewError.value = ''
  compositePreview.value = null
  clearCompositeErrors()
  syncCompositeTag()
}

async function prepareSingleEditorForSource(sourceId: string, preserve = false): Promise<void> {
  if (!sourceId) return
  if (singleSource.value?.type !== 'local_excel') {
    singleMetadataError.value = panelCopy.value.sourceTypeError
    if (!preserve) {
      singleDraft.sheet = ''
      singleDraft.column = ''
    }
    syncSingleTag()
    return
  }

  singleMetadataLoading.value = true
  singleMetadataError.value = ''
  try {
    const metadata = await store.loadSourceMetadata(sourceId)
    const matchedSheet = metadata.sheets.find((item) => item.name === singleDraft.sheet)
    if (!preserve || !matchedSheet) {
      singleDraft.sheet = ''
      singleDraft.column = ''
    } else if (!matchedSheet.columns.includes(singleDraft.column ?? '')) {
      singleDraft.column = ''
    }
    if (!metadata.sheets.length) singleMetadataError.value = '当前数据源没有读取到可用的 Sheet。'
    syncSingleTag()
  } catch (error) {
    singleMetadataError.value = error instanceof Error ? error.message : '读取数据源结构失败。'
    if (!preserve) {
      singleDraft.sheet = ''
      singleDraft.column = ''
    }
    ElMessage.error(singleMetadataError.value)
  } finally {
    singleMetadataLoading.value = false
  }
}

async function prepareCompositeEditorForSource(sourceId: string, preserve = false): Promise<void> {
  if (!sourceId) return
  if (compositeSource.value?.type !== 'local_excel') {
    compositeMetadataError.value = panelCopy.value.compositeTypeError
    if (!preserve) {
      compositeDraft.sheet = ''
      compositeDraft.columns = []
      compositeDraft.key_column = ''
    }
    compositePreview.value = null
    syncCompositeTag()
    return
  }

  compositeMetadataLoading.value = true
  compositeMetadataError.value = ''
  try {
    const metadata = await store.loadSourceMetadata(sourceId)
    const matchedSheet = metadata.sheets.find((item) => item.name === compositeDraft.sheet)
    if (!preserve || !matchedSheet) {
      compositeDraft.sheet = ''
      compositeDraft.columns = []
      compositeDraft.key_column = ''
    } else {
      const validColumns = new Set(matchedSheet.columns)
      compositeDraft.columns = (compositeDraft.columns ?? []).filter((item) => validColumns.has(item))
      if (!compositeDraft.columns.includes(compositeDraft.key_column ?? '')) {
        compositeDraft.key_column = ''
      }
    }
    if (!metadata.sheets.length) compositeMetadataError.value = '当前数据源没有读取到可用的 Sheet。'
    syncCompositeTag()
  } catch (error) {
    compositeMetadataError.value = error instanceof Error ? error.message : '读取数据源结构失败。'
    if (!preserve) {
      compositeDraft.sheet = ''
      compositeDraft.columns = []
      compositeDraft.key_column = ''
    }
    ElMessage.error(compositeMetadataError.value)
  } finally {
    compositeMetadataLoading.value = false
  }
}

async function refreshCompositePreview(): Promise<void> {
  compositePreview.value = null
  compositePreviewError.value = ''
  if (!canSaveComposite.value || !compositeSource.value) return

  compositePreviewLoading.value = true
  try {
    const response = await fetchCompositePreview({
      source: compositeSource.value,
      sheet: compositeDraft.sheet.trim(),
      columns: compositeDraft.columns ?? [],
      key_column: compositeDraft.key_column ?? '',
    })
    compositePreview.value = response.data
  } catch (error) {
    compositePreviewError.value = error instanceof Error ? error.message : '读取组合变量预览失败。'
  } finally {
    compositePreviewLoading.value = false
  }
}

async function openSingleCreateTab(): Promise<void> {
  resetSingleDraft()
  singleEditingTag.value = null
  singleDialogVisible.value = true
  await prepareSingleEditorForSource(singleDraft.source_id, false)
}

async function openCompositeCreateTab(): Promise<void> {
  resetCompositeDraft()
  compositeEditingTag.value = null
  compositeDialogVisible.value = true
  await prepareCompositeEditorForSource(compositeDraft.source_id, false)
}

async function openEditTab(variable: VariableTag): Promise<void> {
  if ((variable.variable_kind ?? 'single') === 'composite') {
    compositeEditingTag.value = variable.tag
    compositeDraft.tag = variable.tag
    compositeDraft.source_id = variable.source_id
    compositeDraft.sheet = variable.sheet
    compositeDraft.columns = [...(variable.columns ?? [])]
    compositeDraft.key_column = variable.key_column ?? ''
    compositeDraft.expected_type = 'json'
    compositeTagTouched.value =
      variable.tag.trim() !==
      getCompositeSuggestion(
        variable.source_id.trim(),
        variable.sheet.trim(),
        (variable.key_column ?? '').trim(),
      )
    compositeDialogVisible.value = true
    await prepareCompositeEditorForSource(variable.source_id, true)
    await refreshCompositePreview()
    return
  }

  singleEditingTag.value = variable.tag
  singleDraft.tag = variable.tag
  singleDraft.source_id = variable.source_id
  singleDraft.sheet = variable.sheet
  singleDraft.column = variable.column ?? ''
  singleDraft.expected_type = variable.expected_type ?? 'str'
  singleTagTouched.value =
    variable.tag.trim() !==
    getSingleSuggestion(
      variable.source_id.trim(),
      variable.sheet.trim(),
      (variable.column ?? '').trim(),
    )
  singleDialogVisible.value = true
  await prepareSingleEditorForSource(variable.source_id, true)
}

function closeSingleEditorTab(): void {
  singleDialogVisible.value = false
}

function closeCompositeEditorTab(): void {
  compositeDialogVisible.value = false
}

function handleSingleDialogClosed(): void {
  singleEditingTag.value = null
  resetSingleDraft()
}

function handleCompositeDialogClosed(): void {
  compositeEditingTag.value = null
  resetCompositeDraft()
}

async function handleSingleSourceChange(value: string): Promise<void> {
  singleDraft.source_id = value
  singleDraft.sheet = ''
  singleDraft.column = ''
  clearSingleErrors()
  syncSingleTag()
  await prepareSingleEditorForSource(value, false)
}

function handleSingleSheetChange(value: string): void {
  singleDraft.sheet = value
  singleDraft.column = ''
  singleErrors.sheet = ''
  singleErrors.column = ''
  syncSingleTag()
}

function handleSingleColumnChange(value: string): void {
  singleDraft.column = value
  singleErrors.column = ''
  syncSingleTag()
}

function handleSingleTagInput(value: string): void {
  singleDraft.tag = value
  singleErrors.tag = ''
  singleTagTouched.value = true
}

async function handleCompositeSourceChange(value: string): Promise<void> {
  compositeDraft.source_id = value
  compositeDraft.sheet = ''
  compositeDraft.columns = []
  compositeDraft.key_column = ''
  clearCompositeErrors()
  syncCompositeTag()
  await prepareCompositeEditorForSource(value, false)
  await refreshCompositePreview()
}

async function handleCompositeSheetChange(value: string): Promise<void> {
  compositeDraft.sheet = value
  compositeDraft.columns = []
  compositeDraft.key_column = ''
  compositeErrors.sheet = ''
  compositeErrors.columns = ''
  compositeErrors.key_column = ''
  syncCompositeTag()
  await refreshCompositePreview()
}

async function handleCompositeColumnsChange(value: string[]): Promise<void> {
  compositeDraft.columns = [...new Set(value)]
  if (!compositeDraft.columns.includes(compositeDraft.key_column ?? '')) {
    compositeDraft.key_column = ''
  }
  compositeErrors.columns = ''
  compositeErrors.key_column = ''
  syncCompositeTag()
  await refreshCompositePreview()
}

async function handleCompositeKeyChange(value: string): Promise<void> {
  compositeDraft.key_column = value
  compositeErrors.key_column = ''
  syncCompositeTag()
  await refreshCompositePreview()
}

function handleCompositeTagInput(value: string): void {
  compositeDraft.tag = value
  compositeErrors.tag = ''
  compositeTagTouched.value = true
}

function validateSingleDraft(): boolean {
  clearSingleErrors()
  if (!singleDraft.source_id.trim()) singleErrors.source_id = '请选择来源数据。'
  if (!singleDraft.sheet.trim()) singleErrors.sheet = '请选择 Sheet。'
  if (!singleDraft.column?.trim()) singleErrors.column = '请选择列名。'
  if (!singleDraft.tag.trim()) singleErrors.tag = '请输入变量标签。'
  if (
    singleDraft.tag.trim() &&
    store.variables.some(
      (item) => item.tag === singleDraft.tag.trim() && item.tag !== singleEditingTag.value,
    )
  ) {
    singleErrors.tag = '变量标签已存在，请保持唯一。'
  }
  if (!singleDraft.expected_type) singleErrors.expected_type = '请选择期望类型。'
  return !Object.values(singleErrors).some(Boolean)
}

function validateCompositeDraft(): boolean {
  clearCompositeErrors()
  if (!compositeDraft.source_id.trim()) compositeErrors.source_id = '请选择来源数据。'
  if (!compositeDraft.sheet.trim()) compositeErrors.sheet = '请选择 Sheet。'
  if ((compositeDraft.columns?.length ?? 0) < 2) compositeErrors.columns = '至少选择 2 列。'
  if (!compositeDraft.key_column?.trim()) compositeErrors.key_column = '请选择 key 列。'
  if (
    compositeDraft.key_column &&
    !compositeDraft.columns?.includes(compositeDraft.key_column)
  ) {
    compositeErrors.key_column = 'key 列必须来自已选关联列。'
  }
  if (!compositeDraft.tag.trim()) compositeErrors.tag = '请输入变量标签。'
  if (
    compositeDraft.tag.trim() &&
    store.variables.some(
      (item) => item.tag === compositeDraft.tag.trim() && item.tag !== compositeEditingTag.value,
    )
  ) {
    compositeErrors.tag = '变量标签已存在，请保持唯一。'
  }
  return !Object.values(compositeErrors).some(Boolean)
}

async function saveSingleVariable(): Promise<void> {
  if (!validateSingleDraft()) {
    ElMessage.warning('请先完整填写单个变量信息。')
    return
  }
  const nextTag = singleDraft.tag.trim()
  store.upsertVariable(
    {
      tag: nextTag,
      source_id: singleDraft.source_id.trim(),
      sheet: singleDraft.sheet.trim(),
      variable_kind: 'single',
      column: singleDraft.column?.trim(),
      expected_type: singleDraft.expected_type ?? 'str',
    },
    singleEditingTag.value ?? undefined,
  )
  emit('saved', nextTag)
  emit('changed')
  closeSingleEditorTab()
  ElMessage.success(singleEditingTag.value ? '单个变量已更新。' : '单个变量已添加。')
}

async function saveCompositeVariable(): Promise<void> {
  if (!validateCompositeDraft()) {
    ElMessage.warning('请先完整填写组合变量信息。')
    return
  }
  await refreshCompositePreview()
  const nextTag = compositeDraft.tag.trim()
  store.upsertVariable(
    {
      tag: nextTag,
      source_id: compositeDraft.source_id.trim(),
      sheet: compositeDraft.sheet.trim(),
      variable_kind: 'composite',
      columns: [...(compositeDraft.columns ?? [])],
      key_column: compositeDraft.key_column?.trim(),
      expected_type: 'json',
    },
    compositeEditingTag.value ?? undefined,
  )
  emit('saved', nextTag)
  emit('changed')
  closeCompositeEditorTab()
  ElMessage.success(compositeEditingTag.value ? '组合变量已更新。' : '组合变量已添加。')
}

function removeVariable(tag: string): void {
  store.removeVariable(tag)
  emit('changed')
  if (detailDialogTag.value === tag) detailDialogVisible.value = false
  ElMessage.success('变量已移除。')
}

async function chooseTag(tag: string): Promise<void> {
  const variable = store.variables.find((item) => item.tag === tag)
  if (!variable) return
  detailDialogTag.value = variable.tag
  detailDialogVisible.value = true
  store.setActiveTag(variable.tag)
  detailLoading.value = true
  detailError.value = ''
  try {
    await store.loadVariablePreview(variable, undefined, true)
  } catch (error) {
    detailError.value = error instanceof Error ? error.message : '读取变量详情失败。'
    ElMessage.error(detailError.value)
  } finally {
    detailLoading.value = false
  }
}

function handleDetailDialogClosed(): void {
  detailDialogTag.value = null
  detailError.value = ''
  detailLoading.value = false
}

function formatJsonPreview(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return '[无法格式化 JSON]'
  }
}

function getExpectedTypeLabel(value?: string | null): string {
  return EXPECTED_TYPE_OPTIONS.find((item) => item.value === value)?.label ?? '未指定'
}

function getVariableKindLabel(variable: VariableTag): string {
  return (variable.variable_kind ?? 'single') === 'composite' ? '组合变量 / JSON' : '单个变量'
}

function getVariableFieldSummary(variable: VariableTag): string {
  return (variable.variable_kind ?? 'single') === 'composite'
    ? `key: ${variable.key_column ?? '-'} / 列: ${(variable.columns ?? []).join('、')}`
    : variable.column ?? '-'
}
</script>

<template>
  <div class="variable-layout">
    <div class="variable-config-panel">
      <div class="panel-toolbar">
        <div class="toolbar-copy">
          <strong>{{ panelCopy.heading }}</strong>
          <span>{{ panelCopy.description }}</span>
        </div>
        <div class="toolbar-actions">
          <el-button plain :disabled="!store.sources.length" @click="openCompositeCreateTab">添加组合变量</el-button>
          <el-button type="primary" :disabled="!store.sources.length" @click="openSingleCreateTab">添加单个变量</el-button>
        </div>
      </div>

      <el-alert
        :title="variableGuide.title"
        :description="variableGuide.description"
        :type="variableGuide.type"
        :closable="false"
        show-icon
      />

      <div class="variable-summary-panel">
        <el-table
          :data="store.variables"
          class="workbench-table"
          empty-text="请先添加单个变量或组合变量。"
        >
          <el-table-column label="变量标签" min-width="180">
            <template #default="{ row }">
              <button class="tag-button" type="button" @click="chooseTag(row.tag)">
                {{ row.tag }}
              </button>
            </template>
          </el-table-column>
          <el-table-column label="变量类型" min-width="130">
            <template #default="{ row }">{{ getVariableKindLabel(row) }}</template>
          </el-table-column>
          <el-table-column prop="source_id" label="来源" min-width="120" />
          <el-table-column prop="sheet" label="Sheet" min-width="120" />
          <el-table-column label="字段结构" min-width="220">
            <template #default="{ row }">{{ getVariableFieldSummary(row) }}</template>
          </el-table-column>
          <el-table-column label="期望类型" min-width="120">
            <template #default="{ row }">{{ getExpectedTypeLabel(row.expected_type) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="210" align="right">
            <template #default="{ row }">
              <div class="table-actions">
                <el-button link type="primary" @click="chooseTag(row.tag)">查看详情</el-button>
                <el-button link type="primary" @click="openEditTab(row)">编辑</el-button>
                <el-button link type="danger" @click="removeVariable(row.tag)">删除</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <aside class="variable-pool-panel">
      <div class="pool-heading">
        <div>
          <h3>{{ panelCopy.poolHeading }}</h3>
          <p>{{ panelCopy.poolDescriptionSecondary }}</p>
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
          <small>{{ getVariableKindLabel(variable) }} / {{ variable.source_id }} / {{ variable.sheet }} / {{ getVariableFieldSummary(variable) }}</small>
        </button>
        <div v-if="!store.variables.length" class="empty-pool">{{ panelCopy.emptyPool }}</div>
      </div>
    </aside>
  </div>

  <el-dialog
    v-model="singleDialogVisible"
    :title="singleDialogTitle"
    width="640px"
    destroy-on-close
    class="variable-editor-dialog"
    @closed="handleSingleDialogClosed"
  >
    <div class="dialog-form variable-editor-panel">
      <div class="detail-copy">
        <strong>单个变量配置</strong>
        <span>{{ panelCopy.singleDialogDescription }}</span>
      </div>

      <el-alert
        v-if="singleMetadataError"
        :title="singleMetadataError"
        type="warning"
        :closable="false"
        show-icon
      />

      <el-form label-position="top">
        <el-form-item label="来源数据" :error="singleErrors.source_id">
          <el-select
            :model-value="singleDraft.source_id"
            class="full-width"
            filterable
            placeholder="请选择来源数据"
            @update:model-value="handleSingleSourceChange"
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
          <el-form-item label="Sheet" :error="singleErrors.sheet">
            <el-select
              :model-value="singleDraft.sheet"
              class="full-width"
              filterable
              placeholder="请选择 Sheet"
              :loading="singleMetadataLoading"
              :disabled="!singleDraft.source_id || !singleSheetOptions.length"
              @update:model-value="handleSingleSheetChange"
            >
              <el-option
                v-for="sheet in singleSheetOptions"
                :key="sheet.name"
                :label="sheet.name"
                :value="sheet.name"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="列名" :error="singleErrors.column">
            <el-select
              :model-value="singleDraft.column"
              class="full-width"
              filterable
              placeholder="请选择列名"
              :disabled="!singleDraft.sheet || !singleColumnOptions.length"
              @update:model-value="handleSingleColumnChange"
            >
              <el-option
                v-for="column in singleColumnOptions"
                :key="column"
                :label="column"
                :value="column"
              />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="变量标签" :error="singleErrors.tag">
          <el-input
            :model-value="singleDraft.tag"
            placeholder="[source-sheet-column]"
            @input="handleSingleTagInput"
          />
        </el-form-item>
        <el-form-item label="期望类型" :error="singleErrors.expected_type">
          <el-select
            v-model="singleDraft.expected_type"
            class="full-width"
            placeholder="请选择期望类型"
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
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button plain @click="closeSingleEditorTab">取消</el-button>
        <el-button type="primary" :disabled="!canSaveSingle" @click="saveSingleVariable">
          保存变量
        </el-button>
      </div>
    </template>
  </el-dialog>

  <el-dialog
    v-model="compositeDialogVisible"
    :title="compositeDialogTitle"
    width="760px"
    destroy-on-close
    class="variable-editor-dialog"
    @closed="handleCompositeDialogClosed"
  >
    <div class="dialog-form variable-editor-panel">
      <div class="detail-copy">
        <strong>组合变量配置</strong>
        <span>选择列并指定 Key。</span>
      </div>

      <el-alert
        v-if="compositeMetadataError"
        :title="compositeMetadataError"
        type="warning"
        :closable="false"
        show-icon
      />

      <el-form label-position="top">
        <el-form-item label="来源数据" :error="compositeErrors.source_id">
          <el-select
            :model-value="compositeDraft.source_id"
            class="full-width"
            filterable
            placeholder="请选择来源数据"
            @update:model-value="handleCompositeSourceChange"
          >
            <el-option
              v-for="source in sourceOptions"
              :key="source.id"
              :label="source.id"
              :value="source.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="Sheet" :error="compositeErrors.sheet">
          <el-select
            :model-value="compositeDraft.sheet"
            class="full-width"
            filterable
            placeholder="请选择 Sheet"
            :loading="compositeMetadataLoading"
            :disabled="!compositeDraft.source_id || !compositeSheetOptions.length"
            @update:model-value="handleCompositeSheetChange"
          >
            <el-option
              v-for="sheet in compositeSheetOptions"
              :key="sheet.name"
              :label="sheet.name"
              :value="sheet.name"
            />
          </el-select>
        </el-form-item>
        <div class="dual-field">
          <el-form-item label="关联列" :error="compositeErrors.columns">
            <el-select
              :model-value="compositeDraft.columns"
              multiple
              filterable
              collapse-tags
              collapse-tags-tooltip
              class="full-width"
              placeholder="至少选择 2 列"
              :disabled="!compositeDraft.sheet || !compositeColumnOptions.length"
              @update:model-value="handleCompositeColumnsChange"
            >
              <el-option
                v-for="column in compositeColumnOptions"
                :key="column"
                :label="column"
                :value="column"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="Key 列" :error="compositeErrors.key_column">
            <el-select
              :model-value="compositeDraft.key_column"
              class="full-width"
              placeholder="请选择作为主键的 Key 列"
              :disabled="!compositeKeyOptions.length"
              @update:model-value="handleCompositeKeyChange"
            >
              <el-option
                v-for="column in compositeKeyOptions"
                :key="column"
                :label="column"
                :value="column"
              />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="变量标签" :error="compositeErrors.tag">
          <el-input
            :model-value="compositeDraft.tag"
            placeholder="[source-sheet-key-mapping]"
            @input="handleCompositeTagInput"
          />
        </el-form-item>
        <el-form-item label="期望类型">
          <el-input model-value="json" disabled />
        </el-form-item>
      </el-form>

      <div class="dialog-footer composite-dialog-actions">
        <el-button plain @click="closeCompositeEditorTab">取消</el-button>
        <el-button type="primary" :disabled="!canSaveComposite" @click="saveCompositeVariable">
          保存变量
        </el-button>
      </div>

      <div class="composite-preview-panel">
        <div class="detail-copy">
          <strong>JSON 预览</strong>
          <span>预览当前 JSON 结构。</span>
        </div>
        <el-alert
          v-if="compositePreviewError"
          :title="compositePreviewError"
          type="warning"
          :closable="false"
          show-icon
        />
        <div v-else-if="compositePreviewLoading" class="empty-pool">
          正在生成预览。
        </div>
        <div v-else-if="!compositePreview" class="empty-pool">
          选择来源、Sheet、关联列和 Key 列后显示。
        </div>
        <div v-else class="json-preview-shell">
          <div class="preview-summary">
            <span>预览统计</span>
            <strong>
              {{ compositePreview!.total_rows }} 行 /
              {{ Object.keys(compositePreview!.mapping).length }} 个 key
            </strong>
            <small>
              Key：{{ compositePreview!.key_column }}
            </small>
          </div>
          <pre class="json-preview-block">{{ formatJsonPreview(compositePreview!.mapping) }}</pre>
        </div>

      </div>
    </div>
  </el-dialog>

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
        <strong>{{ detailVariable?.tag ?? '未命名变量' }}</strong>
        <p>查看来源、结构和预览。</p>
      </div>
    </template>

    <div v-if="detailVariable" class="detail-dialog-shell variable-detail-panel">
      <div class="detail-topbar">
        <div class="detail-copy">
          <strong>变量详情</strong>
          <span>单变量显示列预览，组合变量显示 JSON。</span>
        </div>
        <el-button plain @click="chooseTag(detailVariable.tag)">高亮变量</el-button>
      </div>
      <div class="detail-meta-grid" :class="{ 'detail-meta-grid--composite': detailPreview?.variable_kind === 'composite' }">
        <article class="detail-meta-item"><span>来源数据</span><strong>{{ detailVariable.source_id }}</strong></article>
        <article class="detail-meta-item"><span>Sheet</span><strong>{{ detailVariable.sheet }}</strong></article>
        <article class="detail-meta-item"><span>变量类型</span><strong>{{ getVariableKindLabel(detailVariable) }}</strong></article>
        <article class="detail-meta-item"><span>期望类型</span><strong>{{ getExpectedTypeLabel(detailVariable.expected_type) }}</strong></article>
      </div>
      <div class="preview-summary preview-source-summary">
        <span>来源路径</span>
        <strong class="source-path-text">{{ detailSourcePath || '当前没有可展示的来源路径。' }}</strong>
        <small>用于确认当前来源。</small>
      </div>
      <el-alert v-if="detailError" :title="detailError" type="warning" :closable="false" show-icon />
      <div v-else-if="detailLoading" class="empty-pool">正在加载变量详情，请稍候。</div>
      <template v-else>
        <div class="preview-summary">
          <span>预览数据</span>
          <strong>{{ detailVariable.tag }}</strong>
          <small>已加载 {{ detailLoadedRows }} / {{ detailPreview?.total_rows ?? 0 }} 行。</small>
        </div>
        <div v-if="detailPreview?.variable_kind === 'composite'" class="json-preview-shell">
          <div class="preview-summary">
            <span>字段结构</span>
            <strong>key: {{ detailPreview.key_column }}</strong>
            <small>关联列：{{ detailPreview.columns.join('、') }}</small>
          </div>
          <pre class="json-preview-block detail-json-block">{{ formatJsonPreview(detailPreview.mapping) }}</pre>
        </div>
        <div v-else class="detail-table-shell">
          <el-table :data="detailPreview?.preview_rows ?? []" class="workbench-table preview-table" max-height="560" empty-text="当前没有可展示的预览数据。">
            <el-table-column prop="row_index" label="行号" width="120" />
            <el-table-column label="值" min-width="260">
              <template #default="{ row }"><span class="preview-value">{{ row.value ?? '空值' }}</span></template>
            </el-table-column>
          </el-table>
        </div>
      </template>
    </div>
  </el-dialog>
</template>

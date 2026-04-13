<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { pickLocalSourcePath } from '../../api/workbench'
import { useWorkbenchStore } from '../../store/workbench'
import type { SourceManagementStoreLike } from '../../types/panelStores'
import type { DataSource, SourceType } from '../../types/workbench'
import { getSourceTypeLabel, SOURCE_TYPE_OPTIONS } from '../../utils/workbenchMeta'

const props = withDefaults(
  defineProps<{
    store?: SourceManagementStoreLike
    sourceIssues?: Record<string, string>
    variant?: 'workbench' | 'fixed-rules'
  }>(),
  {
    sourceIssues: () => ({}),
    variant: 'workbench',
  },
)

const emit = defineEmits<{
  saved: [sourceId: string]
  changed: []
}>()

const defaultStore = useWorkbenchStore()
const store = props.store ?? defaultStore
const sourceIssueMap = computed(() => props.sourceIssues ?? {})
const isFixedRulesVariant = computed(() => props.variant === 'fixed-rules')

const dialogVisible = ref(false)
const editingId = ref<string | null>(null)
const isPicking = ref(false)

const draft = reactive<DataSource>({
  id: '',
  type: 'local_excel',
  pathOrUrl: '',
  token: '',
})

const draftErrors = reactive({
  id: '',
  pathOrUrl: '',
})

const supports = computed(() => store.capabilities)
const localSource = computed(() => draft.type === 'local_excel' || draft.type === 'local_csv')
const needsToken = computed(() => draft.type === 'feishu')
const panelCopy = computed(() => ({
  heading: isFixedRulesVariant.value ? '数据源管理' : '统一管理本地文件、飞书和 SVN 入口',
  description: isFixedRulesVariant.value
    ? '本页数据源独立保存。'
    : '本地 Excel / CSV 会通过系统文件选择框记录真实本地路径，不再复制文件到项目运行目录。',
  sampleAction: isFixedRulesVariant.value ? '加载样例' : '加载示例数据源',
  emptyText: isFixedRulesVariant.value ? '暂无数据源。' : '还没有录入数据源。',
  localHelperReady: isFixedRulesVariant.value
    ? '先选文件，再保存。'
    : '请先完成系统文件选择，再点击“保存数据源”。选中文件后会把真实本地绝对路径写入当前输入框。',
  localHelperEmpty: isFixedRulesVariant.value
    ? '先填标识，再选文件。'
    : '请先填写数据源标识，再点击“选择文件”。系统文件框会在本机打开，并把真实本地绝对路径写入当前输入框。',
}))
const canPickLocalFile = computed(
  () => localSource.value && !isPicking.value && draft.id.trim().length > 0,
)
const canSaveSource = computed(() => {
  const path = draft.pathOrUrl?.trim() ?? ''
  return !isPicking.value && draft.id.trim().length > 0 && path.length > 0 && validatePathByType(path)
})

function resetDraft(): void {
  draft.id = ''
  draft.type = 'local_excel'
  draft.pathOrUrl = ''
  draft.token = ''
  clearDraftErrors()
}

function clearDraftErrors(): void {
  draftErrors.id = ''
  draftErrors.pathOrUrl = ''
}

function openCreateDialog(): void {
  editingId.value = null
  resetDraft()
  dialogVisible.value = true
}

function openEditDialog(source: DataSource): void {
  editingId.value = source.id
  draft.id = source.id
  draft.type = source.type
  draft.pathOrUrl = source.pathOrUrl ?? source.path ?? source.url ?? ''
  draft.token = source.token ?? ''
  clearDraftErrors()
  dialogVisible.value = true
}

function useSampleSource(): void {
  store.useSampleSource()
  emit('saved', 'src_demo')
  emit('changed')
  ElMessage.success('示例数据源已填入。')
}

function removeSource(sourceId: string): void {
  store.removeSource(sourceId)
  emit('changed')
  ElMessage.success('数据源已移除。')
}

function handleSourceTypeChange(nextType: SourceType): void {
  draft.type = nextType
  draftErrors.pathOrUrl = ''

  if (nextType === 'local_excel' || nextType === 'local_csv') {
    draft.pathOrUrl = ''
    return
  }

  draft.pathOrUrl = draft.pathOrUrl?.trim() ?? ''
}

function validatePathByType(path: string): boolean {
  const lowerPath = path.toLowerCase()

  if (draft.type === 'local_excel') {
    return lowerPath.endsWith('.xlsx') || lowerPath.endsWith('.xls')
  }

  if (draft.type === 'local_csv') {
    return lowerPath.endsWith('.csv')
  }

  return true
}

function validateDraft(): boolean {
  clearDraftErrors()

  if (!draft.id.trim()) {
    draftErrors.id = '请输入数据源标识。'
  }

  if (!draft.pathOrUrl?.trim()) {
    draftErrors.pathOrUrl = localSource.value ? '请选择或输入本地文件路径。' : '请输入链接或目录路径。'
  } else if (!validatePathByType(draft.pathOrUrl.trim())) {
    draftErrors.pathOrUrl =
      draft.type === 'local_csv'
        ? '本地 CSV 数据源仅支持 .csv 文件。'
        : '本地 Excel 数据源仅支持 .xls 或 .xlsx 文件。'
  }

  return !draftErrors.id && !draftErrors.pathOrUrl
}

async function saveSource(): Promise<void> {
  if (!validateDraft()) {
    ElMessage.warning('请先完善必填项后再保存数据源。')
    return
  }

  const sourceId = draft.id.trim()
  store.upsertSource(
    {
      id: sourceId,
      type: draft.type,
      pathOrUrl: draft.pathOrUrl?.trim(),
      token: draft.token?.trim(),
    },
    editingId.value ?? undefined,
  )
  dialogVisible.value = false
  emit('saved', sourceId)
  emit('changed')
  ElMessage.success(editingId.value ? '数据源已更新。' : '数据源已添加。')
}

function getStatusTone(source: DataSource): 'success' | 'warning' | 'info' {
  if (sourceIssueMap.value[source.id]) {
    return 'warning'
  }

  if (source.type === 'feishu' && !source.token) {
    return 'warning'
  }

  if (source.type === 'svn') {
    return 'info'
  }

  return 'success'
}

function getStatusLabel(source: DataSource): string {
  if (sourceIssueMap.value[source.id]) {
    return '路径失效'
  }
  if (source.type === 'feishu' && !source.token) {
    return '待授权'
  }

  if (source.type === 'svn') {
    return '待同步'
  }

  return '已就绪'
}

function getPathLabel(sourceType: SourceType): string {
  if (sourceType === 'feishu') {
    return '飞书链接'
  }

  if (sourceType === 'svn') {
    return 'SVN 目录'
  }

  return '本地路径'
}

function getSourceIssue(sourceId: string): string {
  return sourceIssueMap.value[sourceId] ?? ''
}

async function chooseLocalFile(): Promise<void> {
  if (!localSource.value || isPicking.value) {
    return
  }

  if (!draft.id.trim()) {
    draftErrors.id = '请先填写数据源标识。'
    ElMessage.warning('请先填写数据源标识，再选择本地文件。')
    return
  }

  isPicking.value = true
  draftErrors.pathOrUrl = ''

  try {
    const response = await pickLocalSourcePath(draft.type as 'local_excel' | 'local_csv')

    if (response.code !== 200 || !response.data.selected_path) {
      ElMessage.info('已取消选择文件。')
      return
    }

    draft.pathOrUrl = response.data.selected_path
    ElMessage.success('已记录真实本地路径。')
  } catch (error) {
    draftErrors.pathOrUrl = error instanceof Error ? error.message : '选择本地文件失败。'
    ElMessage.error(draftErrors.pathOrUrl)
  } finally {
    isPicking.value = false
  }
}
</script>

<template>
  <div class="panel-stack">
    <div class="capability-row">
      <span class="meta-label">当前后端声明支持</span>
      <div class="capability-list">
        <el-tag v-for="item in supports" :key="item" effect="plain" round type="info">
          {{ getSourceTypeLabel(item) }}
        </el-tag>
      </div>
    </div>

    <div class="panel-toolbar">
      <div class="toolbar-copy">
        <strong>{{ panelCopy.heading }}</strong>
        <span>{{ panelCopy.description }}</span>
      </div>
      <div class="toolbar-actions">
        <el-button plain @click="useSampleSource">{{ panelCopy.sampleAction }}</el-button>
        <el-button type="primary" @click="openCreateDialog">新增数据源</el-button>
      </div>
    </div>

    <el-table :data="store.sources" class="workbench-table" :empty-text="panelCopy.emptyText">
      <el-table-column label="标识" min-width="160">
        <template #default="{ row }">
          <div class="mono-chip">{{ row.id }}</div>
        </template>
      </el-table-column>
      <el-table-column label="类型" min-width="140">
        <template #default="{ row }">
          {{ getSourceTypeLabel(row.type) }}
        </template>
      </el-table-column>
      <el-table-column label="路径 / 链接" min-width="340">
        <template #default="{ row }">
          <div>
            <span class="truncate-line">{{ row.pathOrUrl ?? row.path ?? row.url }}</span>
            <small
              v-if="getSourceIssue(row.id)"
              style="display: block; margin-top: 4px; color: var(--el-color-warning)"
            >
              {{ getSourceIssue(row.id) }}
            </small>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="状态" min-width="120">
        <template #default="{ row }">
          <el-tag :type="getStatusTone(row)" effect="light" round>
            {{ getStatusLabel(row) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="170" align="right">
        <template #default="{ row }">
          <div class="table-actions">
            <el-button link type="primary" @click="openEditDialog(row)">编辑</el-button>
            <el-button link type="danger" @click="removeSource(row.id)">删除</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑数据源' : '新增数据源'"
      width="600px"
      destroy-on-close
    >
      <div class="dialog-form">
        <el-form label-position="top">
          <el-form-item label="数据源标识" :error="draftErrors.id">
            <el-input
              v-model="draft.id"
              placeholder="例如：src_items、src_drop_table"
              maxlength="48"
              @input="draftErrors.id = ''"
            />
          </el-form-item>

          <el-form-item label="数据源类型">
            <el-select
              :model-value="draft.type"
              class="full-width"
              @update:model-value="handleSourceTypeChange"
            >
              <el-option
                v-for="option in SOURCE_TYPE_OPTIONS"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </el-form-item>

          <el-form-item :label="getPathLabel(draft.type)" :error="draftErrors.pathOrUrl">
            <div class="field-with-action">
              <el-input
                v-model="draft.pathOrUrl"
                :placeholder="localSource ? '请选择或输入本地文件路径' : '请输入链接或目录路径'"
                @input="draftErrors.pathOrUrl = ''"
              />
              <el-button
                v-if="localSource"
                plain
                :loading="isPicking"
                :disabled="!canPickLocalFile"
                class="field-action-button"
                @click="chooseLocalFile"
              >
                {{ isPicking ? '文件选择中' : '选择文件' }}
              </el-button>
            </div>

            <span v-if="localSource" class="field-helper">
              {{
                draft.id.trim()
                  ? panelCopy.localHelperReady
                  : panelCopy.localHelperEmpty
              }}
            </span>
          </el-form-item>

          <el-form-item v-if="needsToken" label="访问令牌">
            <el-input
              v-model="draft.token"
              type="password"
              show-password
              placeholder="飞书接入时可预留 token"
            />
          </el-form-item>
        </el-form>
      </div>

      <template #footer>
        <div class="dialog-footer">
          <el-button plain @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :disabled="!canSaveSource" @click="saveSource">
            保存数据源
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { pickLocalSourcePath } from '../../api/workbench'
import {
  ensureTrailingSlash,
  getDefaultSvnCredentialTestDirUrl,
  isHttpDirUrl,
  parseSvnHost,
  type SvnCredentialItem,
  listSvnCredentialHosts,
} from '../../api/svn'
import SvnPickerDialog from './SvnPickerDialog.vue'
import SvnCredentialDialog from './SvnCredentialDialog.vue'
import { useWorkbenchStore } from '../../store/workbench'
import type { SourceManagementStoreLike } from '../../types/panelStores'
import type { DataSource, SourceType } from '../../types/workbench'
import { getSourceTypeLabel, SOURCE_TYPE_OPTIONS } from '../../utils/workbenchMeta'

const props = withDefaults(
  defineProps<{
    store?: SourceManagementStoreLike
    sourceIssues?: Record<string, string>
    variant?: 'workbench' | 'fixed-rules'
    toolbarMode?: 'embedded' | 'hidden'
  }>(),
  {
    sourceIssues: () => ({}),
    variant: 'workbench',
    toolbarMode: 'embedded',
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

const localSource = computed(() => draft.type === 'local_excel' || draft.type === 'local_csv')
const needsToken = computed(() => draft.type === 'feishu')
const isSvnSource = computed(() => draft.type === 'svn')

// SVN 子模式：远端 URL（默认）或本地工作副本路径
const svnSubMode = ref<'remote' | 'working_copy'>('remote')

const svnPickerVisible = ref(false)
const svnCredentialDialogVisible = ref(false)
const svnCredentialDialogHost = ref('')
const svnCredentialDialogDefaultTestDirUrl = ref('')
const svnCredentialDialogDefaultUsername = ref('')
const svnPickerDirUrl = ref('')
const svnCredentialItems = ref<SvnCredentialItem[]>([])

const panelCopy = computed(() => ({
  emptyText: isFixedRulesVariant.value ? '暂无数据源。' : '还没有录入数据源。',
  localHelperReady: '先填标识，再选文件；本机系统弹窗会返回真实绝对路径',
  localHelperEmpty: '先填标识，再选文件；本机系统弹窗会返回真实绝对路径',
}))
const canPickLocalFile = computed(
  () => localSource.value && !isPicking.value && draft.id.trim().length > 0,
)
const canBrowseSvnDirectory = computed(
  () =>
    isSvnSource.value &&
    svnSubMode.value === 'remote' &&
    draft.id.trim().length > 0 &&
    isHttpDirUrl(draft.pathOrUrl?.trim() ?? ''),
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
  svnSubMode.value = 'remote'
  dialogVisible.value = true
  void refreshSvnCredentialItems()
}

function openEditDialog(source: DataSource): void {
  editingId.value = source.id
  draft.id = source.id
  draft.type = source.type
  draft.pathOrUrl = source.pathOrUrl ?? source.path ?? source.url ?? ''
  draft.token = source.token ?? ''
  if (source.type === 'svn') {
    svnSubMode.value = isRemoteSvnSource(source) ? 'remote' : 'working_copy'
  } else {
    svnSubMode.value = 'remote'
  }
  clearDraftErrors()
  dialogVisible.value = true
  void refreshSvnCredentialItems()
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

  if (nextType === 'svn') {
    svnSubMode.value = 'remote'
    draft.pathOrUrl = ''
    return
  }

  draft.pathOrUrl = draft.pathOrUrl?.trim() ?? ''
}

function handleSvnSubModeChange(value: 'remote' | 'working_copy'): void {
  svnSubMode.value = value
  draft.pathOrUrl = ''
  draftErrors.pathOrUrl = ''
}

function validatePathByType(path: string): boolean {
  const lowerPath = path.toLowerCase()

  if (draft.type === 'local_excel') {
    return lowerPath.endsWith('.xlsx') || lowerPath.endsWith('.xls')
  }

  if (draft.type === 'local_csv') {
    return lowerPath.endsWith('.csv')
  }

  if (draft.type === 'svn' && svnSubMode.value === 'remote') {
    // 远端 URL 必须是 http(s) 且指向 .xls/.xlsx 单文件。
    if (!isHttpDirUrl(path)) {
      return false
    }
    if (path.endsWith('/')) {
      return false
    }
    return lowerPath.endsWith('.xls') || lowerPath.endsWith('.xlsx')
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
    if (isRemoteSvnSource(source) && !hasCredentialFor(source)) {
      return 'warning'
    }
    return 'success'
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
    if (isRemoteSvnSource(source) && !hasCredentialFor(source)) {
      return '待授权'
    }
    return '已就绪'
  }

  return '已就绪'
}

function getPathLabel(sourceType: SourceType): string {
  if (sourceType === 'feishu') {
    return '飞书链接'
  }

  if (sourceType === 'svn') {
    return svnSubMode.value === 'remote' ? 'SVN 文件 URL' : 'SVN 工作副本路径'
  }

  return '本地路径'
}

function isRemoteSvnSource(source: DataSource): boolean {
  const locator = (source.pathOrUrl ?? source.path ?? source.url ?? '').trim()
  return /^https?:\/\//i.test(locator)
}

function hasCredentialFor(source: DataSource): boolean {
  const host = parseSvnHost(source.pathOrUrl ?? source.url ?? '')
  if (!host) {
    return false
  }
  return svnCredentialItems.value.some((item) => item.host === host)
}

async function refreshSvnCredentialItems(): Promise<void> {
  try {
    const response = await listSvnCredentialHosts()
    svnCredentialItems.value = response.data.items
  } catch {
    // 凭据列表加载失败不阻塞主流程，状态标签会回退为"已就绪"。
  }
}

function openSvnPicker(): void {
  if (!canBrowseSvnDirectory.value) {
    ElMessage.warning('请先输入合法的 SVN 目录 URL（http/https，以 / 结尾）。')
    return
  }
  svnPickerDirUrl.value = ensureTrailingSlash(draft.pathOrUrl ?? '')
  svnPickerVisible.value = true
}

function handleSvnPicked(fileUrl: string): void {
  draft.pathOrUrl = fileUrl
  draftErrors.pathOrUrl = ''
  ElMessage.success('已选择 SVN 文件。')
}

function handleCredentialRequiredFromPicker(host: string): void {
  svnPickerVisible.value = false
  openSvnCredentialDialog(host)
}

function openSvnCredentialDialog(host: string): void {
  const normalizedHost = host.trim().toLowerCase()
  const matchedCredential = svnCredentialItems.value.find((item) => item.host === normalizedHost)
  svnCredentialDialogHost.value = host
  svnCredentialDialogDefaultTestDirUrl.value =
    matchedCredential?.test_dir_url?.trim() || getDefaultSvnCredentialTestDirUrl(normalizedHost)
  svnCredentialDialogDefaultUsername.value = matchedCredential?.username ?? ''
  svnCredentialDialogVisible.value = true
}

async function handleSvnCredentialSaved(host: string): Promise<void> {
  await refreshSvnCredentialItems()
  ElMessage.success(`已保存 ${host} 的 SVN 凭据。`)
  // 凭据保存完成后自动重新打开 picker 触发一次浏览。
  if (canBrowseSvnDirectory.value) {
    openSvnPicker()
  }
}

function handleManageSvnCredential(): void {
  const dirUrl = ensureTrailingSlash(draft.pathOrUrl ?? '')
  const host = parseSvnHost(dirUrl)
  if (!host) {
    ElMessage.warning('请先输入 SVN 目录 URL，再配置凭据。')
    return
  }
  openSvnCredentialDialog(host)
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

defineExpose({
  openCreateDialog,
})
</script>

<template>
  <div class="panel-stack">
    <div v-if="toolbarMode === 'embedded'" class="workbench-section-toolbar">
      <div class="workbench-section-toolbar__actions">
        <button
          type="button"
          class="ec-btn-outline-compact"
          @click="openCreateDialog"
        >
          <svg class="ec-btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 5v14M5 12h14" />
          </svg>
          新增数据源
        </button>
        <button
          type="button"
          class="ec-btn-text-collapse"
          aria-disabled="true"
        >
          收起
          <svg class="ec-btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="m18 15-6-6-6 6" />
          </svg>
        </button>
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
      <el-table-column label="操作" width="170" align="left">
        <template #default="{ row }">
          <div class="table-actions">
            <button type="button" class="ec-action-link" @click="openEditDialog(row)">编辑</button>
            <button type="button" class="ec-action-link-danger" @click="removeSource(row.id)">删除</button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑数据源' : '新增数据源'"
      width="520px"
      destroy-on-close
    >
      <div class="flex flex-col gap-4">
        <div>
          <label class="mb-1.5 block text-[12px] font-medium text-ink-500">数据源标识</label>
          <el-input
            v-model="draft.id"
            placeholder="例如：src_items、src_drop_table"
            maxlength="48"
            @input="draftErrors.id = ''"
          />
          <div
            v-if="draftErrors.id"
            class="mt-1 text-[12px] text-danger"
          >{{ draftErrors.id }}</div>
          <div
            v-else
            class="mt-1 text-[12px] text-ink-500"
          >唯一标识，仅允许字母、数字与下划线</div>
        </div>

        <div>
          <label class="mb-1.5 block text-[12px] font-medium text-ink-500">数据源类型</label>
          <el-select
            :model-value="draft.type"
            class="w-full"
            @update:model-value="handleSourceTypeChange"
          >
            <el-option
              v-for="option in SOURCE_TYPE_OPTIONS"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </div>

        <div v-if="isSvnSource">
          <label class="mb-1.5 block text-[12px] font-medium text-ink-500">SVN 接入方式</label>
          <el-radio-group
            :model-value="svnSubMode"
            size="small"
            @update:model-value="(value: string | number | boolean) => handleSvnSubModeChange(value as 'remote' | 'working_copy')"
          >
            <el-radio-button label="remote">远端 URL</el-radio-button>
            <el-radio-button label="working_copy">本地工作副本</el-radio-button>
          </el-radio-group>
          <div class="mt-1 text-[12px] text-ink-500">
            首次接入推荐使用远端 URL：粘贴目录链接 → 浏览选择 .xls/.xlsx 文件即可。
          </div>
        </div>

        <div>
          <label class="mb-1.5 block text-[12px] font-medium text-ink-500">{{ getPathLabel(draft.type) }}</label>
          <div class="flex items-center gap-2">
            <el-input
              v-model="draft.pathOrUrl"
              class="flex-1"
              :placeholder="
                localSource
                  ? '请选择或输入本地文件路径'
                  : isSvnSource && svnSubMode === 'remote'
                    ? '例如 https://samosvn/data/project/samo/GameDatas/datas_qa88/'
                    : isSvnSource
                      ? '请输入本地 SVN 工作副本路径，例如 D:\\svn\\datas\\quests.xls'
                      : '请输入链接或目录路径'
              "
              @input="draftErrors.pathOrUrl = ''"
            />
            <button
              v-if="localSource"
              type="button"
              class="ec-btn ec-btn-secondary shrink-0"
              :disabled="!canPickLocalFile"
              @click="chooseLocalFile"
            >
              <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M4 4h12l4 4v12H4z M14 4v6h6" />
              </svg>
              {{ isPicking ? '文件选择中…' : '选择文件' }}
            </button>
            <button
              v-if="isSvnSource && svnSubMode === 'remote'"
              type="button"
              class="ec-btn ec-btn-secondary shrink-0"
              :disabled="!canBrowseSvnDirectory"
              :title="canBrowseSvnDirectory ? '' : '先填标识，再粘贴一个 http(s) 目录 URL'"
              @click="openSvnPicker"
            >
              浏览此目录
            </button>
          </div>
          <div
            v-if="draftErrors.pathOrUrl"
            class="mt-1 text-[12px] text-danger"
          >{{ draftErrors.pathOrUrl }}</div>
          <div
            v-else-if="localSource"
            class="mt-1 text-[12px] text-ink-500"
          >
            {{
              draft.id.trim()
                ? panelCopy.localHelperReady
                : panelCopy.localHelperEmpty
            }}
          </div>
          <div
            v-else-if="isSvnSource && svnSubMode === 'remote'"
            class="mt-1 flex items-center gap-3 text-[12px] text-ink-500"
          >
            <span>支持目录 URL 浏览，选中文件后会自动写回完整文件 URL。</span>
            <button
              type="button"
              class="ec-action-link"
              :disabled="!draft.pathOrUrl?.trim()"
              @click="handleManageSvnCredential"
            >
              管理 SVN 凭据
            </button>
          </div>
        </div>

        <div v-if="needsToken">
          <label class="mb-1.5 block text-[12px] font-medium text-ink-500">访问令牌</label>
          <el-input
            v-model="draft.token"
            type="password"
            show-password
            placeholder="飞书接入时可预留 token"
          />
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end gap-2">
          <button
            type="button"
            class="ec-btn ec-btn-secondary"
            @click="dialogVisible = false"
          >
            取消
          </button>
          <button
            type="button"
            class="ec-btn ec-btn-primary"
            :disabled="!canSaveSource"
            @click="saveSource"
          >
            保存数据源
          </button>
        </div>
      </template>
    </el-dialog>

    <SvnPickerDialog
      v-model:visible="svnPickerVisible"
      :base-dir-url="svnPickerDirUrl"
      :extension-filter="['xls', 'xlsx']"
      @picked="handleSvnPicked"
      @credential-required="handleCredentialRequiredFromPicker"
    />

    <SvnCredentialDialog
      v-model:visible="svnCredentialDialogVisible"
      :host="svnCredentialDialogHost"
      :default-test-dir-url="svnCredentialDialogDefaultTestDirUrl"
      :default-username="svnCredentialDialogDefaultUsername"
      @saved="handleSvnCredentialSaved"
    />
  </div>
</template>

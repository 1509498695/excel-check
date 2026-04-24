<script setup lang="ts">
/**
 * SVN 远端目录文件选择弹窗。
 *
 * 范围约束（来自最终需求收口）：
 * - 仅显示 .xls / .xlsx 文件 + 子目录；
 * - 支持「最多再下钻 1 层」；
 * - 文件量级 ~400，不分页，前端搜索过滤；
 * - 401（已被前端兜底跳登录）以外的 4xx/5xx 都抛 SvnApiError 给上层处理。
 */

import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import {
  SvnApiError,
  type SvnEntry,
  ensureTrailingSlash,
  isHttpDirUrl,
  listSvnDirectory,
  parseSvnHost,
} from '../../api/svn'

const props = defineProps<{
  visible: boolean
  /** 用户在 DataSourcePanel 中输入的目录 URL，作为下钻深度=0 锚点。 */
  baseDirUrl: string
  /** 限制可选文件后缀，默认 ['xls','xlsx']。 */
  extensionFilter?: string[]
  /** 最多额外下钻层数，默认 1（即用户起点 + 1 层子目录）。 */
  maxDepth?: number
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  picked: [fileUrl: string]
  /** 触发凭据弹窗：上层负责弹出 SvnCredentialDialog，再 retry 浏览。 */
  'credential-required': [host: string]
  cancel: []
}>()

const state = reactive({
  currentDirUrl: '',
  baseDirUrl: '',
  searchKeyword: '',
  isLoading: false,
  errorMessage: '',
})

const entries = ref<SvnEntry[]>([])

const allowedExtensions = computed(() => {
  const list = (props.extensionFilter ?? ['xls', 'xlsx']).map((ext) => ext.toLowerCase())
  return new Set(list)
})

const maxDepth = computed(() => props.maxDepth ?? 1)

const currentDepth = computed(() => {
  if (!state.baseDirUrl || !state.currentDirUrl) {
    return 0
  }
  if (state.currentDirUrl === state.baseDirUrl) {
    return 0
  }
  // 目录 URL 都以 `/` 结尾；通过尾段路径段差计算下钻深度。
  const baseSegments = state.baseDirUrl.replace(/\/$/, '').split('/').length
  const currentSegments = state.currentDirUrl.replace(/\/$/, '').split('/').length
  return Math.max(0, currentSegments - baseSegments)
})

const isAtMaxDepth = computed(() => currentDepth.value >= maxDepth.value)

const filteredEntries = computed(() => {
  const keyword = state.searchKeyword.trim().toLowerCase()
  return entries.value.filter((entry) => {
    if (entry.kind === 'file') {
      const lowerName = entry.name.toLowerCase()
      const dotIndex = lowerName.lastIndexOf('.')
      const ext = dotIndex >= 0 ? lowerName.slice(dotIndex + 1) : ''
      if (!allowedExtensions.value.has(ext)) {
        return false
      }
    }
    if (!keyword) {
      return true
    }
    return entry.name.toLowerCase().includes(keyword)
  })
})

const breadcrumbSegments = computed<Array<{ label: string; dirUrl: string; isCurrent: boolean }>>(
  () => {
    if (!state.baseDirUrl) {
      return []
    }
    const baseLabel = displayDirLabel(state.baseDirUrl)
    const segments = [
      { label: baseLabel, dirUrl: state.baseDirUrl, isCurrent: state.currentDirUrl === state.baseDirUrl },
    ]
    if (state.currentDirUrl && state.currentDirUrl !== state.baseDirUrl) {
      segments.push({
        label: displayDirLabel(state.currentDirUrl),
        dirUrl: state.currentDirUrl,
        isCurrent: true,
      })
    }
    return segments
  },
)

function displayDirLabel(dirUrl: string): string {
  const trimmed = dirUrl.replace(/\/$/, '')
  const lastSlash = trimmed.lastIndexOf('/')
  if (lastSlash < 0) {
    return trimmed || dirUrl
  }
  return trimmed.slice(lastSlash + 1) || trimmed
}

async function loadDirectory(dirUrl: string): Promise<void> {
  if (!isHttpDirUrl(dirUrl)) {
    state.errorMessage = '请输入有效的 http(s)://… 目录 URL。'
    entries.value = []
    return
  }
  const normalized = ensureTrailingSlash(dirUrl)
  state.currentDirUrl = normalized
  state.isLoading = true
  state.errorMessage = ''
  entries.value = []

  try {
    const response = await listSvnDirectory(normalized)
    entries.value = response.data.entries
  } catch (error) {
    if (error instanceof SvnApiError) {
      if (error.category === 'auth_failed') {
        const host = parseSvnHost(normalized)
        emit('credential-required', host)
        state.errorMessage = error.message || 'SVN 鉴权失败，请重新输入凭据。'
      } else {
        state.errorMessage = error.message
      }
    } else if (error instanceof Error) {
      state.errorMessage = error.message
    } else {
      state.errorMessage = '加载 SVN 目录失败。'
    }
  } finally {
    state.isLoading = false
  }
}

watch(
  () => [props.visible, props.baseDirUrl] as const,
  ([visible, baseDirUrl]) => {
    if (!visible) {
      return
    }
    const normalizedBase = ensureTrailingSlash(baseDirUrl)
    state.baseDirUrl = normalizedBase
    state.searchKeyword = ''
    void loadDirectory(normalizedBase)
  },
)

function handleEnterDir(entry: SvnEntry): void {
  if (isAtMaxDepth.value) {
    ElMessage.info('已是最深一层，无法继续下钻。')
    return
  }
  const nextDirUrl = ensureTrailingSlash(`${state.currentDirUrl}${entry.name}`)
  void loadDirectory(nextDirUrl)
}

function handleSelectFile(entry: SvnEntry): void {
  const fullUrl = `${state.currentDirUrl}${entry.name}`
  emit('picked', fullUrl)
  emit('update:visible', false)
}

function handleBackToBase(): void {
  if (state.currentDirUrl === state.baseDirUrl) {
    return
  }
  void loadDirectory(state.baseDirUrl)
}

function handleRefresh(): void {
  void loadDirectory(state.currentDirUrl || state.baseDirUrl)
}

function handleClose(): void {
  emit('cancel')
  emit('update:visible', false)
}

function formatSize(size: number | null): string {
  if (size === null || size === undefined) {
    return '—'
  }
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`
  return `${(size / 1024 / 1024 / 1024).toFixed(2)} GB`
}

function formatDate(value: string): string {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    title="选择 SVN 文件"
    width="780px"
    destroy-on-close
    @update:model-value="(value: boolean) => emit('update:visible', value)"
  >
    <div class="space-y-4">
      <!-- 顶部面包屑 + 搜索 + 刷新 -->
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-2 text-[12px] text-ink-500">
          <span>位置：</span>
          <template v-for="(segment, index) in breadcrumbSegments" :key="segment.dirUrl">
            <button
              type="button"
              class="ec-action-link"
              :class="{ 'font-semibold text-ink-900': segment.isCurrent }"
              :disabled="segment.isCurrent"
              @click="loadDirectory(segment.dirUrl)"
            >
              {{ segment.label }}
            </button>
            <span v-if="index < breadcrumbSegments.length - 1" class="text-ink-400">/</span>
          </template>
        </div>
        <div class="flex items-center gap-2">
          <el-input
            v-model="state.searchKeyword"
            placeholder="按名称过滤"
            class="w-[220px]"
            clearable
          />
          <button
            type="button"
            class="ec-btn ec-btn-secondary"
            :disabled="state.isLoading"
            @click="handleRefresh"
          >
            {{ state.isLoading ? '加载中…' : '刷新' }}
          </button>
        </div>
      </div>

      <div v-if="currentDepth > 0" class="text-[12px] text-ink-500">
        <button type="button" class="ec-action-link" @click="handleBackToBase">回到入口目录</button>
        <span class="ml-2">最多支持下钻 {{ maxDepth }} 层。</span>
      </div>

      <!-- 错误提示 -->
      <div
        v-if="state.errorMessage"
        class="rounded border border-yellow-200 bg-yellow-50 p-3 text-[13px] text-yellow-800"
      >
        {{ state.errorMessage }}
      </div>

      <!-- 列表 -->
      <div class="max-h-[460px] overflow-y-auto rounded border border-line">
        <table class="w-full text-[13px]">
          <thead class="bg-canvas text-[12px] text-ink-500">
            <tr>
              <th class="px-3 py-2 text-left">名称</th>
              <th class="px-3 py-2 text-right w-[120px]">大小</th>
              <th class="px-3 py-2 text-left w-[160px]">最近提交</th>
              <th class="px-3 py-2 text-right w-[160px]">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="state.isLoading">
              <td colspan="4" class="px-3 py-6 text-center text-ink-500">正在加载…</td>
            </tr>
            <tr v-else-if="filteredEntries.length === 0">
              <td colspan="4" class="px-3 py-6 text-center text-ink-500">
                {{ entries.length ? '没有匹配的 .xls/.xlsx 文件或子目录。' : '当前目录为空。' }}
              </td>
            </tr>
            <tr
              v-for="entry in filteredEntries"
              :key="entry.name"
              class="border-t border-line hover:bg-canvas/60"
            >
              <td class="px-3 py-2">
                <div class="flex items-center gap-2">
                  <span
                    class="inline-flex h-5 w-5 items-center justify-center rounded text-[11px] font-semibold"
                    :class="
                      entry.kind === 'dir'
                        ? 'bg-blue-50 text-blue-600'
                        : 'bg-emerald-50 text-emerald-600'
                    "
                  >
                    {{ entry.kind === 'dir' ? 'D' : 'F' }}
                  </span>
                  <span class="font-medium text-ink-900">{{ entry.name }}</span>
                </div>
              </td>
              <td class="px-3 py-2 text-right text-ink-700">
                {{ entry.kind === 'dir' ? '—' : formatSize(entry.size) }}
              </td>
              <td class="px-3 py-2 text-ink-500">
                <div>r{{ entry.revision ?? '—' }}</div>
                <div class="text-[11px]">{{ formatDate(entry.last_modified_at) }}</div>
              </td>
              <td class="px-3 py-2 text-right">
                <button
                  v-if="entry.kind === 'dir'"
                  type="button"
                  class="ec-action-link"
                  :disabled="isAtMaxDepth"
                  :title="isAtMaxDepth ? '已是最深一层' : '进入此子目录'"
                  @click="handleEnterDir(entry)"
                >
                  {{ isAtMaxDepth ? '已是最深一层' : '进入' }}
                </button>
                <button
                  v-else
                  type="button"
                  class="ec-action-link"
                  @click="handleSelectFile(entry)"
                >
                  选中
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <template #footer>
      <div class="flex justify-end gap-2">
        <button type="button" class="ec-btn ec-btn-secondary" @click="handleClose">
          关闭
        </button>
      </div>
    </template>
  </el-dialog>
</template>

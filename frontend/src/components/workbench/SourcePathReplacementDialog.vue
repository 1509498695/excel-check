<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { listSvnDirectory } from '../../api/svn'
import { validateLocalDirectoryPath } from '../../api/workbench'
import type { SourcePathReplacementStoreLike } from '../../types/panelStores'
import type { SourcePathReplacementGroup } from '../../utils/sourcePathReplacement'

const props = withDefaults(
  defineProps<{
    store: SourcePathReplacementStoreLike
    variant?: 'workbench' | 'fixed-rules'
  }>(),
  {
    variant: 'workbench',
  },
)

type GroupFormState = {
  selectedDirectory: string
  newDirectory: string
  isSavingPreset: boolean
  isApplying: boolean
}

const dialogVisible = ref(false)
const activeGroup = ref<SourcePathReplacementGroup>('local')
const formState = reactive<Record<SourcePathReplacementGroup, GroupFormState>>({
  local: {
    selectedDirectory: '',
    newDirectory: '',
    isSavingPreset: false,
    isApplying: false,
  },
  svn: {
    selectedDirectory: '',
    newDirectory: '',
    isSavingPreset: false,
    isApplying: false,
  },
})

const copy = computed(() => ({
  title: props.variant === 'fixed-rules' ? '项目校验数据源路径管理' : '个人校验数据源路径管理',
  subtitle:
    '按数据源类型分别管理本地目录与 SVN 目录。只替换文件名前的目录路径，保留原文件名不变，并在完成后立即刷新当前已接入数据源的元数据与变量预览。',
}))

const groupTabs = computed(() => [
  {
    key: 'local' as const,
    label: '本地路径',
    description: '管理本地 Excel / CSV 和 SVN 工作副本路径。',
  },
  {
    key: 'svn' as const,
    label: 'SVN 路径',
    description: '管理远端 SVN 目录 URL，并用于替换远端 HTTP 链接型数据源。',
  },
])

const groupCopy = computed<
  Record<
    SourcePathReplacementGroup,
    {
      chooseTitle: string
      choosePlaceholder: string
      addTitle: string
      addPlaceholder: string
      saveButtonLabel: string
      emptyText: string
      applyButtonLabel: string
      noCandidateText: string
      successText: (updatedCount: number, failedCount: number) => string
      failureTitle: string
    }
  >
>(() => ({
  local: {
    chooseTitle: '选择本地目录',
    choosePlaceholder: '从已保存的本地目录中选择',
    addTitle: '新增并保存本地目录',
    addPlaceholder: '输入本地绝对目录路径，例如 D:\\project_samo\\GameDatas\\datas_qa89',
    saveButtonLabel: '保存本地目录',
    emptyText: '还没有保存本地目录。先在上方输入一个目录并保存，我们就可以在不同版本的本地目录之间快速切换了。',
    applyButtonLabel: '一键替换本地路径并刷新',
    noCandidateText: '当前没有可替换的本地路径型数据源。',
    successText: (updatedCount, failedCount) =>
      failedCount > 0
        ? `已替换 ${updatedCount} 个本地数据源，其中 ${failedCount} 个刷新失败，请检查数据源状态提示。`
        : `已替换并刷新 ${updatedCount} 个本地数据源，请重新执行校验。`,
    failureTitle: '本地路径替换失败',
  },
  svn: {
    chooseTitle: '选择 SVN 目录',
    choosePlaceholder: '从已保存的 SVN 目录 URL 中选择',
    addTitle: '新增并保存 SVN 目录',
    addPlaceholder: '输入 SVN 目录 URL，例如 https://samosvn/data/project/samo/GameDatas/datas_qa89/',
    saveButtonLabel: '保存 SVN 目录',
    emptyText: '还没有保存 SVN 目录。先在上方输入一个目录 URL 并保存，我们就可以在不同版本的 SVN 目录之间快速切换了。',
    applyButtonLabel: '一键替换 SVN 路径并刷新',
    noCandidateText: '当前没有可替换的远端 SVN 数据源。',
    successText: (updatedCount, failedCount) =>
      failedCount > 0
        ? `已替换 ${updatedCount} 个 SVN 数据源，其中 ${failedCount} 个刷新失败，请检查数据源状态提示。`
        : `已替换并刷新 ${updatedCount} 个 SVN 数据源，请重新执行校验。`,
    failureTitle: 'SVN 路径替换失败',
  },
}))

function getGroupState(group: SourcePathReplacementGroup): GroupFormState {
  return formState[group]
}

function getPresetList(group: SourcePathReplacementGroup): string[] {
  return group === 'svn'
    ? props.store.svnPathReplacementPresets
    : props.store.localPathReplacementPresets
}

function getSelectedPreset(group: SourcePathReplacementGroup): string | null {
  return group === 'svn'
    ? props.store.selectedSvnPathReplacementPreset
    : props.store.selectedLocalPathReplacementPreset
}

function syncSelectedDirectory(group: SourcePathReplacementGroup): void {
  getGroupState(group).selectedDirectory = getSelectedPreset(group) ?? ''
}

function openDialog(): void {
  activeGroup.value = 'local'
  syncSelectedDirectory('local')
  syncSelectedDirectory('svn')
  formState.local.newDirectory = ''
  formState.svn.newDirectory = ''
  dialogVisible.value = true
}

async function normalizeDirectoryPath(
  group: SourcePathReplacementGroup,
  rawDirectoryPath: string,
): Promise<string> {
  if (group === 'svn') {
    const normalizedDirUrl = rawDirectoryPath.trim()
    if (!normalizedDirUrl) {
      throw new Error('SVN 目录 URL 不能为空。')
    }
    const response = await listSvnDirectory(normalizedDirUrl)
    return response.data.dir_url
  }

  const response = await validateLocalDirectoryPath(rawDirectoryPath)
  return response.data.directory_path
}

async function handleSavePreset(group: SourcePathReplacementGroup): Promise<void> {
  const state = getGroupState(group)
  const candidatePath = state.newDirectory.trim()
  if (!candidatePath) {
    ElMessage.warning(group === 'svn' ? '请先输入需要保存的 SVN 目录 URL。' : '请先输入需要保存的本地目录。')
    return
  }

  state.isSavingPreset = true
  try {
    const normalizedPath = await normalizeDirectoryPath(group, candidatePath)
    props.store.addPathReplacementPreset(group, normalizedPath)
    props.store.setSelectedPathReplacementPreset(group, normalizedPath)
    await props.store.saveConfigNow()
    state.selectedDirectory = normalizedPath
    state.newDirectory = ''
    ElMessage.success(group === 'svn' ? 'SVN 目录已保存。' : '本地目录已保存。')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存目录失败。')
  } finally {
    state.isSavingPreset = false
  }
}

async function handleApplyReplacement(group: SourcePathReplacementGroup): Promise<void> {
  const state = getGroupState(group)
  const candidatePath = state.selectedDirectory.trim()
  if (!candidatePath) {
    ElMessage.warning(group === 'svn' ? '请先选择一个 SVN 目录 URL。' : '请先选择一个本地目录。')
    return
  }

  state.isApplying = true
  try {
    const normalizedPath = await normalizeDirectoryPath(group, candidatePath)
    state.selectedDirectory = normalizedPath
    props.store.setSelectedPathReplacementPreset(group, normalizedPath)
    const result = await props.store.replaceSourceBasePath(group, normalizedPath)

    if (!result.updatedCount) {
      ElMessage.warning(groupCopy.value[group].noCandidateText)
      return
    }

    ElMessage.success(groupCopy.value[group].successText(result.updatedCount, result.failedCount))
    dialogVisible.value = false
  } catch (error) {
    const message = error instanceof Error ? error.message : '数据源路径管理失败。'
    await ElMessageBox.alert(message, groupCopy.value[group].failureTitle, {
      type: 'error',
      confirmButtonText: '知道了',
    })
  } finally {
    state.isApplying = false
  }
}

defineExpose({
  openDialog,
})
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    width="780px"
    :title="copy.title"
    destroy-on-close
  >
    <div class="space-y-5">
      <p class="text-[13px] leading-6 text-ink-500">
        {{ copy.subtitle }}
      </p>

      <div class="rounded-card border border-line bg-canvas p-2">
        <div class="grid grid-cols-2 gap-2">
          <button
            v-for="tab in groupTabs"
            :key="tab.key"
            type="button"
            class="rounded-field border px-4 py-3 text-left transition"
            :class="
              activeGroup === tab.key
                ? 'border-blue-200 bg-blue-50 text-accent shadow-sm'
                : 'border-line bg-white text-ink-700 hover:border-blue-200 hover:bg-blue-50/40'
            "
            @click="activeGroup = tab.key"
          >
            <div class="text-[13px] font-semibold">
              {{ tab.label }}
            </div>
            <div class="mt-1 text-[12px] text-ink-500">
              {{ tab.description }}
            </div>
          </button>
        </div>
      </div>

      <section class="space-y-3 rounded-card border border-line bg-canvas px-5 py-4">
        <div class="text-[13px] font-semibold text-ink-900">
          {{ groupCopy[activeGroup].chooseTitle }}
        </div>
        <el-select
          v-model="formState[activeGroup].selectedDirectory"
          class="w-full"
          :placeholder="groupCopy[activeGroup].choosePlaceholder"
          clearable
          filterable
        >
          <el-option
            v-for="preset in getPresetList(activeGroup)"
            :key="preset"
            :label="preset"
            :value="preset"
          />
        </el-select>
      </section>

      <section class="space-y-3 rounded-card border border-line bg-canvas px-5 py-4">
        <div class="text-[13px] font-semibold text-ink-900">
          {{ groupCopy[activeGroup].addTitle }}
        </div>
        <div class="flex flex-col gap-3 md:flex-row md:items-center">
          <el-input
            v-model="formState[activeGroup].newDirectory"
            :placeholder="groupCopy[activeGroup].addPlaceholder"
            clearable
          />
          <button
            type="button"
            class="ec-btn-outline whitespace-nowrap"
            :disabled="formState[activeGroup].isSavingPreset"
            @click="handleSavePreset(activeGroup)"
          >
            {{ groupCopy[activeGroup].saveButtonLabel }}
          </button>
        </div>
      </section>

      <section class="space-y-3 rounded-card border border-line bg-canvas px-5 py-4">
        <div class="flex items-center justify-between gap-3">
          <div class="text-[13px] font-semibold text-ink-900">已保存目录列表</div>
          <span class="text-[12px] text-ink-500">
            共 {{ getPresetList(activeGroup).length }} 个
          </span>
        </div>
        <div
          v-if="getPresetList(activeGroup).length"
          class="max-h-52 space-y-2 overflow-y-auto pr-1"
        >
          <button
            v-for="preset in getPresetList(activeGroup)"
            :key="preset"
            type="button"
            class="flex w-full items-start justify-between gap-3 rounded-field border border-line bg-white px-4 py-3 text-left transition hover:border-blue-300 hover:bg-blue-50/40"
            @click="formState[activeGroup].selectedDirectory = preset"
          >
            <span class="break-all text-[13px] text-ink-900">{{ preset }}</span>
            <span
              v-if="formState[activeGroup].selectedDirectory === preset"
              class="shrink-0 text-[12px] font-medium text-accent"
            >
              当前选择
            </span>
          </button>
        </div>
        <div
          v-else
          class="rounded-field border border-dashed border-line bg-white px-4 py-5 text-[13px] text-ink-500"
        >
          {{ groupCopy[activeGroup].emptyText }}
        </div>
      </section>
    </div>

    <template #footer>
      <div class="flex justify-end gap-3">
        <button
          type="button"
          class="ec-btn-ghost"
          :disabled="formState.local.isApplying || formState.local.isSavingPreset || formState.svn.isApplying || formState.svn.isSavingPreset"
          @click="dialogVisible = false"
        >
          取消
        </button>
        <button
          type="button"
          class="ec-btn-primary"
          :disabled="formState[activeGroup].isApplying"
          @click="handleApplyReplacement(activeGroup)"
        >
          {{ groupCopy[activeGroup].applyButtonLabel }}
        </button>
      </div>
    </template>
  </el-dialog>
</template>

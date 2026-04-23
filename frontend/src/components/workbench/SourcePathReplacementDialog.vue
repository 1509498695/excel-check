<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { validateLocalDirectoryPath } from '../../api/workbench'
import type { SourcePathReplacementStoreLike } from '../../types/panelStores'

const props = withDefaults(
  defineProps<{
    store: SourcePathReplacementStoreLike
    variant?: 'workbench' | 'fixed-rules'
  }>(),
  {
    variant: 'workbench',
  },
)

const dialogVisible = ref(false)
const formState = reactive({
  selectedDirectory: '',
  newDirectory: '',
  isSavingPreset: false,
  isApplying: false,
})

const copy = computed(() => ({
  title: props.variant === 'fixed-rules' ? '项目校验路径替换' : '个人校验路径替换',
  subtitle:
    '只替换文件名前的目录路径，保留原文件名不变，并在完成后立即刷新当前已接入数据源的元数据。',
}))

function syncSelectedDirectory(): void {
  formState.selectedDirectory = props.store.selectedPathReplacementPreset ?? ''
}

function openDialog(): void {
  syncSelectedDirectory()
  formState.newDirectory = ''
  dialogVisible.value = true
}

async function normalizeDirectoryPath(rawDirectoryPath: string): Promise<string> {
  const response = await validateLocalDirectoryPath(rawDirectoryPath)
  return response.data.directory_path
}

async function handleSavePreset(): Promise<void> {
  const candidatePath = formState.newDirectory.trim()
  if (!candidatePath) {
    ElMessage.warning('请先输入需要保存的替换目录。')
    return
  }

  formState.isSavingPreset = true
  try {
    const normalizedPath = await normalizeDirectoryPath(candidatePath)
    props.store.addPathReplacementPreset(normalizedPath)
    props.store.setSelectedPathReplacementPreset(normalizedPath)
    await props.store.saveConfigNow()
    formState.selectedDirectory = normalizedPath
    formState.newDirectory = ''
    ElMessage.success('替换目录已保存。')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存替换目录失败。')
  } finally {
    formState.isSavingPreset = false
  }
}

async function handleApplyReplacement(): Promise<void> {
  const candidatePath = formState.selectedDirectory.trim()
  if (!candidatePath) {
    ElMessage.warning('请先选择一个替换目录。')
    return
  }

  formState.isApplying = true
  try {
    const normalizedPath = await normalizeDirectoryPath(candidatePath)
    formState.selectedDirectory = normalizedPath
    props.store.setSelectedPathReplacementPreset(normalizedPath)
    const result = await props.store.replaceSourceBasePath(normalizedPath)

    if (!result.updatedCount) {
      ElMessage.warning('当前没有可替换的本地文件型数据源。')
      return
    }

    if (result.failedCount > 0) {
      ElMessage.warning(
        `已替换 ${result.updatedCount} 个数据源，其中 ${result.failedCount} 个刷新失败，请检查数据源状态提示。`,
      )
    } else {
      ElMessage.success(`已替换并刷新 ${result.updatedCount} 个数据源。`)
    }
    dialogVisible.value = false
  } catch (error) {
    const message = error instanceof Error ? error.message : '路径替换失败。'
    await ElMessageBox.alert(message, '路径替换失败', {
      type: 'error',
      confirmButtonText: '知道了',
    })
  } finally {
    formState.isApplying = false
  }
}

defineExpose({
  openDialog,
})
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    width="720px"
    :title="copy.title"
    destroy-on-close
  >
    <div class="space-y-5">
      <p class="text-[13px] leading-6 text-ink-500">
        {{ copy.subtitle }}
      </p>

      <section class="space-y-3 rounded-card border border-line bg-canvas px-5 py-4">
        <div class="text-[13px] font-semibold text-ink-900">选择替换目录</div>
        <el-select
          v-model="formState.selectedDirectory"
          class="w-full"
          placeholder="从已保存的替换目录中选择"
          clearable
          filterable
        >
          <el-option
            v-for="preset in props.store.pathReplacementPresets"
            :key="preset"
            :label="preset"
            :value="preset"
          />
        </el-select>
      </section>

      <section class="space-y-3 rounded-card border border-line bg-canvas px-5 py-4">
        <div class="text-[13px] font-semibold text-ink-900">新增并保存目录</div>
        <div class="flex flex-col gap-3 md:flex-row md:items-center">
          <el-input
            v-model="formState.newDirectory"
            placeholder="输入本地绝对目录路径，例如 D:\\project_samo\\GameDatas\\datas_qa89"
            clearable
          />
          <button
            type="button"
            class="ec-btn-outline whitespace-nowrap"
            :disabled="formState.isSavingPreset"
            @click="handleSavePreset"
          >
            保存目录
          </button>
        </div>
      </section>

      <section class="space-y-3 rounded-card border border-line bg-canvas px-5 py-4">
        <div class="flex items-center justify-between gap-3">
          <div class="text-[13px] font-semibold text-ink-900">已保存目录列表</div>
          <span class="text-[12px] text-ink-500">
            共 {{ props.store.pathReplacementPresets.length }} 个
          </span>
        </div>
        <div
          v-if="props.store.pathReplacementPresets.length"
          class="max-h-52 space-y-2 overflow-y-auto pr-1"
        >
          <button
            v-for="preset in props.store.pathReplacementPresets"
            :key="preset"
            type="button"
            class="flex w-full items-start justify-between gap-3 rounded-field border border-line bg-white px-4 py-3 text-left transition hover:border-blue-300 hover:bg-blue-50/40"
            @click="formState.selectedDirectory = preset"
          >
            <span class="break-all text-[13px] text-ink-900">{{ preset }}</span>
            <span
              v-if="formState.selectedDirectory === preset"
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
          还没有保存替换目录。先在上方输入一个目录并保存，我们就可以在不同版本目录之间快速切换了。
        </div>
      </section>
    </div>

    <template #footer>
      <div class="flex justify-end gap-3">
        <button
          type="button"
          class="ec-btn-ghost"
          :disabled="formState.isApplying || formState.isSavingPreset"
          @click="dialogVisible = false"
        >
          取消
        </button>
        <button
          type="button"
          class="ec-btn-primary"
          :disabled="formState.isApplying"
          @click="handleApplyReplacement"
        >
          一键替换并刷新
        </button>
      </div>
    </template>
  </el-dialog>
</template>

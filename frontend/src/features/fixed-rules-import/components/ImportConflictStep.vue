<script setup lang="ts">
import type { ImportConflict, ImportConflictResolutions } from '../types'

defineProps<{
  conflicts: ImportConflict[]
  resolutions: Required<ImportConflictResolutions>
  previewStale: boolean
  isPreviewing: boolean
}>()

const emit = defineEmits<{
  (event: 'changed'): void
  (event: 'refresh-preview'): void
}>()

function getResolutionValue(
  resolutions: Required<ImportConflictResolutions>,
  conflict: ImportConflict,
): string {
  if (conflict.kind === 'variable_tag') {
    return resolutions.variable_tags[conflict.item_id] ?? ''
  }
  if (conflict.kind === 'rule_name') {
    return resolutions.rule_names[conflict.item_id] ?? ''
  }
  if (conflict.kind === 'group_name') {
    return resolutions.group_names[conflict.item_id] ?? ''
  }
  return ''
}

function setResolutionValue(
  resolutions: Required<ImportConflictResolutions>,
  conflict: ImportConflict,
  value: string,
): void {
  if (conflict.kind === 'variable_tag') {
    resolutions.variable_tags[conflict.item_id] = value
  } else if (conflict.kind === 'rule_name') {
    resolutions.rule_names[conflict.item_id] = value
  } else if (conflict.kind === 'group_name') {
    resolutions.group_names[conflict.item_id] = value
  }
  emit('changed')
}

function getResolutionPlaceholder(conflict: ImportConflict): string {
  if (conflict.kind === 'variable_tag') return '填写新的变量 tag'
  if (conflict.kind === 'rule_name') return '填写新的规则名'
  if (conflict.kind === 'group_name') return '填写新的规则组名'
  return ''
}

function canResolve(conflict: ImportConflict): boolean {
  return ['variable_tag', 'rule_name', 'group_name'].includes(conflict.kind)
}
</script>

<template>
  <div class="space-y-3">
    <div v-if="!conflicts.length" class="rounded-field border border-line bg-card p-5 text-[13px] text-ink-500">
      暂无需要人工处理的冲突。
    </div>
    <div
      v-for="conflict in conflicts"
      :key="`${conflict.kind}-${conflict.item_id}-${conflict.message}`"
      class="rounded-field border border-line bg-card p-4"
    >
      <div class="flex items-center justify-between gap-3">
        <div class="text-[13px] font-medium text-ink-900">{{ conflict.item_id }}</div>
        <el-tag
          size="small"
          :type="conflict.level === 'error' ? 'danger' : conflict.level === 'warning' ? 'warning' : 'info'"
        >
          {{ conflict.level }}
        </el-tag>
      </div>
      <div class="mt-2 text-[13px] text-ink-600">{{ conflict.message }}</div>
      <div v-if="conflict.candidates.length" class="mt-2 text-[12px] text-ink-500">
        候选：{{ conflict.candidates.join('、') }}
      </div>
      <el-input
        v-if="canResolve(conflict)"
        class="mt-3"
        :model-value="getResolutionValue(resolutions, conflict)"
        :placeholder="getResolutionPlaceholder(conflict)"
        clearable
        @input="setResolutionValue(resolutions, conflict, String($event))"
      />
    </div>

    <div class="flex justify-end">
      <el-button
        type="primary"
        :loading="isPreviewing"
        :disabled="!previewStale"
        @click="emit('refresh-preview')"
      >
        重新生成预览
      </el-button>
    </div>
  </div>
</template>

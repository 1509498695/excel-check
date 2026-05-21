<script setup lang="ts">
import type { SourceMapping, SourceMappingAction, SourceMappingDraft } from '../types'

const props = defineProps<{
  mappings: SourceMapping[]
  drafts: SourceMappingDraft[]
}>()

const emit = defineEmits<{
  (event: 'update:mappings', value: SourceMapping[]): void
}>()

function updateMapping(index: number, patch: Partial<SourceMapping>): void {
  const nextMappings = props.mappings.map((mapping, currentIndex) =>
    currentIndex === index
      ? {
          ...mapping,
          ...patch,
          next_source: patch.next_source ?? mapping.next_source,
        }
      : mapping,
  )
  emit('update:mappings', nextMappings)
}

function updatePath(index: number, value: string): void {
  const mapping = props.mappings[index]
  if (!mapping?.next_source) return
  const source = { ...mapping.next_source }
  if (source.type === 'svn') {
    source.url = value
    source.path = undefined
  } else {
    source.path = value
    source.url = undefined
  }
  source.pathOrUrl = value
  updateMapping(index, { next_source: source })
}
</script>

<template>
  <div class="space-y-3">
    <div
      v-for="(mapping, index) in mappings"
      :key="mapping.personal_source_id"
      class="rounded-field border border-line bg-card p-4"
    >
      <div class="mb-3 flex items-start justify-between gap-3">
        <div class="min-w-0">
          <div class="text-[13px] font-medium text-ink-900">
            {{ drafts[index]?.personal_source.id ?? mapping.personal_source_id }}
          </div>
          <div class="mt-1 truncate text-[12px] text-ink-500">
            {{ drafts[index]?.personal_source.pathOrUrl || drafts[index]?.personal_source.path || drafts[index]?.personal_source.url }}
          </div>
          <div class="mt-1 text-[12px] text-ink-500">{{ drafts[index]?.reason }}</div>
        </div>
        <el-select
          :model-value="mapping.action"
          class="w-[160px] shrink-0"
          @change="updateMapping(index, { action: $event as SourceMappingAction })"
        >
          <el-option label="新增" value="new" />
          <el-option label="复用" value="reuse" />
          <el-option label="修改路径/URL" value="replace" />
          <el-option label="跳过" value="skip" />
        </el-select>
      </div>

      <div
        v-if="drafts[index]?.requires_confirmation"
        class="mb-3 rounded-field border border-warning/40 bg-warning-soft/50 p-3 text-[12px] text-ink-700"
      >
        <div class="font-medium text-ink-900">高风险数据源映射</div>
        <div class="mt-1">
          项目校验已存在同 ID 但路径或 URL 不同的数据源。请明确选择复用、修改路径后导入、新增为独立数据源或跳过，并勾选确认。
        </div>
      </div>

      <el-select
        v-if="mapping.action === 'reuse'"
        :model-value="mapping.project_source_id"
        class="w-full"
        filterable
        placeholder="选择项目已有数据源"
        @change="updateMapping(index, { project_source_id: String($event) })"
      >
        <el-option
          v-for="candidate in drafts[index]?.candidates ?? []"
          :key="candidate.id"
          :label="`${candidate.id} · ${candidate.pathOrUrl || candidate.path || candidate.url || ''}`"
          :value="candidate.id"
        />
      </el-select>

      <el-input
        v-else-if="mapping.action === 'new' || mapping.action === 'replace'"
        :model-value="mapping.next_source?.pathOrUrl || mapping.next_source?.path || mapping.next_source?.url || ''"
        placeholder="导入时使用的数据源路径或 URL"
        @input="updatePath(index, String($event))"
      />

      <el-checkbox
        v-if="drafts[index]?.requires_confirmation"
        class="mt-3"
        :model-value="mapping.confirmed"
        @change="updateMapping(index, { confirmed: Boolean($event) })"
      >
        我已确认该数据源映射方式
      </el-checkbox>
    </div>
  </div>
</template>

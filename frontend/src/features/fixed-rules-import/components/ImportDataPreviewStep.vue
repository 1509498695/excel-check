<script setup lang="ts">
import type { WorkbenchImportPreview } from '../types'

defineProps<{
  preview: WorkbenchImportPreview | null
}>()

function getPreviewSamples(payload: Record<string, unknown> | null | undefined): string[] {
  if (!payload) return []
  const rows = payload.preview_rows
  if (Array.isArray(rows)) {
    return rows.slice(0, 5).map((row) => {
      const item = row as Record<string, unknown>
      return `第 ${item.row_index ?? '-'} 行：${String(item.value ?? '')}`
    })
  }
  const mapping = payload.mapping
  if (mapping && typeof mapping === 'object' && !Array.isArray(mapping)) {
    return Object.entries(mapping as Record<string, unknown>)
      .slice(0, 5)
      .map(([key, value]) => `${key}：${JSON.stringify(value)}`)
  }
  return []
}

function importantRuleResults(preview: WorkbenchImportPreview) {
  return preview.rule_results.filter((item) => item.status === 'skipped' || item.status === 'error')
}
</script>

<template>
  <div class="space-y-4">
    <div v-if="!preview" class="rounded-field border border-dashed border-line bg-subtle p-6 text-center text-[13px] text-ink-500">
      点击“生成预览”后查看数据源、变量与前 20 行预览校验结果。
    </div>
    <template v-else>
      <div
        v-if="preview.blocking_errors.length"
        class="rounded-field border border-danger/30 bg-danger-soft/40 p-4 text-[13px] text-ink-700"
      >
        <div class="font-medium text-ink-900">存在阻断问题</div>
        <ul class="mt-2 list-disc space-y-1 pl-5">
          <li v-for="error in preview.blocking_errors" :key="error">{{ error }}</li>
        </ul>
      </div>

      <el-table :data="preview.variable_previews" size="small" border>
        <el-table-column prop="tag" label="变量" min-width="220" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="message" label="预览结果" min-width="260" />
      </el-table>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <div class="mb-2 text-[13px] font-medium text-ink-900">数据源检查</div>
          <el-table :data="preview.source_results" size="small" border>
            <el-table-column prop="item_id" label="数据源" min-width="150" />
            <el-table-column prop="status" label="状态" width="90" />
            <el-table-column prop="message" label="说明" min-width="180" />
          </el-table>
        </div>
        <div>
          <div class="mb-2 text-[13px] font-medium text-ink-900">变量检查</div>
          <el-table :data="preview.variable_results" size="small" border>
            <el-table-column prop="item_id" label="变量" min-width="150" />
            <el-table-column prop="status" label="状态" width="90" />
            <el-table-column prop="message" label="说明" min-width="180" />
          </el-table>
        </div>
      </div>

      <div v-if="importantRuleResults(preview).length">
        <div class="mb-2 text-[13px] font-medium text-ink-900">受影响规则</div>
        <el-table :data="importantRuleResults(preview)" size="small" border>
          <el-table-column prop="item_id" label="规则" min-width="160" />
          <el-table-column prop="status" label="状态" width="90" />
          <el-table-column prop="message" label="原因" min-width="260" />
        </el-table>
      </div>

      <div>
        <div class="mb-2 text-[13px] font-medium text-ink-900">预览样例</div>
        <div class="space-y-2">
          <div
            v-for="item in preview.variable_previews"
            :key="item.tag"
            class="rounded-field border border-line bg-card p-3"
          >
            <div class="text-[12px] font-medium text-ink-900">{{ item.tag }}</div>
            <div
              v-if="getPreviewSamples(item.preview ?? null).length"
              class="mt-2 space-y-1 text-[12px] text-ink-600"
            >
              <div v-for="sample in getPreviewSamples(item.preview ?? null)" :key="sample">
                {{ sample }}
              </div>
            </div>
            <div v-else class="mt-2 text-[12px] text-ink-500">暂无可展示样例</div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

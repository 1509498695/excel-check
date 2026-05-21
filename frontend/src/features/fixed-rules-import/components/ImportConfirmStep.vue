<script setup lang="ts">
import type { DuplicateRuleAction, ImportItemResult, WorkbenchImportPreview } from '../types'

defineProps<{
  preview: WorkbenchImportPreview | null
  duplicateRuleActions?: Record<string, DuplicateRuleAction>
}>()

const emit = defineEmits<{
  (event: 'update-duplicate-rule-action', ruleId: string, action: DuplicateRuleAction): void
}>()

function skippedRules(preview: WorkbenchImportPreview) {
  return preview.rule_results.filter((item) => item.status === 'skipped' || item.status === 'error')
}

function importedRuleCount(preview: WorkbenchImportPreview) {
  return preview.rule_results.filter((item) => item.status === 'new' || item.status === 'renamed').length
}

function reusedRuleCount(preview: WorkbenchImportPreview) {
  return preview.rule_results.filter((item) => item.status === 'reuse').length
}

function blockedRuleCount(preview: WorkbenchImportPreview) {
  return skippedRules(preview).length
}

function isDuplicateRule(row: ImportItemResult): boolean {
  return row.details?.duplicate_rule === true
}

function duplicateRuleAction(row: ImportItemResult): DuplicateRuleAction {
  const action = row.details?.duplicate_action
  return action === 'skip' ? 'skip' : 'rename'
}

function duplicateRuleLabel(row: ImportItemResult): string {
  if (!isDuplicateRule(row)) {
    return '否'
  }
  return row.status === 'skipped' ? '已跳过' : '已重命名'
}
</script>

<template>
  <div class="space-y-4">
    <div v-if="!preview" class="rounded-field border border-dashed border-line bg-subtle p-6 text-center text-[13px] text-ink-500">
      生成预览后可确认导入。
    </div>
    <template v-else>
      <div
        v-if="preview.blocking_errors.length"
        class="rounded-field border border-danger/30 bg-danger-soft/40 p-3 text-[13px] text-ink-700"
      >
        <div class="mb-1 font-medium text-danger">存在阻断问题，暂不能导入</div>
        <ul class="list-disc space-y-1 pl-5">
          <li v-for="error in preview.blocking_errors" :key="error">{{ error }}</li>
        </ul>
      </div>

      <div class="grid grid-cols-3 gap-3">
        <div class="rounded-field border border-line bg-card p-4">
          <div class="text-[12px] text-ink-500">成功导入规则</div>
          <div class="mt-1 text-[18px] font-semibold text-ink-900">
            {{ importedRuleCount(preview) }}
          </div>
          <div class="mt-1 text-[12px] text-ink-500">新增 {{ preview.summary.rules_new }}，改名 {{ preview.summary.rules_renamed }}</div>
        </div>
        <div class="rounded-field border border-line bg-card p-4">
          <div class="text-[12px] text-ink-500">复用规则</div>
          <div class="mt-1 text-[18px] font-semibold text-ink-900">
            {{ reusedRuleCount(preview) }}
          </div>
          <div class="mt-1 text-[12px] text-ink-500">复用项目已有定义</div>
        </div>
        <div class="rounded-field border border-line bg-card p-4">
          <div class="text-[12px] text-ink-500">阻断规则</div>
          <div class="mt-1 text-[18px] font-semibold text-ink-900">
            {{ blockedRuleCount(preview) }}
          </div>
          <div class="mt-1 text-[12px] text-ink-500">全局阻断 {{ preview.summary.blocking_errors }}</div>
        </div>
      </div>

      <el-table :data="preview.rule_results" size="small" border>
        <el-table-column label="个人规则" min-width="220">
          <template #default="{ row }">
            <div class="whitespace-pre-wrap break-all leading-5">
              {{ row.item_id }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="最终规则名" min-width="260">
          <template #default="{ row }">
            <div class="whitespace-pre-wrap break-all leading-5">
              {{ row.details?.rule_name ?? '—' }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="重复规则" width="110">
          <template #default="{ row }">
            <el-tag v-if="isDuplicateRule(row)" type="warning" size="small">
              {{ duplicateRuleLabel(row) }}
            </el-tag>
            <span v-else class="text-ink-400">否</span>
          </template>
        </el-table-column>
        <el-table-column label="处理方式" width="180">
          <template #default="{ row }">
            <el-radio-group
              v-if="isDuplicateRule(row)"
              :model-value="duplicateRuleActions?.[row.item_id] ?? duplicateRuleAction(row)"
              size="small"
              @change="emit('update-duplicate-rule-action', row.item_id, $event as DuplicateRuleAction)"
            >
              <el-radio-button label="rename">重命名</el-radio-button>
              <el-radio-button label="skip">跳过</el-radio-button>
            </el-radio-group>
            <span v-else class="text-ink-400">—</span>
          </template>
        </el-table-column>
        <el-table-column label="导入状态" width="120">
          <template #default="{ row }">
            <span class="whitespace-pre-wrap break-all">
              {{ row.status }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="说明" min-width="280">
          <template #default="{ row }">
            <div class="whitespace-pre-wrap break-all leading-5">
              {{ row.message }}
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="skippedRules(preview).length">
        <div class="mb-2 text-[13px] font-medium text-ink-900">跳过规则</div>
        <el-table :data="skippedRules(preview)" size="small" border>
          <el-table-column label="规则" min-width="260">
            <template #default="{ row }">
              <div class="whitespace-pre-wrap break-all leading-5">
                {{ row.item_id }}
              </div>
            </template>
          </el-table-column>
          <el-table-column label="原因" min-width="360">
            <template #default="{ row }">
              <div class="whitespace-pre-wrap break-all leading-5">
                {{ row.message }}
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </template>
  </div>
</template>

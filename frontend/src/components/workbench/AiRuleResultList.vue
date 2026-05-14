<script setup lang="ts">
import { InfoFilled } from '@element-plus/icons-vue'

import EmptyState from '../shell/EmptyState.vue'
import AiRuleResultItem from './AiRuleResultItem.vue'
import type { AiMissingItem } from '../../types/ai'
import type { FixedRuleGroup } from '../../types/fixedRules'
import type {
  AiResultSummaryViewModel,
  AiRuleResultViewModel,
} from '../../utils/aiRuleViewModel'

defineProps<{
  items: AiRuleResultViewModel[]
  summary: AiResultSummaryViewModel
  loading: boolean
  error: string
  canApply: boolean
  canAutoCompleteApply: boolean
  autoCompleteApplyLoading: boolean
  showApplyGroupSelect: boolean
  selectedApplyGroupId: string
  applyGroupOptions: FixedRuleGroup[]
}>()

const emit = defineEmits<{
  (e: 'update:selected-apply-group-id', value: string): void
  (e: 'view-config', item: AiRuleResultViewModel): void
  (e: 'apply-rule', item: AiRuleResultViewModel): void
  (e: 'resolve-missing', missing: AiMissingItem | undefined): void
  (e: 'auto-complete-apply'): void
  (e: 'rewrite-rule'): void
}>()

function updateSelectedApplyGroupId(value: string | number | boolean | undefined): void {
  emit('update:selected-apply-group-id', value === undefined ? '' : String(value))
}
</script>

<template>
  <section class="smart-rule-card ai-rule-result-list">
    <div class="smart-rule-card__header">
      <h3>AI 校验结果</h3>
    </div>

    <div v-if="loading" class="ai-rule-result-state">AI 正在分析规则描述，请稍候。</div>
    <div v-else-if="error" class="ai-rule-result-state is-error">{{ error }}</div>
    <EmptyState
      v-else-if="!items.length"
      variant="table"
      icon-tone="rule"
      title="暂无 AI 校验结果"
      description="输入规则描述并点击 AI 校验后，这里会展示可添加、需补充和不可添加的规则"
      :min-height="160"
    />
    <template v-else>
      <div class="ai-rule-summary">
        <div class="ai-rule-summary__copy">
          <InfoFilled class="h-4 w-4 text-accent" />
          <span>{{ summary.text }}</span>
        </div>
        <div class="ai-rule-summary__actions">
          <div v-if="showApplyGroupSelect" class="ai-rule-summary__group-select">
            <span>添加到规则组</span>
            <el-select
              :model-value="selectedApplyGroupId"
              clearable
              filterable
              size="small"
              placeholder="不选择，添加到 AI生成规则组"
              @update:model-value="updateSelectedApplyGroupId"
            >
              <el-option
                v-for="group in applyGroupOptions"
                :key="group.group_id"
                :label="group.group_name"
                :value="group.group_id"
              />
            </el-select>
          </div>
          <span class="ai-rule-summary__badge" :class="`is-${summary.tone}`">
            {{ summary.label }}
          </span>
        </div>
      </div>

      <div class="ai-rule-result-list__items">
        <AiRuleResultItem
          v-for="item in items"
          :key="item.id"
          :item="item"
          :can-apply="canApply"
          :can-auto-complete-apply="canAutoCompleteApply"
          :auto-complete-apply-loading="autoCompleteApplyLoading"
          @view-config="(value) => emit('view-config', value)"
          @apply-rule="(value) => emit('apply-rule', value)"
          @resolve-missing="(value) => emit('resolve-missing', value)"
          @auto-complete-apply="emit('auto-complete-apply')"
          @rewrite-rule="emit('rewrite-rule')"
        />
      </div>
    </template>
  </section>
</template>

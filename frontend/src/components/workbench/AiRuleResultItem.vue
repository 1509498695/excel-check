<script setup lang="ts">
import {
  CircleCheck,
  CircleClose,
  CirclePlus,
  EditPen,
  MagicStick,
  Plus,
  QuestionFilled,
  View,
} from '@element-plus/icons-vue'

import PrimaryButton from '../shell/PrimaryButton.vue'
import SecondaryButton from '../shell/SecondaryButton.vue'
import type { AiMissingItem } from '../../types/ai'
import type { AiRuleResultViewModel, AiRuleUiStatus } from '../../utils/aiRuleViewModel'
import { getStatusLabel } from '../../utils/aiRuleViewModel'

defineProps<{
  item: AiRuleResultViewModel
  canApply: boolean
  canAutoCompleteApply: boolean
  autoCompleteApplyLoading: boolean
}>()

const emit = defineEmits<{
  (e: 'view-config', item: AiRuleResultViewModel): void
  (e: 'apply-rule', item: AiRuleResultViewModel): void
  (e: 'resolve-missing', missing: AiMissingItem | undefined): void
  (e: 'auto-complete-apply'): void
  (e: 'rewrite-rule'): void
}>()

const statusIconMap: Record<AiRuleUiStatus, unknown> = {
  ready: CircleCheck,
  duplicate: CirclePlus,
  needs_input: QuestionFilled,
  rejected: CircleClose,
  applied: CircleCheck,
  loading: QuestionFilled,
  empty: QuestionFilled,
  error: CircleClose,
}

function getStatusIcon(status: AiRuleUiStatus): unknown {
  return statusIconMap[status]
}
</script>

<template>
  <article class="ai-rule-result-item" :class="`is-${item.status}`">
    <div class="ai-rule-result-item__status">
      <span class="ai-rule-result-item__icon">
        <component :is="getStatusIcon(item.status)" class="h-4 w-4" />
      </span>
      <span class="ai-rule-status-label" :class="`is-${item.status}`">
        {{ getStatusLabel(item.status) }}
      </span>
    </div>

    <div class="ai-rule-result-item__main">
      <h4>{{ item.title }}</h4>
      <p class="ai-rule-result-item__meta">{{ item.metaText }}</p>
      <p v-if="item.missingText" class="ai-rule-result-item__missing">
        缺失信息：{{ item.missingText }}
      </p>
      <p v-if="item.reasonText" class="ai-rule-result-item__reason">
        原因：{{ item.reasonText }}
      </p>
    </div>

    <div class="ai-rule-result-item__actions">
      <template v-if="item.status === 'ready'">
        <SecondaryButton size="sm" @click="emit('view-config', item)">
          <template #icon><View /></template>
          查看配置
        </SecondaryButton>
        <PrimaryButton size="sm" :disabled="!canApply" @click="emit('apply-rule', item)">
          <template #icon><Plus /></template>
          添加规则
        </PrimaryButton>
      </template>
      <template v-else-if="item.status === 'duplicate'">
        <SecondaryButton size="sm" disabled>已有规则</SecondaryButton>
      </template>
      <template v-else-if="item.status === 'needs_input'">
        <PrimaryButton
          size="sm"
          :disabled="!canAutoCompleteApply"
          :loading="autoCompleteApplyLoading"
          @click="emit('auto-complete-apply')"
        >
          <template #icon><MagicStick /></template>
          一键补齐并添加
        </PrimaryButton>
        <SecondaryButton size="sm" @click="emit('resolve-missing', item.missing)">
          选择数据源
        </SecondaryButton>
        <SecondaryButton size="sm" @click="emit('resolve-missing', item.missing)">
          新增数据源
        </SecondaryButton>
        <SecondaryButton size="sm" @click="emit('resolve-missing', item.missing)">
          补充字段线索
        </SecondaryButton>
      </template>
      <template v-else-if="item.status === 'rejected'">
        <SecondaryButton size="sm" @click="emit('rewrite-rule')">
          <template #icon><EditPen /></template>
          改写规则
        </SecondaryButton>
      </template>
      <template v-else-if="item.status === 'applied'">
        <SecondaryButton size="sm" disabled>已添加</SecondaryButton>
      </template>
    </div>
  </article>
</template>

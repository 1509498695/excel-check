<script setup lang="ts">
import { computed } from 'vue'
import StatusBadge from './StatusBadge.vue'
import type { StatusBadgeType } from './types'

type SectionHeaderTone = 'pending' | 'active' | 'done' | 'warn' | 'error'

const props = withDefaults(
  defineProps<{
    title: string
    description?: string
    variant?: 'simple' | 'workbench'
    step?: string
    statusLabel?: string
    statusTone?: SectionHeaderTone
    statusType?: StatusBadgeType
  }>(),
  {
    description: '',
    variant: 'simple',
    step: '',
    statusLabel: '',
    statusTone: 'done',
    statusType: undefined,
  },
)

const normalizedStatusType = computed<StatusBadgeType>(() => {
  if (props.statusType) return props.statusType
  if (props.statusTone === 'done') return 'success'
  if (props.statusTone === 'active') return 'success'
  if (props.statusTone === 'warn') return 'warning'
  if (props.statusTone === 'error') return 'danger'
  return 'pending'
})
</script>

<template>
  <div v-if="variant === 'workbench'" class="ui-section-header workbench-section-head">
    <span class="workbench-section-head__index">{{ step }}</span>
    <div class="workbench-section-head__content">
      <div class="workbench-section-head__title-row">
        <h2 class="workbench-section-head__title">{{ title }}</h2>
        <StatusBadge v-if="statusLabel" :type="normalizedStatusType" :label="statusLabel" />
      </div>
      <p v-if="description" class="workbench-section-head__description">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="workbench-section-head__actions">
      <slot name="actions" />
    </div>
  </div>

  <div v-else class="ui-section-header ui-section-header--simple">
    <div class="ui-section-header__copy">
      <div class="ui-section-header__title-row">
        <h2 class="ui-section-header__title">{{ title }}</h2>
        <StatusBadge v-if="statusLabel" :type="normalizedStatusType" :label="statusLabel" />
      </div>
      <p v-if="description" class="ui-section-header__description">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="ui-section-header__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

type SectionHeaderTone = 'pending' | 'active' | 'done' | 'warn' | 'error'

const props = withDefaults(
  defineProps<{
    title: string
    description?: string
    variant?: 'simple' | 'workbench'
    step?: string
    statusLabel?: string
    statusTone?: SectionHeaderTone
  }>(),
  {
    description: '',
    variant: 'simple',
    step: '',
    statusLabel: '',
    statusTone: 'done',
  },
)

const statusClass = computed(() => {
  if (props.statusTone === 'pending') {
    return 'bg-slate-100 text-slate-600'
  }
  if (props.statusTone === 'active') {
    return 'bg-accent-soft text-accent-ink'
  }
  if (props.statusTone === 'warn') {
    return 'bg-warning-soft/70 text-amber-700'
  }
  if (props.statusTone === 'error') {
    return 'bg-danger-soft/70 text-danger'
  }
  return 'bg-green-50 text-green-600'
})
</script>

<template>
  <div v-if="variant === 'workbench'" class="workbench-section-head">
    <span class="workbench-section-head__index">{{ step }}</span>
    <div class="workbench-section-head__content">
      <div class="workbench-section-head__title-row">
        <h2 class="workbench-section-head__title">{{ title }}</h2>
        <span v-if="statusLabel" class="workbench-section-head__status" :class="statusClass">
          ● {{ statusLabel }}
        </span>
      </div>
      <p v-if="description" class="workbench-section-head__description">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="workbench-section-head__actions">
      <slot name="actions" />
    </div>
  </div>

  <div v-else class="flex items-end justify-between gap-4">
    <div class="min-w-0">
      <h2 class="text-[15px] font-semibold tracking-tight text-ink-900">{{ title }}</h2>
      <p v-if="description" class="mt-1 text-[12px] text-ink-500">{{ description }}</p>
    </div>
    <div class="flex items-center gap-2 shrink-0">
      <slot name="actions" />
    </div>
  </div>
</template>

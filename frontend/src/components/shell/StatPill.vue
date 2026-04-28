<script setup lang="ts">
import MetricCard from './MetricCard.vue'
import type { StatusBadgeType } from './types'

type Tone = 'pending' | 'active' | 'done' | 'warn' | 'error'

withDefaults(
  defineProps<{
    label: string
    value: number | string
    statusLabel: string
    statusTone?: Tone
  }>(),
  {
    statusTone: 'pending',
  },
)

const toneMap: Record<Tone, StatusBadgeType> = {
  pending: 'neutral',
  active: 'success',
  done: 'success',
  warn: 'warning',
  error: 'danger',
}
</script>

<template>
  <MetricCard
    :label="label"
    :value="value"
    :status-label="statusLabel"
    :status-type="toneMap[statusTone]"
  />
</template>

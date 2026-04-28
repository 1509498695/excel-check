<script setup lang="ts">
import StatusBadge from './StatusBadge.vue'
import type { StatusBadgeType } from './types'

type Tone = 'pending' | 'active' | 'done' | 'warn' | 'error'

const props = withDefaults(
  defineProps<{
    tone?: Tone
    label: string
  }>(),
  {
    tone: 'pending',
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
  <StatusBadge :type="toneMap[props.tone]" :label="label" />
</template>

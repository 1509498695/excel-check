<script setup lang="ts">
import { computed } from 'vue'
import type { StatusBadgeType } from './types'

const props = withDefaults(
  defineProps<{
    type?: StatusBadgeType
    label: string
  }>(),
  {
    type: 'neutral',
  },
)

const badgeClass = computed(() => `ui-status-badge--${props.type}`)
</script>

<template>
  <span class="ui-status-badge" :class="badgeClass">
    <span class="ui-status-badge__dot"></span>
    <span class="ui-status-badge__label">{{ label }}</span>
  </span>
</template>

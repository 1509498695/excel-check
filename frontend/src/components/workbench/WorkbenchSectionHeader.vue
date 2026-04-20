<script setup lang="ts">
import SectionHeader from '../shell/SectionHeader.vue'

withDefaults(
  defineProps<{
    step: string
    title: string
    description: string
    statusLabel?: string
    statusTone?: 'pending' | 'active' | 'done' | 'warn' | 'error'
  }>(),
  {
    statusLabel: '已完成',
    statusTone: 'done',
  },
)
</script>

<template>
  <SectionHeader
    variant="workbench"
    :step="step"
    :title="title"
    :description="description"
    :status-label="statusLabel"
    :status-tone="statusTone"
  />
</template>

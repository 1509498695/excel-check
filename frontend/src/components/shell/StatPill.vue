<script setup lang="ts">
// 共享 KPI 卡：caption + 等宽大数字 + StatusDot
// 不是交互单元，禁止 hover 浮起
import StatusDot from './StatusDot.vue'

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
</script>

<template>
  <article class="rounded-card border border-line bg-card p-5 shadow-card-1">
    <div class="text-[12px] font-medium text-ink-500">{{ label }}</div>
    <div class="font-mono mt-3 text-[32px] font-bold leading-none text-ink-900">
      {{ value }}
    </div>
    <div class="mt-3">
      <StatusDot :tone="statusTone" :label="statusLabel" />
    </div>
  </article>
</template>

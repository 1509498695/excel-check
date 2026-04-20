<script setup lang="ts">
// 共享状态胶囊：4 色圆点 + 文字
// pending=ink-300 / active=accent / done=success / warn=warning / error=danger
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

const toneClasses: Record<Tone, { wrap: string; dot: string }> = {
  pending: { wrap: 'bg-subtle text-ink-500', dot: 'bg-ink-300' },
  active: { wrap: 'bg-accent-soft text-accent-ink', dot: 'bg-accent' },
  done: { wrap: 'bg-success-soft text-success', dot: 'bg-success' },
  warn: { wrap: 'bg-warning-soft text-warning', dot: 'bg-warning' },
  error: { wrap: 'bg-danger-soft text-danger', dot: 'bg-danger' },
}
</script>

<template>
  <span
    class="inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[12px] font-medium"
    :class="toneClasses[props.tone].wrap"
  >
    <span class="h-1.5 w-1.5 rounded-full" :class="toneClasses[props.tone].dot"></span>
    {{ label }}
  </span>
</template>

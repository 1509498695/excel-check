<script setup lang="ts">
// 共享空态：圆形浅底 icon + 标题 + 1 句副文案 + 可选 CTA 槽
withDefaults(
  defineProps<{
    title: string
    description?: string
  }>(),
  {
    description: '',
  },
)
</script>

<template>
  <div class="flex flex-col items-center justify-center gap-3 py-12 text-center">
    <div class="flex h-10 w-10 items-center justify-center rounded-full bg-canvas">
      <slot name="icon">
        <svg class="h-4 w-4 text-ink-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M4 4h12l4 4v12H4z M14 4v6h6" />
        </svg>
      </slot>
    </div>
    <div class="text-[13px] font-medium text-ink-700">{{ title }}</div>
    <div v-if="description" class="text-[12px] text-ink-500">{{ description }}</div>
    <div v-if="$slots.action" class="mt-2">
      <slot name="action" />
    </div>
  </div>
</template>

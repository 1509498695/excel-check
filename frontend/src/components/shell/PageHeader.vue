<script setup lang="ts">
// 共享页面头：面包屑 + h1 标题 + 右侧 actions 槽
// 用于替代旧的 app-shell-toolbar，由各业务页面自己提供顶栏
withDefaults(
  defineProps<{
    breadcrumb?: string
    title: string
  }>(),
  {
    breadcrumb: '',
  },
)
</script>

<template>
  <header class="flex items-center justify-between gap-4 border-b border-line bg-card px-8 py-4">
    <div class="min-w-0">
      <div v-if="breadcrumb" class="text-[12px] text-ink-500">{{ breadcrumb }}</div>
      <h1 class="mt-0.5 text-[18px] font-semibold tracking-tight text-ink-900">
        {{ title }}
      </h1>
    </div>
    <div class="flex items-center gap-2 shrink-0">
      <slot name="actions" />
    </div>
  </header>
</template>

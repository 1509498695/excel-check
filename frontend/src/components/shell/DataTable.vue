<script setup lang="ts">
// 共享数据表骨架：极简表头（canvas 底 + 12px uppercase）+ 行 hover bg-canvas
// 不规定列结构，调用方通过 thead/tbody slot 自行注入；空态由调用方走 EmptyState
defineProps<{
  ariaLabel?: string
}>()
</script>

<template>
  <div class="overflow-hidden rounded-field border border-line">
    <table class="w-full table-fixed text-[13px]" :aria-label="ariaLabel">
      <thead class="bg-canvas text-left text-[12px] font-medium uppercase tracking-wider text-ink-500">
        <slot name="head" />
      </thead>
      <tbody>
        <slot name="body" />
      </tbody>
    </table>
  </div>
</template>

<style scoped>
/* 给所有数据表行加上极轻 hover，强化"行是基本单元"的语义 */
:deep(tbody tr) {
  transition: background-color 150ms cubic-bezier(0.2, 0, 0, 1);
}
:deep(tbody tr:hover) {
  background-color: #f7f8fa;
}
:deep(tbody tr:not(:last-child) td) {
  border-bottom: 1px solid #e5e7eb;
}
:deep(td) {
  padding: 12px 16px;
  vertical-align: middle;
  text-align: left;
}
:deep(th) {
  padding: 12px 16px;
  vertical-align: middle;
  text-align: left;
}
</style>

<script setup lang="ts">
withDefaults(
  defineProps<{
    ariaLabel?: string
    fixed?: boolean
  }>(),
  {
    fixed: true,
  },
)
</script>

<template>
  <div class="ui-data-table">
    <table class="w-full text-[13px]" :class="fixed ? 'table-fixed' : ''" :aria-label="ariaLabel">
      <thead>
        <slot name="head" />
      </thead>
      <tbody>
        <slot name="body" />
      </tbody>
    </table>
  </div>
</template>

<style scoped>
:deep(tbody tr) {
  transition: background-color 150ms cubic-bezier(0.2, 0, 0, 1);
}
:deep(tbody tr:hover) {
  background-color: #f3f7ff;
}
:deep(tbody tr:not(:last-child) td) {
  border-bottom: 1px solid #eef2f7;
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
  color: #94a3b8;
  background: #f6f8fc;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.02em;
}
</style>

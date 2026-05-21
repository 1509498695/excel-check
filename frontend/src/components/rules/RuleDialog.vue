<script setup lang="ts">
defineProps<{
  modelValue: boolean
  title: string
  width?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    :width="width ?? '760px'"
    destroy-on-close
    @update:model-value="emit('update:modelValue', Boolean($event))"
  >
    <slot />
    <template
      v-if="$slots.footer"
      #footer
    >
      <slot name="footer" />
    </template>
  </el-dialog>
</template>

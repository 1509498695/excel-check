<script setup lang="ts">
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
  <header class="ui-page-header">
    <div class="ui-page-header__copy">
      <div v-if="breadcrumb" class="ui-page-header__breadcrumb">{{ breadcrumb }}</div>
      <h1 class="ui-page-header__title">
        {{ title }}
      </h1>
    </div>
    <div v-if="$slots.actions" class="ui-page-header__actions">
      <slot name="actions" />
    </div>
  </header>
</template>

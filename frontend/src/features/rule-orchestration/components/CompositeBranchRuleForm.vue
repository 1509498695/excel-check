<script setup lang="ts">
import type { CompositeRuleConfig } from '../../../types/fixedRules'

defineProps<{
  config: CompositeRuleConfig
}>()
</script>

<template>
  <slot :config="config" />
</template>

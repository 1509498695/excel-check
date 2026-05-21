<script setup lang="ts">
import type { MultiCompositePipelineConfig } from '../../../types/fixedRules'

defineProps<{
  config: MultiCompositePipelineConfig
}>()
</script>

<template>
  <slot :config="config" />
</template>

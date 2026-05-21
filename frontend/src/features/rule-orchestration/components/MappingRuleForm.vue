<script setup lang="ts">
import type { MultiCompositeMappingConfig } from '../../../types/fixedRules'

defineProps<{
  config: MultiCompositeMappingConfig
}>()
</script>

<template>
  <slot :config="config" />
</template>

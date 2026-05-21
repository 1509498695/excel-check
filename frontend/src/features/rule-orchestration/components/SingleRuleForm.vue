<script setup lang="ts">
import type { RuleFormState } from '../types'

defineProps<{
  form: RuleFormState
}>()
</script>

<template>
  <slot :form="form" />
</template>

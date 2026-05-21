<script setup lang="ts">
import type { CompositeCondition, DualCompositeComparison } from '../../../types/fixedRules'
import type { RuleFormState } from '../types'

defineProps<{
  form: RuleFormState
  comparisons: DualCompositeComparison[]
  leftFilters: CompositeCondition[]
  rightFilters: CompositeCondition[]
}>()
</script>

<template>
  <slot
    :form="form"
    :comparisons="comparisons"
    :left-filters="leftFilters"
    :right-filters="rightFilters"
  />
</template>

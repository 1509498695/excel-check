<script setup lang="ts">
import type { CompositeCondition } from '../../types/fixedRules'
import type { FieldOption } from '../../rules'

defineProps<{
  condition: CompositeCondition
  fieldOptions: FieldOption[]
  operatorOptions: Array<{ label: string; value: string }>
}>()
</script>

<template>
  <div class="grid grid-cols-3 gap-3">
    <el-select
      v-model="condition.field"
      filterable
      placeholder="字段"
    >
      <el-option
        v-for="field in fieldOptions"
        :key="field.value"
        :label="field.label"
        :value="field.value"
      />
    </el-select>
    <el-select
      v-model="condition.operator"
      placeholder="条件"
    >
      <el-option
        v-for="option in operatorOptions"
        :key="option.value"
        :label="option.label"
        :value="option.value"
      />
    </el-select>
    <el-input
      v-model="condition.expected_value"
      placeholder="比较值"
    />
  </div>
</template>

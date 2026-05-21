<script setup lang="ts">
import type { DualCompositeComparison, FixedRuleOperator } from '../../types/fixedRules'
import type { FieldOption } from '../../rules'

defineProps<{
  comparison: DualCompositeComparison
  leftFieldOptions: FieldOption[]
  rightFieldOptions: FieldOption[]
  operatorOptions: Array<{ label: string; value: FixedRuleOperator | 'not_null' }>
}>()
</script>

<template>
  <div class="grid grid-cols-3 gap-3">
    <el-select
      v-model="comparison.left_field"
      filterable
      placeholder="左侧字段"
    >
      <el-option
        v-for="field in leftFieldOptions"
        :key="field.value"
        :label="field.label"
        :value="field.value"
      />
    </el-select>
    <el-select
      v-model="comparison.operator"
      placeholder="比较"
    >
      <el-option
        v-for="option in operatorOptions"
        :key="option.value"
        :label="option.label"
        :value="option.value"
      />
    </el-select>
    <el-select
      v-model="comparison.right_field"
      filterable
      placeholder="右侧字段"
    >
      <el-option
        v-for="field in rightFieldOptions"
        :key="field.value"
        :label="field.label"
        :value="field.value"
      />
    </el-select>
  </div>
</template>

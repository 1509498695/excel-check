<script setup lang="ts">
import type { FixedRuleDefinition, FixedRuleGroup } from '../../../types/fixedRules'
import type { ImportScopeMode } from '../types'

defineProps<{
  mode: ImportScopeMode
  groupIds: string[]
  ruleIds: string[]
  groups: FixedRuleGroup[]
  rules: FixedRuleDefinition[]
}>()

const emit = defineEmits<{
  (event: 'update:mode', value: ImportScopeMode): void
  (event: 'update:groupIds', value: string[]): void
  (event: 'update:ruleIds', value: string[]): void
}>()
</script>

<template>
  <div class="space-y-4">
    <el-radio-group :model-value="mode" @change="emit('update:mode', $event as ImportScopeMode)">
      <el-radio-button label="groups">按规则组</el-radio-button>
      <el-radio-button label="rules">按规则</el-radio-button>
    </el-radio-group>

    <el-select
      v-if="mode === 'groups'"
      :model-value="groupIds"
      class="w-full"
      multiple
      filterable
      placeholder="选择要导入的个人校验规则组"
      @change="emit('update:groupIds', $event as string[])"
    >
      <el-option
        v-for="group in groups"
        :key="group.group_id"
        :label="group.group_name"
        :value="group.group_id"
      />
    </el-select>

    <el-select
      v-if="mode === 'rules'"
      :model-value="ruleIds"
      class="w-full"
      multiple
      filterable
      placeholder="选择要导入的个人校验规则"
      @change="emit('update:ruleIds', $event as string[])"
    >
      <el-option
        v-for="rule in rules"
        :key="rule.rule_id"
        :label="rule.rule_name"
        :value="rule.rule_id"
      />
    </el-select>
  </div>
</template>

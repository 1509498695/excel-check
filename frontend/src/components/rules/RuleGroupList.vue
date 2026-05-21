<script setup lang="ts">
import { Plus, Search } from '@element-plus/icons-vue'

import SecondaryButton from '../shell/SecondaryButton.vue'
import type { FixedRuleGroup } from '../../types/fixedRules'

defineProps<{
  groups: FixedRuleGroup[]
  selectedGroupId: string
  keyword: string
  counts: Record<string, number>
  invalidGroupIds: Set<string>
}>()

const emit = defineEmits<{
  (e: 'update:keyword', value: string): void
  (e: 'select', groupId: string): void
  (e: 'create'): void
}>()
</script>

<template>
  <div class="workbench-rule-sidebar-toolbar">
    <el-input
      :model-value="keyword"
      placeholder="搜索规则组"
      :prefix-icon="Search"
      clearable
      size="default"
      @update:model-value="emit('update:keyword', String($event))"
    />
    <SecondaryButton
      size="sm"
      class="shrink-0"
      @click="emit('create')"
    >
      <template #icon><Plus /></template>
      新建
    </SecondaryButton>
  </div>

  <nav class="workbench-rule-menu">
    <button
      v-for="group in groups"
      :key="group.group_id"
      type="button"
      class="workbench-rule-menu-item"
      :class="group.group_id === selectedGroupId ? 'is-active' : ''"
      @click="emit('select', group.group_id)"
    >
      <span class="workbench-rule-menu-item__label">{{ group.group_name }}</span>
      <span
        v-if="invalidGroupIds.has(group.group_id)"
        class="workbench-rule-menu-item__dot"
        title="待修复"
      ></span>
      <span class="workbench-rule-menu-item__count">
        {{ counts[group.group_id] ?? 0 }}
      </span>
    </button>
  </nav>
</template>

<script setup lang="ts">
import { Box, Coin, Lock } from '@element-plus/icons-vue'

import EmptyState from '../shell/EmptyState.vue'
import type { PendingConfigPreviewViewModel } from '../../utils/aiRuleViewModel'

defineProps<{
  preview: PendingConfigPreviewViewModel
}>()

function hasItems(items: string[]): boolean {
  return items.length > 0
}
</script>

<template>
  <section class="smart-rule-card pending-config-preview">
    <div class="smart-rule-card__header">
      <h3>待添加配置预览</h3>
    </div>

    <EmptyState
      v-if="!hasItems(preview.sources) && !hasItems(preview.variables) && !hasItems(preview.rules)"
      variant="table"
      icon-tone="rule"
      title="暂无可添加规则"
      description="只有 ready 或已补齐可添加的规则会进入配置预览"
      :min-height="120"
    />

    <div v-else class="pending-config-preview__grid">
      <article class="pending-config-preview__item">
        <span class="pending-config-preview__icon is-source"><Coin class="h-6 w-6" /></span>
        <div>
          <h4>数据源</h4>
          <ul>
            <li v-for="item in preview.sources" :key="item">{{ item }}</li>
          </ul>
        </div>
      </article>

      <article class="pending-config-preview__item">
        <span class="pending-config-preview__icon is-variable"><Box class="h-6 w-6" /></span>
        <div>
          <h4>变量池</h4>
          <ul>
            <li v-for="item in preview.variables" :key="item">{{ item }}</li>
          </ul>
        </div>
      </article>

      <article class="pending-config-preview__item">
        <span class="pending-config-preview__icon is-rule"><Lock class="h-6 w-6" /></span>
        <div>
          <h4>规则</h4>
          <ul>
            <li v-for="item in preview.rules" :key="item">{{ item }}</li>
          </ul>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ArrowRight, Delete, Document } from '@element-plus/icons-vue'

import type { AiRuleDraft } from '../../types/ai'
import type { DraftHistoryViewModel } from '../../utils/aiRuleViewModel'

defineProps<{
  items: DraftHistoryViewModel[]
  loading: boolean
}>()

const emit = defineEmits<{
  (e: 'clear'): void
  (e: 'fill', draft: AiRuleDraft): void
  (e: 'delete', draft: AiRuleDraft): void
}>()
</script>

<template>
  <aside class="draft-history-panel">
    <div class="draft-history-panel__head">
      <div>
        <h3>草稿历史</h3>
        <p>最近 20 条</p>
      </div>
      <button
        type="button"
        class="draft-history-panel__clear"
        :disabled="!items.length"
        @click="emit('clear')"
      >
        清空
      </button>
    </div>

    <div v-if="loading" class="draft-history-panel__empty">正在读取草稿历史…</div>
    <div v-else-if="!items.length" class="draft-history-panel__empty">暂无历史草稿</div>
    <div v-else class="draft-history-panel__list">
      <article
        v-for="item in items"
        :key="item.id"
        class="draft-history-card"
        :class="`is-${item.status}`"
      >
        <span class="draft-history-card__icon">
          <Document class="h-5 w-5" />
        </span>
        <div class="draft-history-card__main">
          <div class="draft-history-card__top">
            <h4>{{ item.title }}</h4>
            <span class="ai-rule-status-label" :class="`is-${item.status}`">
              {{ item.status === 'applied' ? 'applied' : item.status }}
            </span>
          </div>
          <p>{{ item.ruleCount }} 条规则</p>
          <p>{{ item.timeLabel }}</p>
          <div class="draft-history-card__actions">
            <button type="button" class="draft-history-card__fill" @click="emit('fill', item.draft)">
              回填 <ArrowRight class="h-3.5 w-3.5" />
            </button>
            <button
              v-if="item.draft.draft_id"
              type="button"
              class="draft-history-card__delete"
              @click="emit('delete', item.draft)"
            >
              <Delete class="h-3.5 w-3.5" />
              删除
            </button>
          </div>
        </div>
      </article>
    </div>
  </aside>
</template>

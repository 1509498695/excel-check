<script setup lang="ts">
type SectionStatus = 'pending' | 'active' | 'done'

withDefaults(
  defineProps<{
    step: string
    title: string
    description: string
    status?: SectionStatus
    hint?: string
  }>(),
  {
    status: 'pending',
    hint: '',
  },
)

const sectionStatusLabels: Record<SectionStatus, string> = {
  pending: '待完善',
  active: '进行中',
  done: '已完成',
}
</script>

<template>
  <section class="section-block" :class="`section-${status}`">
    <header class="section-header">
      <div class="section-heading">
        <span class="step-badge">步骤 {{ step }}</span>
        <div class="section-copy">
          <div class="section-title-row">
            <h2>{{ title }}</h2>
            <span class="section-status" :class="`is-${status}`">
              {{ sectionStatusLabels[status] }}
            </span>
          </div>
          <p>{{ description }}</p>
          <p v-if="hint" class="section-hint">{{ hint }}</p>
        </div>
      </div>
      <div class="section-actions">
        <slot name="actions" />
      </div>
    </header>

    <div class="section-content">
      <slot />
    </div>
  </section>
</template>

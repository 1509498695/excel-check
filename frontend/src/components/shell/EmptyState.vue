<script setup lang="ts">
import { computed } from 'vue'

type EmptyStateVariant = 'table' | 'panel' | 'result'
type EmptyStateIconTone = 'source' | 'variable' | 'rule' | 'result' | 'default'

const props = withDefaults(
  defineProps<{
    title: string
    description?: string
    variant?: EmptyStateVariant
    minHeight?: number | string
    iconTone?: EmptyStateIconTone
  }>(),
  {
    description: '',
    variant: 'panel',
    minHeight: undefined,
    iconTone: 'default',
  },
)

const stateClass = computed(() => [
  `ui-empty-state--${props.variant}`,
  `ui-empty-state--tone-${props.iconTone}`,
])

const stateStyle = computed(() => {
  if (props.minHeight === undefined) {
    return undefined
  }
  const value = typeof props.minHeight === 'number' ? `${props.minHeight}px` : props.minHeight
  return { minHeight: value }
})
</script>

<template>
  <div class="ui-empty-state" :class="stateClass" :style="stateStyle">
    <div class="ui-empty-state__icon">
      <slot name="icon">
        <svg
          v-if="iconTone === 'source'"
          class="ui-empty-state__glyph"
          viewBox="0 0 32 32"
          fill="none"
          aria-hidden="true"
        >
          <ellipse cx="16" cy="8" rx="8" ry="4" stroke="currentColor" stroke-width="2" />
          <path d="M8 8v10c0 2.2 3.6 4 8 4s8-1.8 8-4V8" stroke="currentColor" stroke-width="2" />
          <path d="M8 13c0 2.2 3.6 4 8 4s8-1.8 8-4" stroke="currentColor" stroke-width="2" />
          <path d="M11 23.5 16 27l5-3.5" stroke="#cbd5e1" stroke-width="2" stroke-linecap="round" />
        </svg>
        <svg
          v-else-if="iconTone === 'variable'"
          class="ui-empty-state__glyph"
          viewBox="0 0 32 32"
          fill="none"
          aria-hidden="true"
        >
          <path d="m12 10-5 6 5 6M20 10l5 6-5 6" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" />
          <path d="m17 8-2 16" stroke="#cbd5e1" stroke-width="2" stroke-linecap="round" />
        </svg>
        <svg
          v-else-if="iconTone === 'rule'"
          class="ui-empty-state__glyph"
          viewBox="0 0 32 32"
          fill="none"
          aria-hidden="true"
        >
          <rect x="7" y="7" width="6" height="6" rx="2" stroke="currentColor" stroke-width="2" />
          <rect x="19" y="7" width="6" height="6" rx="2" stroke="currentColor" stroke-width="2" />
          <rect x="13" y="19" width="6" height="6" rx="2" stroke="currentColor" stroke-width="2" />
          <path d="M13 10h6M10 13v4c0 2 1 3 3 3M22 13v4c0 2-1 3-3 3" stroke="#cbd5e1" stroke-width="2" stroke-linecap="round" />
        </svg>
        <svg
          v-else-if="iconTone === 'result'"
          class="ui-empty-state__glyph"
          viewBox="0 0 32 32"
          fill="none"
          aria-hidden="true"
        >
          <path d="M9 5h10l5 5v15a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z" stroke="currentColor" stroke-width="2" />
          <path d="M19 5v6h6M11 15h8M11 19h5" stroke="#cbd5e1" stroke-width="2" stroke-linecap="round" />
          <circle cx="22" cy="22" r="3.2" stroke="currentColor" stroke-width="2" />
          <path d="m24.5 24.5 2.5 2.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
        </svg>
        <svg
          v-else
          class="ui-empty-state__glyph"
          viewBox="0 0 32 32"
          fill="none"
          aria-hidden="true"
        >
          <path d="m7 12 9-5 9 5-9 5-9-5Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round" />
          <path d="M7 12v8l9 5 9-5v-8M16 17v8" stroke="#cbd5e1" stroke-width="2" stroke-linejoin="round" />
        </svg>
      </slot>
    </div>
    <div class="ui-empty-state__title">{{ title }}</div>
    <div v-if="description" class="ui-empty-state__description">{{ description }}</div>
    <div v-if="$slots.action" class="ui-empty-state__action">
      <slot name="action" />
    </div>
  </div>
</template>

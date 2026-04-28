<script setup lang="ts">
import { computed } from 'vue'

type CardPadding = 'none' | 'sm' | 'md' | 'lg'

const props = withDefaults(
  defineProps<{
    as?: string
    padding?: CardPadding
    hoverable?: boolean
  }>(),
  {
    as: 'section',
    padding: 'md',
    hoverable: false,
  },
)

const paddingClass = computed(() => {
  if (props.padding === 'none') return 'ui-card--padding-none'
  if (props.padding === 'sm') return 'ui-card--padding-sm'
  if (props.padding === 'lg') return 'ui-card--padding-lg'
  return 'ui-card--padding-md'
})
</script>

<template>
  <component
    :is="as"
    class="ui-card"
    :class="[paddingClass, hoverable ? 'ui-card--hoverable' : '']"
  >
    <slot />
  </component>
</template>

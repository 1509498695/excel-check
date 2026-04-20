<script setup lang="ts">
// 工作台专用的折叠步骤卡：不依赖任何 store，纯 props/emit
// 仅供 MainBoard 使用，避免污染共用的 SectionBlock
import { computed } from 'vue'
import StatusDot from '../shell/StatusDot.vue'

type SectionStatus = 'pending' | 'active' | 'done'

const props = withDefaults(
  defineProps<{
    step: string
    title: string
    description: string
    status?: SectionStatus
    expanded: boolean
    isCurrent?: boolean
  }>(),
  {
    status: 'pending',
    isCurrent: false,
  },
)

const emit = defineEmits<{
  (event: 'update:expanded', value: boolean): void
}>()

const sectionStatusLabels: Record<SectionStatus, string> = {
  pending: '待开始',
  active: '进行中',
  done: '已完成',
}

const statusToneMap: Record<SectionStatus, 'pending' | 'active' | 'done'> = {
  pending: 'pending',
  active: 'active',
  done: 'done',
}

// 顶部 2px 主色色带 + 1px line 边：当前激活步骤的视觉锚点（更扁、更安静）
const cardClass = computed(() => {
  if (props.isCurrent && props.expanded) {
    return 'border border-line shadow-card-2 ring-0 before:absolute before:inset-x-0 before:top-0 before:h-0.5 before:bg-accent before:rounded-t-card'
  }
  if (props.expanded) {
    return 'border border-line shadow-card-1'
  }
  return 'border border-line shadow-card-1 hover:border-ink-300'
})

function toggle(): void {
  emit('update:expanded', !props.expanded)
}
</script>

<template>
  <section
    class="relative rounded-card bg-card transition-all duration-200 ease-premium"
    :class="cardClass"
  >
    <!-- 折叠态：单行，整行点击展开 -->
    <button
      v-if="!expanded"
      type="button"
      class="group flex w-full items-center justify-between gap-4 px-6 py-4 text-left"
      @click="toggle"
    >
      <div class="flex items-center gap-3 min-w-0">
        <span
          class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-canvas font-mono text-[12px] font-semibold text-ink-500"
        >
          {{ step.padStart(2, '0') }}
        </span>
        <div class="min-w-0">
          <div class="text-[14px] font-medium text-ink-900 truncate">{{ title }}</div>
          <div class="text-[12px] text-ink-500 truncate">{{ description }}</div>
        </div>
        <StatusDot
          class="ml-2"
          :tone="statusToneMap[status]"
          :label="sectionStatusLabels[status]"
        />
      </div>
      <span class="inline-flex shrink-0 items-center gap-1 text-[12px] text-ink-500">
        展开
        <svg
          class="h-3.5 w-3.5 transition-transform duration-200 ease-premium group-hover:rotate-180"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </span>
    </button>

    <!-- 展开态 -->
    <template v-else>
      <header class="flex items-center justify-between gap-4 border-b border-line/70 px-6 py-4">
        <div class="flex items-center gap-3 min-w-0">
          <span
            class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md font-mono text-[12px] font-semibold"
            :class="isCurrent ? 'bg-accent-soft text-accent-ink' : 'bg-canvas text-ink-500'"
          >
            {{ step.padStart(2, '0') }}
          </span>
          <div class="min-w-0">
            <div class="text-[15px] font-semibold text-ink-900 truncate">{{ title }}</div>
            <div class="text-[12px] text-ink-500 truncate">{{ description }}</div>
          </div>
          <StatusDot
            class="ml-2"
            :tone="statusToneMap[status]"
            :label="sectionStatusLabels[status]"
          />
        </div>
        <div class="flex items-center gap-2 shrink-0">
          <slot name="actions" />
          <button
            type="button"
            class="group inline-flex items-center gap-1 rounded-field px-2.5 py-1.5 text-[12px] text-ink-500 transition hover:bg-canvas hover:text-ink-700"
            @click="toggle"
          >
            收起
            <svg
              class="h-3.5 w-3.5 transition-transform duration-200 ease-premium group-hover:-translate-y-0.5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <path d="M18 15l-6-6-6 6" />
            </svg>
          </button>
        </div>
      </header>
      <div class="px-6 py-5">
        <slot />
      </div>
    </template>
  </section>
</template>

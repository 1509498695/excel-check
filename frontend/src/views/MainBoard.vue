<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import DataSourcePanel from '../components/workbench/DataSourcePanel.vue'
import ResultBoardPanel from '../components/workbench/ResultBoardPanel.vue'
import WorkbenchRuleOrchestrationPanel from '../components/workbench/WorkbenchRuleOrchestrationPanel.vue'
import VariablePoolPanel from '../components/workbench/VariablePoolPanel.vue'
import PageHeader from '../components/shell/PageHeader.vue'
import SectionHeader from '../components/shell/SectionHeader.vue'
import StatPill from '../components/shell/StatPill.vue'
import { useWorkbenchStore } from '../store/workbench'

// 保持原有逻辑不变：工作台的数据加载、自动保存、执行与滚动行为全部维持现状。
const store = useWorkbenchStore()

type StepIndex = 1 | 2 | 3 | 4
type SectionStatus = 'pending' | 'active' | 'done'
type StatTone = 'pending' | 'active' | 'done' | 'warn' | 'error'

const selectedGuideStep = ref<StepIndex | null>(null)
const hasManuallySelectedGuideStep = ref(false)

onMounted(async () => {
  // 保留原有业务逻辑：工作台初始化仍并行读取能力与服务端配置。
  await Promise.all([store.loadCapabilities(), store.loadFromServer()])
})

watch(
  () => [store.sources, store.variables, store.ruleGroups, store.orchestrationRules],
  () => {
    store.triggerAutoSave()
  },
  { deep: true },
)

const sourceStepRef = ref<HTMLElement | null>(null)
const variableStepRef = ref<HTMLElement | null>(null)
const ruleStepRef = ref<HTMLElement | null>(null)
const resultStepRef = ref<HTMLElement | null>(null)
const dataSourcePanelRef = ref<{ openCreateDialog: () => void } | null>(null)
const variablePoolPanelRef = ref<{
  openSingleCreateTab: () => Promise<void>
  openCompositeCreateTab: () => Promise<void>
} | null>(null)

const overviewItems = computed<
  Array<{
    label: string
    value: number
    pendingHint: string
    readyHint: string
    pendingTone: StatTone
    readyTone: StatTone
  }>
>(() => [
  {
    label: '数据源',
    value: store.sources.length,
    pendingHint: '未接入',
    readyHint: '已接入',
    pendingTone: 'warn',
    readyTone: 'done',
  },
  {
    label: '变量',
    value: store.variables.length,
    pendingHint: '未配置',
    readyHint: '已就绪',
    pendingTone: 'pending',
    readyTone: 'done',
  },
  {
    label: '规则',
    value: store.orchestrationRuleCount,
    pendingHint: '未配置',
    readyHint: '已就绪',
    pendingTone: 'pending',
    readyTone: 'done',
  },
  {
    label: '最近异常',
    value: store.abnormalResults.length,
    pendingHint: '尚未执行',
    readyHint: '需关注',
    pendingTone: 'pending',
    readyTone: 'warn',
  },
])

const stepStatuses = computed<{
  source: SectionStatus
  variable: SectionStatus
  rule: SectionStatus
  result: SectionStatus
}>(() => ({
  source: store.sources.length ? 'done' : 'active',
  variable: !store.sources.length ? 'pending' : store.variables.length ? 'done' : 'active',
  rule: !store.variables.length ? 'pending' : store.orchestrationRuleCount ? 'done' : 'active',
  result: !store.orchestrationRuleCount
    ? 'pending'
    : store.executionMeta || store.pageError
      ? 'done'
      : 'active',
}))

const stepHints = computed(() => ({
  source: store.sources.length
    ? `已接入 ${store.sources.length} 个数据源`
    : '至少接入 1 个',
  variable: !store.sources.length
    ? `已沉淀 ${store.variables.length} 个变量`
    : `已沉淀 ${store.variables.length} 个变量`,
  rule: !store.variables.length
    ? `已编排 ${store.orchestrationRuleCount} 条规则`
    : `已编排 ${store.orchestrationRuleCount} 条规则`,
  result: '扫描统计与异常明细',
}))

function getSectionStatusLabel(step: StepIndex): string {
  if (step === 4) {
    if (store.pageError) {
      return '需关注'
    }
    return store.executionMeta ? '已完成' : '待执行'
  }

  if (step === 1) {
    return store.sources.length ? '已完成' : '待配置'
  }

  if (step === 2) {
    return store.variables.length ? '已完成' : '待配置'
  }

  return store.orchestrationRuleCount ? '已完成' : '待配置'
}

function getSectionStatusTone(step: StepIndex): 'pending' | 'done' | 'warn' {
  if (step === 4 && store.pageError) {
    return 'warn'
  }

  return getSectionStatusLabel(step) === '已完成' ? 'done' : 'pending'
}

const workflowGuide = computed(() => {
  if (!store.sources.length) {
    return { step: 1 as StepIndex, action: 'scroll' as const }
  }
  if (!store.variables.length) {
    return { step: 2 as StepIndex, action: 'scroll' as const }
  }
  if (!store.orchestrationRuleCount) {
    return { step: 3 as StepIndex, action: 'scroll' as const }
  }
  if (store.isExecuting || store.pageError || store.executionMeta) {
    return { step: 4 as StepIndex, action: 'scroll' as const }
  }
  return { step: 4 as StepIndex, action: 'execute' as const }
})

const activeGuideStep = computed(() => selectedGuideStep.value ?? workflowGuide.value.step)

const stepperItems = computed(() => [
  {
    step: 1 as StepIndex,
    label: '数据源',
    description: stepHints.value.source,
    status: stepStatuses.value.source,
  },
  {
    step: 2 as StepIndex,
    label: '变量池',
    description: stepHints.value.variable,
    status: stepStatuses.value.variable,
  },
  {
    step: 3 as StepIndex,
    label: '规则',
    description: stepHints.value.rule,
    status: stepStatuses.value.rule,
  },
  {
    step: 4 as StepIndex,
    label: '结果',
    description: stepHints.value.result,
    status: stepStatuses.value.result,
  },
])

watch(
  () => workflowGuide.value.step,
  (step) => {
    if (!hasManuallySelectedGuideStep.value) {
      selectedGuideStep.value = step
    }
  },
  { immediate: true },
)

function getStepRef(step: StepIndex): HTMLElement | null {
  if (step === 1) {
    return sourceStepRef.value
  }
  if (step === 2) {
    return variableStepRef.value
  }
  if (step === 3) {
    return ruleStepRef.value
  }
  return resultStepRef.value
}

async function scrollToStep(step: StepIndex): Promise<void> {
  await nextTick()
  getStepRef(step)?.scrollIntoView({
    behavior: 'smooth',
    block: 'start',
  })
}

async function runExecution(): Promise<void> {
  try {
    // 保留原有业务逻辑：执行入口仍调用原有校验接口并沿用原结果刷新流程。
    await store.executeValidation()
    await scrollToStep(4)
    ElMessage.success('校验完成，结果已刷新。')
  } catch {
    await scrollToStep(4)
  }
}

function applyDemoScenario(): void {
  // 保留原有业务逻辑：样例填充继续走原 store action。
  store.applyDemoScenario()
  ElMessage.success('样例已加载，可直接执行校验。')
}

function openDataSourceCreate(): void {
  dataSourcePanelRef.value?.openCreateDialog()
}

function openSingleVariableCreate(): void {
  void variablePoolPanelRef.value?.openSingleCreateTab()
}

function openCompositeVariableCreate(): void {
  void variablePoolPanelRef.value?.openCompositeCreateTab()
}

async function handleStepperClick(step: StepIndex): Promise<void> {
  hasManuallySelectedGuideStep.value = true
  selectedGuideStep.value = step
  await scrollToStep(step)
}

async function handleSourceSaved(_sourceId: string): Promise<void> {
  await scrollToStep(2)
}

async function handleVariableSaved(_tag: string): Promise<void> {
  await scrollToStep(2)
}
</script>

<template>
  <div class="flex h-full flex-col bg-canvas font-sans text-ink-700">
    <!-- TopBar：极简，左面包屑+标题，右动作 -->
    <PageHeader breadcrumb="主菜单 / 工作台" title="配置表校验工作台">
      <template #actions>
        <button
          v-if="store.pageError"
          type="button"
          class="ec-btn ec-btn-secondary"
          @click="store.clearPageError()"
        >
          <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M5 13l4 4L19 7" />
          </svg>
          清除错误
        </button>
        <button
          type="button"
          class="ec-btn ec-btn-secondary"
          @click="applyDemoScenario"
        >
          <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 4h16v16H4z M9 9h6v6H9z" />
          </svg>
          载入样例数据
        </button>
        <button
          type="button"
          class="ec-btn ec-btn-primary"
          :disabled="store.isExecuting"
          @click="runExecution"
        >
          <svg v-if="!store.isExecuting" class="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
            <path d="M8 5v14l11-7z" />
          </svg>
          <svg v-else class="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 4a8 8 0 1 1-8 8" />
          </svg>
          {{ store.isExecuting ? '执行中…' : '执行校验' }}
        </button>
      </template>
    </PageHeader>

    <!-- 主滚动区 -->
    <div class="flex flex-1 flex-col gap-6 overflow-y-auto px-8 py-8">
      <!-- Stepper -->
      <section aria-label="进度" class="rounded-card border border-line bg-card px-6 py-5 shadow-card-1">
        <div class="flex items-center gap-4">
          <!-- 保留原有业务逻辑：步骤进度仍基于 stepperItems 计算结果遍历渲染 -->
          <template v-for="(item, index) in stepperItems" :key="item.step">
            <button
              type="button"
              class="flex appearance-none items-center gap-3 border-0 bg-transparent p-0 text-left shadow-none transition"
              @click="handleStepperClick(item.step)"
            >
              <span
                class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full font-mono text-[12px] font-semibold transition"
                :class="
                  item.step === activeGuideStep
                    ? 'bg-accent text-white'
                    : item.status === 'done'
                      ? 'bg-success text-white'
                      : 'bg-canvas text-ink-500 ring-1 ring-line'
                "
              >
                {{ item.step }}
              </span>
              <div class="min-w-0">
                <div
                  class="text-[14px] font-semibold transition"
                  :class="item.step === activeGuideStep ? 'text-ink-900' : 'text-ink-700'"
                >
                  {{ item.label }}
                </div>
                <div
                  class="text-[12px] truncate max-w-[220px] transition"
                  :class="item.step === activeGuideStep ? 'text-accent-ink' : 'text-ink-500'"
                >
                  {{ item.description }}
                </div>
              </div>
            </button>
            <div
              v-if="index < stepperItems.length - 1"
              class="h-px flex-1 transition"
              :class="item.status === 'done' ? 'bg-accent' : 'bg-line'"
            ></div>
          </template>
        </div>
      </section>

      <!-- KPI 4 列：StatPill；不浮起 -->
      <section aria-label="概览" class="grid grid-cols-4 gap-4">
        <!-- 保留原有业务逻辑：概览卡仍基于 overviewItems 计算结果遍历渲染 -->
        <StatPill
          v-for="item in overviewItems"
          :key="item.label"
          :label="item.label"
          :value="item.value"
          :status-label="item.value > 0 ? item.readyHint : item.pendingHint"
          :status-tone="item.value > 0 ? item.readyTone : item.pendingTone"
        />
      </section>

      <!-- 4 个步骤工作区 -->
      <section ref="sourceStepRef" class="rounded-card border border-line bg-card shadow-card-1">
        <div class="border-t-2 px-5 py-4" :class="activeGuideStep === 1 ? 'border-accent' : 'border-transparent'">
          <div class="flex items-start justify-between gap-4 border-b border-line pb-3">
            <SectionHeader
              variant="workbench"
              step="01"
              title="数据源"
              description="接入 Excel、CSV、飞书或 SVN 来源"
              :status-label="getSectionStatusLabel(1)"
              :status-tone="getSectionStatusTone(1)"
            />
            <div class="workbench-section-toolbar__actions shrink-0">
              <button
                type="button"
                class="ec-btn-outline-compact"
                @click="openDataSourceCreate"
              >
                <svg class="ec-btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 5v14M5 12h14" />
                </svg>
                新增数据源
              </button>
              <button
                type="button"
                class="ec-btn-text-collapse"
                aria-disabled="true"
              >
                收起
                <svg class="ec-btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="m18 15-6-6-6 6" />
                </svg>
              </button>
            </div>
          </div>
          <div class="pt-1">
            <DataSourcePanel ref="dataSourcePanelRef" toolbar-mode="hidden" @saved="handleSourceSaved" />
          </div>
        </div>
      </section>

      <section ref="variableStepRef" class="rounded-card border border-line bg-card shadow-card-1">
        <div class="border-t-2 px-5 py-4" :class="activeGuideStep === 2 ? 'border-accent' : 'border-transparent'">
          <div class="flex items-start justify-between gap-4 border-b border-line pb-3">
            <SectionHeader
              variant="workbench"
              step="02"
              title="变量池"
              description="沉淀后续规则编排会复用的字段与组合变量"
              :status-label="getSectionStatusLabel(2)"
              :status-tone="getSectionStatusTone(2)"
            />
            <div class="workbench-section-toolbar__actions shrink-0">
              <button
                type="button"
                class="ec-btn-outline-compact"
                :disabled="!store.sources.length"
                @click="openSingleVariableCreate"
              >
                添加单个变量
              </button>
              <button
                type="button"
                class="ec-btn-outline-compact"
                :disabled="!store.sources.length"
                @click="openCompositeVariableCreate"
              >
                添加组合变量
              </button>
            </div>
          </div>
          <div class="pt-1">
            <VariablePoolPanel ref="variablePoolPanelRef" toolbar-mode="hidden" @saved="handleVariableSaved" />
          </div>
        </div>
      </section>

      <section ref="ruleStepRef" class="rounded-card border border-line bg-card shadow-card-1">
        <div class="border-t-2 px-5 py-4" :class="activeGuideStep === 3 ? 'border-accent' : 'border-transparent'">
          <div class="flex items-center justify-between gap-4 border-b border-line pb-3">
            <SectionHeader
              variant="workbench"
              step="03"
              title="规则"
              description="按组组织比较、非空、唯一和组合变量规则"
              :status-label="getSectionStatusLabel(3)"
              :status-tone="getSectionStatusTone(3)"
            />
          </div>
          <div class="pt-3">
            <WorkbenchRuleOrchestrationPanel />
            <div class="mt-6 flex justify-end">
              <button
                type="button"
                class="ec-btn ec-btn-primary"
                :disabled="store.isExecuting"
                @click="runExecution"
              >
                <svg class="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M8 5v14l11-7z" />
                </svg>
                执行校验
              </button>
            </div>
          </div>
        </div>
      </section>

      <section ref="resultStepRef" class="rounded-card border border-line bg-card shadow-card-1">
        <div class="border-t-2 px-5 py-4" :class="activeGuideStep === 4 ? 'border-accent' : 'border-transparent'">
          <div class="flex items-start justify-between gap-4 border-b border-line pb-4">
            <SectionHeader
              variant="workbench"
              step="04"
              title="结果"
              description="查看扫描统计、失败来源和异常明细"
              :status-label="getSectionStatusLabel(4)"
              :status-tone="getSectionStatusTone(4)"
            />
          </div>
          <div class="pt-4">
            <ResultBoardPanel :rule-count="store.orchestrationRuleCount" />
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  CircleCheckFilled,
  CollectionTag,
  DataBoard,
  FolderOpened,
  Operation,
  SetUp,
  TrendCharts,
  VideoPlay,
} from '@element-plus/icons-vue'

import DataSourcePanel from '../components/workbench/DataSourcePanel.vue'
import ResultBoardPanel from '../components/workbench/ResultBoardPanel.vue'
import WorkbenchRuleOrchestrationPanel from '../components/workbench/WorkbenchRuleOrchestrationPanel.vue'
import SectionBlock from '../components/workbench/SectionBlock.vue'
import VariablePoolPanel from '../components/workbench/VariablePoolPanel.vue'
import { useWorkbenchStore } from '../store/workbench'

// 保持原有逻辑不变：工作台的数据加载、自动保存、执行与滚动行为全部维持现状。
const store = useWorkbenchStore()

onMounted(async () => {
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

type StepIndex = 1 | 2 | 3 | 4
type SectionStatus = 'pending' | 'active' | 'done'

const overviewItems = computed(() => [
  {
    label: '数据源',
    value: store.sources.length,
    icon: FolderOpened,
    tone: 'brand',
  },
  {
    label: '变量',
    value: store.variables.length,
    icon: CollectionTag,
    tone: 'info',
  },
  {
    label: '规则数',
    value: store.orchestrationRuleCount,
    icon: SetUp,
    tone: 'accent',
  },
  {
    label: '异常结果',
    value: store.abnormalResults.length,
    icon: TrendCharts,
    tone: 'danger',
  },
])

const currentDateLabel = computed(() =>
  new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  }).format(new Date()),
)

const integrationStatus = computed(() => {
  if (store.pageError) {
    return {
      label: '待处理',
      type: 'danger' as const,
      helper: '校验未完成，请先查看结果面板中的报错信息。',
    }
  }

  if (store.capabilities.length) {
    return {
      label: '已连接',
      type: 'success' as const,
      helper: '后端能力已就绪，可直接执行本地校验。',
    }
  }

  return {
    label: '连接中',
    type: 'info' as const,
    helper: '正在读取后端能力信息。',
  }
})

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
    ? `已接入 ${store.sources.length} 个数据源，可以继续沉淀变量。`
    : '先接入至少一个数据源，作为变量与规则配置的基础输入。',
  variable: !store.sources.length
    ? '请先完成数据源接入，再继续配置变量。'
    : store.variables.length
      ? `已沉淀 ${store.variables.length} 个变量，可继续核对字段或进入规则配置。`
      : '建议优先补齐关键字段变量，后续配置规则会更顺手。',
  rule: !store.variables.length
    ? '请先完成变量配置。'
    : store.orchestrationRuleCount
      ? `已配置 ${store.orchestrationRuleCount} 条规则，可继续补充条件或直接执行校验。`
      : '使用规则组与「新增规则」配置比较、非空、唯一或组合变量分支校验。',
  result: !store.orchestrationRuleCount
    ? '请先完成前三步，再在这里查看结果。'
    : store.executionMeta
      ? `最近一次扫描 ${store.executionMeta.total_rows_scanned} 行数据，结果已同步刷新。`
      : store.pageError
        ? '执行失败后，错误与失败来源会集中展示在这里。'
        : '规则准备完成后，可在这里查看扫描统计与异常明细。',
}))

const workflowGuide = computed(() => {
  if (!store.sources.length) {
    return {
      tone: 'info',
      badge: '下一步',
      title: '先接入数据源',
      description: '新增一个本地 Excel 或 CSV 来源，后续变量和规则都会复用它。',
      step: 1 as StepIndex,
      actionLabel: '查看步骤 1',
      action: 'scroll' as const,
    }
  }

  if (!store.variables.length) {
    const preferredSource = store.preferredSourceId ?? store.sources[0]?.id ?? '当前数据源'
    return {
      tone: 'brand',
      badge: '下一步',
      title: `数据源 ${preferredSource} 已就绪`,
      description: '补充 Sheet、字段和变量标签，保存后即可继续配置规则。',
      step: 2 as StepIndex,
      actionLabel: '配置变量',
      action: 'scroll' as const,
    }
  }

  if (!store.orchestrationRuleCount) {
    return {
      tone: 'warning',
      badge: '下一步',
      title: '变量已准备完成',
      description: '在规则组中新增规则后，即可开始首轮校验。',
      step: 3 as StepIndex,
      actionLabel: '配置规则',
      action: 'scroll' as const,
    }
  }

  if (store.isExecuting) {
    return {
      tone: 'info',
      badge: '执行中',
      title: '正在运行校验任务',
      description: '系统正在读取数据并刷新结果，请稍候。',
      step: 4 as StepIndex,
      actionLabel: '查看结果',
      action: 'scroll' as const,
    }
  }

  if (store.pageError) {
    return {
      tone: 'danger',
      badge: '需处理',
      title: '本次执行未完成',
      description: '请先查看结果看板中的错误提示，再决定是否调整数据源或规则。',
      step: 4 as StepIndex,
      actionLabel: '查看结果',
      action: 'scroll' as const,
    }
  }

  if (store.executionMeta) {
    return {
      tone: 'success',
      badge: '已完成',
      title: '校验已完成',
      description: `最近一次扫描 ${store.executionMeta.total_rows_scanned} 行数据，返回 ${store.abnormalResults.length} 条异常记录。`,
      step: 4 as StepIndex,
      actionLabel: '查看结果',
      action: 'scroll' as const,
    }
  }

  return {
    tone: 'brand',
    badge: '可执行',
    title: '可以开始校验',
    description: '当前规则已满足执行条件，可直接发起一次完整校验。',
    step: 4 as StepIndex,
    actionLabel: '开始校验',
    action: 'execute' as const,
  }
})

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
    await store.executeValidation()
    await scrollToStep(4)
    ElMessage.success('校验完成，结果已刷新。')
  } catch {
    await scrollToStep(4)
    // 页面级错误已由 store 托管，这里只保留执行入口。
  }
}

function applyDemoScenario(): void {
  store.applyDemoScenario()
  ElMessage.success('联调样例已加载，可直接执行校验。')
}

async function handleGuideAction(): Promise<void> {
  if (workflowGuide.value.action === 'execute') {
    await runExecution()
    return
  }

  await scrollToStep(workflowGuide.value.step)
}

async function handleSourceSaved(_sourceId: string): Promise<void> {
  await scrollToStep(2)
}

async function handleVariableSaved(_tag: string): Promise<void> {
  await scrollToStep(2)
}
</script>

<template>
  <div class="main-board">
    <header class="workbench-topbar">
      <div class="topbar-brand">
        <div class="brand-icon">
          <DataBoard />
        </div>
        <div class="brand-copy">
          <div class="brand-title-row">
            <strong>配置表校验工作台</strong>
            <el-tag :type="integrationStatus.type" effect="light" round>
              {{ integrationStatus.label }}
            </el-tag>
          </div>
          <p>围绕数据源、变量、规则和结果看板完成一轮本地校验，适合快速联调与日常巡检。</p>
        </div>
      </div>

      <div class="topbar-meta">
        <div class="meta-card">
          <span>日期</span>
          <strong>{{ currentDateLabel }}</strong>
        </div>
        <div class="meta-card">
          <span>运行模式</span>
          <strong>本地开发</strong>
        </div>
        <div class="meta-card">
          <span>当前状态</span>
          <strong>{{ integrationStatus.helper }}</strong>
        </div>
      </div>
    </header>

    <section class="overview-strip">
      <div class="overview-grid">
        <article
          v-for="item in overviewItems"
          :key="item.label"
          class="overview-item"
          :class="`is-${item.tone}`"
        >
          <div class="overview-icon-box" :class="`is-${item.tone}`">
            <component :is="item.icon" class="overview-icon" />
          </div>
          <div>
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </article>
      </div>

      <div class="overview-actions">
        <el-button :icon="Operation" plain @click="applyDemoScenario">加载样例</el-button>
        <el-button v-if="store.pageError" :icon="CircleCheckFilled" plain @click="store.clearPageError()">
          清除错误
        </el-button>
        <el-button
          :icon="VideoPlay"
          type="primary"
          :loading="store.isExecuting"
          @click="runExecution"
        >
          开始校验
        </el-button>
      </div>
    </section>

    <section class="workflow-guide" :class="`is-${workflowGuide.tone}`">
      <div class="guide-copy">
        <span class="guide-badge">{{ workflowGuide.badge }}</span>
        <strong>{{ workflowGuide.title }}</strong>
        <p>{{ workflowGuide.description }}</p>
      </div>
      <div class="guide-actions">
        <el-button :type="workflowGuide.action === 'execute' ? 'primary' : 'default'" @click="handleGuideAction">
          {{ workflowGuide.actionLabel }}
        </el-button>
      </div>
    </section>

    <div ref="sourceStepRef" class="step-anchor">
      <SectionBlock
        step="1"
        title="数据源接入管理"
        description="录入并维护 Excel、CSV、飞书与 SVN 来源，为变量抽取和规则执行提供稳定输入。"
        :status="stepStatuses.source"
        :hint="stepHints.source"
      >
        <DataSourcePanel @saved="handleSourceSaved" />
      </SectionBlock>
    </div>

    <div ref="variableStepRef" class="step-anchor">
      <SectionBlock
        step="2"
        title="变量池构建"
        description="从 source、sheet 与字段中沉淀可复用变量，作为规则编排的统一输入。"
        :status="stepStatuses.variable"
        :hint="stepHints.variable"
      >
        <VariablePoolPanel @saved="handleVariableSaved" />
      </SectionBlock>
    </div>

    <div ref="ruleStepRef" class="step-anchor">
      <SectionBlock
        step="3"
        title="规则编排"
        description="按规则组管理校验规则，与「固定规则检查」页数据相互独立。"
        :status="stepStatuses.rule"
        :hint="stepHints.rule"
      >
        <WorkbenchRuleOrchestrationPanel />

        <div class="section-footbar">
          <el-button
            :icon="VideoPlay"
            type="primary"
            size="large"
            :loading="store.isExecuting"
            @click="runExecution"
          >
            开始校验
          </el-button>
        </div>
      </SectionBlock>
    </div>

    <div ref="resultStepRef" class="step-anchor">
      <SectionBlock
        step="4"
        title="校验结果看板"
        description="集中查看扫描统计、失败来源与异常明细，便于定位问题并快速复查。"
        :status="stepStatuses.result"
        :hint="stepHints.result"
      >
        <ResultBoardPanel />
      </SectionBlock>
    </div>
  </div>
</template>

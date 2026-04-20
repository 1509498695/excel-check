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

const stepGuideItems = computed(() => {
  const recommendedStep = workflowGuide.value.step
  const getToneByStatus = (status: SectionStatus) => {
    if (status === 'done') {
      return 'success' as const
    }
    if (status === 'active') {
      return 'brand' as const
    }
    return 'info' as const
  }
  const getBadgeByStatus = (status: SectionStatus) => {
    if (status === 'done') {
      return '已完成'
    }
    if (status === 'active') {
      return '进行中'
    }
    return '待开始'
  }

  // 保留原有业务逻辑：步骤说明仅复用现有 workflowGuide / stepHints / stepStatuses 计算结果组织展示。
  return [
    {
      step: 1 as StepIndex,
      label: '数据源',
      count: `${store.sources.length} 项`,
      title: recommendedStep === 1 ? workflowGuide.value.title : '先接入数据源',
      description:
        recommendedStep === 1
          ? workflowGuide.value.description
          : '新增一个本地 Excel、CSV、飞书或 SVN 来源，后续变量和规则配置都会复用这里的输入。',
      summary: stepHints.value.source,
      badge: recommendedStep === 1 ? workflowGuide.value.badge : getBadgeByStatus(stepStatuses.value.source),
      tone: recommendedStep === 1 ? workflowGuide.value.tone : getToneByStatus(stepStatuses.value.source),
      status: stepStatuses.value.source,
      action:
        recommendedStep === 1 && workflowGuide.value.action === 'execute'
          ? ('execute' as const)
          : ('scroll' as const),
      actionLabel: recommendedStep === 1 ? workflowGuide.value.actionLabel : '查看步骤 1',
    },
    {
      step: 2 as StepIndex,
      label: '变量池',
      count: `${store.variables.length} 项`,
      title: recommendedStep === 2 ? workflowGuide.value.title : '沉淀变量池',
      description:
        recommendedStep === 2
          ? workflowGuide.value.description
          : '从已接入数据源中补充 Sheet、字段和变量标签，后续规则编排和结果定位都会基于这些变量展开。',
      summary: stepHints.value.variable,
      badge: recommendedStep === 2 ? workflowGuide.value.badge : getBadgeByStatus(stepStatuses.value.variable),
      tone: recommendedStep === 2 ? workflowGuide.value.tone : getToneByStatus(stepStatuses.value.variable),
      status: stepStatuses.value.variable,
      action:
        recommendedStep === 2 && workflowGuide.value.action === 'execute'
          ? ('execute' as const)
          : ('scroll' as const),
      actionLabel: recommendedStep === 2 ? workflowGuide.value.actionLabel : '查看步骤 2',
    },
    {
      step: 3 as StepIndex,
      label: '规则',
      count: `${store.orchestrationRuleCount} 条`,
      title: recommendedStep === 3 ? workflowGuide.value.title : '配置规则',
      description:
        recommendedStep === 3
          ? workflowGuide.value.description
          : '按规则组组织比较、非空、唯一和组合变量分支校验，完成后就可以进入首次完整执行。',
      summary: stepHints.value.rule,
      badge: recommendedStep === 3 ? workflowGuide.value.badge : getBadgeByStatus(stepStatuses.value.rule),
      tone: recommendedStep === 3 ? workflowGuide.value.tone : getToneByStatus(stepStatuses.value.rule),
      status: stepStatuses.value.rule,
      action:
        recommendedStep === 3 && workflowGuide.value.action === 'execute'
          ? ('execute' as const)
          : ('scroll' as const),
      actionLabel: recommendedStep === 3 ? workflowGuide.value.actionLabel : '查看步骤 3',
    },
    {
      step: 4 as StepIndex,
      label: '结果',
      count: `${store.abnormalResults.length} 条`,
      title: recommendedStep === 4 ? workflowGuide.value.title : '查看结果',
      description:
        recommendedStep === 4
          ? workflowGuide.value.description
          : '查看扫描统计、失败来源和异常明细；当规则已就绪但尚未执行时，也可以直接从这里发起一次完整校验。',
      summary: stepHints.value.result,
      badge: recommendedStep === 4 ? workflowGuide.value.badge : getBadgeByStatus(stepStatuses.value.result),
      tone: recommendedStep === 4 ? workflowGuide.value.tone : getToneByStatus(stepStatuses.value.result),
      status: stepStatuses.value.result,
      action:
        recommendedStep === 4 && workflowGuide.value.action === 'execute'
          ? ('execute' as const)
          : ('scroll' as const),
      actionLabel: recommendedStep === 4 ? workflowGuide.value.actionLabel : '查看步骤 4',
    },
  ]
})

const activeGuideStep = computed(() => selectedGuideStep.value ?? workflowGuide.value.step)
const activeGuideDetail = computed(
  () => stepGuideItems.value.find((item) => item.step === activeGuideStep.value) ?? stepGuideItems.value[0],
)

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
    // 页面级错误已由 store 托管，这里只保留执行入口。
  }
}

function applyDemoScenario(): void {
  store.applyDemoScenario()
  ElMessage.success('联调样例已加载，可直接执行校验。')
}

async function handleGuideAction(): Promise<void> {
  if (activeGuideDetail.value.action === 'execute') {
    await runExecution()
    return
  }

  await scrollToStep(activeGuideDetail.value.step)
}

async function handleGuideStepClick(step: StepIndex): Promise<void> {
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
  <div class="main-board workbench-desktop-app">
    <header class="workbench-topbar workbench-toolbar-shell">
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
          <p>固定外壳，专注在右侧内容区完成接入、配置、执行和复查。</p>
        </div>
      </div>

      <div class="workbench-toolbar-tray">
        <div class="topbar-meta workbench-toolbar-meta">
          <div class="meta-card">
            <span>日期</span>
            <strong>{{ currentDateLabel }}</strong>
          </div>
          <div class="meta-card">
            <span>模式</span>
            <strong>本地开发</strong>
          </div>
          <el-tooltip :content="integrationStatus.helper" placement="bottom">
            <div class="meta-card meta-card-compact">
              <span>状态</span>
              <strong>{{ integrationStatus.label }}</strong>
            </div>
          </el-tooltip>
        </div>

        <div class="overview-actions workbench-toolbar-actions">
          <el-tooltip content="载入当前联调样例" placement="bottom">
            <el-button :icon="Operation" plain @click="applyDemoScenario">样例</el-button>
          </el-tooltip>
          <el-button v-if="store.pageError" :icon="CircleCheckFilled" plain @click="store.clearPageError()">
            清错
          </el-button>
          <el-button
            :icon="VideoPlay"
            type="primary"
            :loading="store.isExecuting"
            @click="runExecution"
          >
            执行
          </el-button>
        </div>
      </div>
    </header>

    <div class="workbench-desktop-layout">
      <section class="workbench-stage-content">
        <section class="overview-strip workbench-overview-strip">
          <div class="overview-grid">
            <!-- // 保留原有业务逻辑：概览卡仍基于 overviewItems 计算结果遍历渲染 -->
            <article
              v-for="item in overviewItems"
              :key="item.label"
              class="overview-item"
              :class="`is-${item.tone}`"
            >
              <!-- // 保持 4 列不变，只重排卡片内部层级，避免宽屏下内容挤在左上角 -->
              <div class="overview-item-top">
                <div class="overview-icon-box" :class="`is-${item.tone}`">
                  <component :is="item.icon" class="overview-icon" />
                </div>
                <span class="overview-item-label">{{ item.label }}</span>
              </div>
              <div class="overview-item-value">
                <strong>{{ item.value }}</strong>
              </div>
            </article>
          </div>
        </section>

        <section class="workflow-guide workbench-step-guide-shell" :class="`is-${activeGuideDetail.tone}`">
          <div class="workbench-step-guide-nav">
            <!-- // 保留原有业务逻辑：步骤说明导航仍基于 stepGuideItems 计算结果遍历渲染 -->
            <button
              v-for="item in stepGuideItems"
              :key="item.step"
              type="button"
              class="step-guide-nav-item"
              :class="[
                `is-${item.status}`,
                { 'is-selected': item.step === activeGuideStep },
              ]"
              @click="handleGuideStepClick(item.step)"
            >
              <span class="step-guide-nav-index">步骤 {{ item.step }}</span>
              <strong>{{ item.label }}</strong>
              <small>{{ item.count }}</small>
            </button>
          </div>

          <!-- // 单列瀑布：标题/描述置顶，下方水平摆放 meta 与 CTA，避免左右分列打断阅读动线 -->
          <div class="workbench-step-guide-detail">
            <div class="workbench-step-guide-copy">
              <span class="guide-badge">{{ activeGuideDetail.badge }}</span>
              <strong>{{ activeGuideDetail.title }}</strong>
              <p>{{ activeGuideDetail.description }}</p>
            </div>

            <!-- // 步骤说明 + 状态标签靠左，主 CTA 吸附到当前行右端 -->
            <div class="workbench-step-guide-context">
              <div class="workbench-step-guide-meta">
                <div class="step-guide-summary-card">
                  <span>当前说明</span>
                  <strong>{{ activeGuideDetail.summary }}</strong>
                </div>
                <div class="step-guide-detail-tags">
                  <el-tag type="info" effect="light" round>{{ activeGuideDetail.label }}</el-tag>
                  <el-tag v-if="activeGuideDetail.status === 'done'" type="success" effect="light" round>
                    已就绪
                  </el-tag>
                  <el-tag v-else-if="activeGuideDetail.status === 'active'" type="warning" effect="light" round>
                    当前重点
                  </el-tag>
                  <el-tag v-else type="info" effect="light" round>
                    待继续
                  </el-tag>
                </div>
              </div>

              <div class="guide-actions workbench-step-guide-actions">
                <el-button
                  :type="activeGuideDetail.action === 'execute' ? 'primary' : 'default'"
                  @click="handleGuideAction"
                >
                  {{ activeGuideDetail.actionLabel }}
                </el-button>
              </div>
            </div>
          </div>
        </section>

        <div ref="sourceStepRef" class="step-anchor">
          <SectionBlock
            step="1"
            title="数据源"
            description="接入 Excel、CSV、飞书或 SVN 来源。"
            :status="stepStatuses.source"
            :hint="stepHints.source"
          >
            <DataSourcePanel @saved="handleSourceSaved" />
          </SectionBlock>
        </div>

        <div ref="variableStepRef" class="step-anchor">
          <SectionBlock
            step="2"
            title="变量池"
            description="沉淀后续规则编排会复用的字段与组合变量。"
            :status="stepStatuses.variable"
            :hint="stepHints.variable"
          >
            <VariablePoolPanel @saved="handleVariableSaved" />
          </SectionBlock>
        </div>

        <div ref="ruleStepRef" class="step-anchor">
          <SectionBlock
            step="3"
            title="规则"
            description="按组组织比较、非空、唯一和组合变量规则。"
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
            title="结果"
            description="查看扫描统计、失败来源和异常明细。"
            :status="stepStatuses.result"
            :hint="stepHints.result"
          >
            <ResultBoardPanel />
          </SectionBlock>
        </div>
      </section>
    </div>
  </div>
</template>

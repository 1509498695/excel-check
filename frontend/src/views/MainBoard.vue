<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  CircleCheckFilled,
  Connection,
  DataAnalysis,
  Files,
  Lightning,
  MagicStick,
  VideoPlay,
} from '@element-plus/icons-vue'

import DataSourcePanel from '../components/workbench/DataSourcePanel.vue'
import ResultBoardPanel from '../components/workbench/ResultBoardPanel.vue'
import RuleComposerPanel from '../components/workbench/RuleComposerPanel.vue'
import SectionBlock from '../components/workbench/SectionBlock.vue'
import VariablePoolPanel from '../components/workbench/VariablePoolPanel.vue'
import { useWorkbenchStore } from '../store/workbench'

const store = useWorkbenchStore()
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
    icon: Connection,
  },
  {
    label: '变量标签',
    value: store.variables.length,
    icon: Files,
  },
  {
    label: '规则数',
    value: store.rules.length,
    icon: MagicStick,
  },
  {
    label: '异常结果',
    value: store.abnormalResults.length,
    icon: DataAnalysis,
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
      helper: '执行结果出现错误，请查看结果看板。',
    }
  }

  if (store.capabilities.length) {
    return {
      label: '联调正常',
      type: 'success' as const,
      helper: '前后端代理已连接，可直接执行本地校验。',
    }
  }

  return {
    label: '检测中',
    type: 'info' as const,
    helper: '正在读取后端能力声明。',
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
  rule: !store.variables.length ? 'pending' : store.rules.length ? 'done' : 'active',
  result: !store.rules.length ? 'pending' : store.executionMeta || store.pageError ? 'done' : 'active',
}))

const stepHints = computed(() => ({
  source: store.sources.length
    ? `已录入 ${store.sources.length} 个数据源，可继续配置变量池。`
    : '先录入至少一个数据源，浏览器会把本地文件桥接成后端可读路径。',
  variable: !store.sources.length
    ? '需要先完成步骤 1，才能继续添加变量。'
    : store.variables.length
      ? `当前已配置 ${store.variables.length} 个变量标签，可继续查看变量详情或进入步骤 3 编排规则。`
      : '建议优先通过来源数据、Sheet 和列名的逐级选择补充关键变量。',
  rule: !store.variables.length
    ? '请先完成变量池配置。'
    : store.rules.length
      ? `当前已创建 ${store.rules.length} 条规则，可继续补参数或直接执行校验。`
      : '优先从 not_null、unique、cross_table_mapping 三条模板规则开始，最快形成完整闭环。',
  result: !store.rules.length
    ? '请先完成前面 3 个步骤，再在这里查看结果。'
    : store.executionMeta
      ? `最近一次执行扫描 ${store.executionMeta.total_rows_scanned} 行数据，结果面板已同步刷新。`
      : store.pageError
        ? '执行失败后，错误提示和失败数据源会集中展示在这里。'
        : '规则准备完成后，点击“立即执行校验”即可在这里查看扫描统计和异常明细。',
}))

const workflowGuide = computed(() => {
  if (!store.sources.length) {
    return {
      tone: 'info',
      badge: '推荐下一步',
      title: '先完成数据源接入',
      description: '新增一个本地 Excel / CSV 数据源后，系统会把它自动设为后续变量配置的默认来源。',
      step: 1 as StepIndex,
      actionLabel: '查看步骤 1',
      action: 'scroll' as const,
    }
  }

  if (!store.variables.length) {
    const preferredSource = store.preferredSourceId ?? store.sources[0]?.id ?? '当前数据源'
    return {
      tone: 'brand',
      badge: '流程推进',
      title: `数据源 ${preferredSource} 已就绪`,
      description: '下一步建议补充 sheet、column 和变量标签。变量保存后会自动高亮并跳转到规则编排区。',
      step: 2 as StepIndex,
      actionLabel: '去添加变量',
      action: 'scroll' as const,
    }
  }

  if (!store.rules.length) {
    return {
      tone: 'warning',
      badge: '流程推进',
      title: '变量池已经准备就绪',
      description: '优先添加静态规则模板，先跑通 not_null、unique 和 cross_table_mapping 的最小闭环。',
      step: 3 as StepIndex,
      actionLabel: '去编排规则',
      action: 'scroll' as const,
    }
  }

  if (store.isExecuting) {
    return {
      tone: 'info',
      badge: '执行中',
      title: '校验任务正在运行',
      description: '系统正在读取数据源、执行规则并刷新结果看板，请稍候。',
      step: 4 as StepIndex,
      actionLabel: '查看结果',
      action: 'scroll' as const,
    }
  }

  if (store.pageError) {
    return {
      tone: 'danger',
      badge: '待处理',
      title: '执行过程中出现错误',
      description: '错误详情已经同步到结果看板，建议先查看步骤 4 的提示，再决定是否调整数据源或规则。',
      step: 4 as StepIndex,
      actionLabel: '查看结果',
      action: 'scroll' as const,
    }
  }

  if (store.executionMeta) {
    return {
      tone: 'success',
      badge: '已完成',
      title: '本地完整校验流程已跑通',
      description: `最近一次执行扫描 ${store.executionMeta.total_rows_scanned} 行数据，返回 ${store.abnormalResults.length} 条异常记录。`,
      step: 4 as StepIndex,
      actionLabel: '查看结果',
      action: 'scroll' as const,
    }
  }

  return {
    tone: 'brand',
    badge: '可执行',
    title: '规则已具备执行条件',
    description: '现在可以直接发起一次完整校验，结果会自动刷新到步骤 4 的结果看板。',
    step: 4 as StepIndex,
    actionLabel: '立即执行校验',
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
    ElMessage.success('校验已执行完成，结果看板已刷新。')
  } catch {
    await scrollToStep(4)
    // 页面级错误已由 store 托管，这里只保留执行入口，不重复覆盖提示。
  }
}

function applyDemoScenario(): void {
  store.applyDemoScenario()
  ElMessage.success('联调用示例已填充，现在可以直接执行校验。')
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
          <Connection />
        </div>
        <div class="brand-copy">
          <div class="brand-title-row">
            <strong>配置表动态规则校验工作台</strong>
            <el-tag :type="integrationStatus.type" effect="light" round>
              {{ integrationStatus.label }}
            </el-tag>
          </div>
          <p>
            围绕数据源、变量池、规则编排和结果看板完成一次完整本地校验流程，保持企业工作台排版的清晰度，也方便持续扩展飞书、SVN
            和更多规则类型。
          </p>
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
        <article v-for="item in overviewItems" :key="item.label" class="overview-item">
          <div class="overview-icon-box">
            <component :is="item.icon" class="overview-icon" />
          </div>
          <div>
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </article>
      </div>

      <div class="overview-actions">
        <el-button :icon="Lightning" plain @click="applyDemoScenario">填充联调用示例</el-button>
        <el-button v-if="store.pageError" :icon="CircleCheckFilled" plain @click="store.clearPageError()">
          清空错误提示
        </el-button>
        <el-button
          :icon="VideoPlay"
          type="primary"
          :loading="store.isExecuting"
          @click="runExecution"
        >
          立即执行校验
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
        description="统一维护本地 Excel、CSV、飞书和 SVN 入口，为变量抽取和规则执行提供稳定来源。"
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
        description="通过 source、sheet 和列名提取业务字段，把后端可读取的列整理为规则可复用的变量标签。"
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
        description="静态规则负责高频校验，动态规则保留后续扩展入口，让工作台既稳定又具备生长空间。"
        :status="stepStatuses.rule"
        :hint="stepHints.rule"
      >
        <RuleComposerPanel />

        <div class="section-footbar">
          <el-button
            :icon="VideoPlay"
            type="primary"
            size="large"
            :loading="store.isExecuting"
            @click="runExecution"
          >
            立即执行校验
          </el-button>
        </div>
      </SectionBlock>
    </div>

    <div ref="resultStepRef" class="step-anchor">
      <SectionBlock
        step="4"
        title="校验结果看板"
        description="集中展示扫描统计、失败数据源和异常明细，为联调定位、结果导出和后续修复提供依据。"
        :status="stepStatuses.result"
        :hint="stepHints.result"
      >
        <ResultBoardPanel />
      </SectionBlock>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import DataTable from '../shell/DataTable.vue'
import EmptyState from '../shell/EmptyState.vue'
import MetricCard from '../shell/MetricCard.vue'
import SecondaryButton from '../shell/SecondaryButton.vue'
import { useWorkbenchStore } from '../../store/workbench'
import type { AbnormalResult, ExecutionMeta } from '../../types/workbench'
import { getRuleTitle } from '../../utils/workbenchMeta'

type ResultBoardStoreLike = {
  pageError: string
  isExecuting: boolean
  isResultPageLoading: boolean
  executionMeta: ExecutionMeta | null
  abnormalResults: AbnormalResult[]
  abnormalResultTotal: number
  resultId: number | null
  resultCurrentPage: number
  resultPageSize: number
  resultPageCount: number
  isResultExporting: boolean
  loadResultPage: (page: number) => Promise<void>
  exportResults: () => Promise<void>
}

const props = withDefaults(
  defineProps<{
    store?: ResultBoardStoreLike
    ruleCount: number
    variant?: 'default' | 'personal'
  }>(),
  {
    variant: 'default',
  },
)

const defaultStore = useWorkbenchStore()
const store = computed<ResultBoardStoreLike>(() => props.store ?? defaultStore)

const resultStats = computed(() => {
  const total = store.value.abnormalResultTotal
  const scanned = store.value.executionMeta?.total_rows_scanned ?? 0
  const failedSources = store.value.executionMeta?.failed_sources.length ?? 0
  const durationMs = store.value.executionMeta?.execution_time_ms ?? 0

  return {
    total,
    scanned,
    failedSources,
    durationMs,
  }
})

const shouldShowPagination = computed(
  () => !!store.value.executionMeta && store.value.abnormalResultTotal > store.value.resultPageSize,
)

const canExportResults = computed(
  () => !!store.value.executionMeta?.result_id && !store.value.isExecuting && !store.value.isResultExporting,
)

const shouldShowPersonalReadyState = computed(
  () => props.variant === 'personal' && !store.value.executionMeta && !store.value.isExecuting,
)

const summaryCards = computed(() => [
  { label: '扫描总行数', value: resultStats.value.scanned, statusLabel: '已统计', statusType: 'success' as const, iconTone: 'primary' as const },
  { label: '失败数据源', value: resultStats.value.failedSources, statusLabel: resultStats.value.failedSources ? '需关注' : '正常', statusType: resultStats.value.failedSources ? 'warning' as const : 'success' as const, iconTone: 'warning' as const },
  { label: '异常结果', value: resultStats.value.total, statusLabel: resultStats.value.total ? '需处理' : '正常', statusType: resultStats.value.total ? 'warning' as const : 'success' as const, iconTone: 'danger' as const },
  { label: '执行耗时', value: `${resultStats.value.durationMs}ms`, statusLabel: '已完成', statusType: 'neutral' as const, iconTone: 'purple' as const },
])

function getLevelType(level: string): 'danger' | 'warning' | 'success' | 'info' {
  if (level === 'error') {
    return 'danger'
  }
  if (level === 'warning') {
    return 'warning'
  }
  if (level === 'success') {
    return 'success'
  }
  return 'info'
}

function displayRawValue(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '空值'
  }

  if (typeof value === 'object') {
    return JSON.stringify(value)
  }

  return String(value)
}

function handlePageChange(page: number): void {
  void store.value.loadResultPage(page)
}

function handleExportResults(): void {
  void store.value.exportResults()
}
</script>

<template>
  <div class="result-board-panel flex flex-col gap-5" :class="variant === 'personal' ? 'result-board-panel--personal' : ''">
    <div
      v-if="store.pageError"
      role="alert"
      class="rounded-card border border-line border-l-4 border-l-danger bg-danger-soft/50 px-4 py-3 text-[13px] text-ink-700"
    >
      {{ store.pageError }}
    </div>

    <div
      v-if="store.executionMeta?.failed_sources.length"
      role="alert"
      class="rounded-card border border-line border-l-4 border-l-warning bg-warning-soft/40 px-4 py-3 text-[13px] text-ink-700"
    >
      失败数据源：{{ store.executionMeta.failed_sources.join('、') }}
    </div>

    <div
      v-if="shouldShowPersonalReadyState"
      class="personal-result-empty"
    >
      <EmptyState
        variant="result"
        icon-tone="result"
        title="结果面板已就绪"
        description="先完成数据源、变量池和规则配置，再执行一次校验"
        :min-height="180"
      />
    </div>

    <div
      v-if="!ruleCount"
      v-show="!shouldShowPersonalReadyState"
      class="personal-result-empty"
    >
      <EmptyState
        variant="result"
        icon-tone="result"
        title="结果面板已就绪"
        description="先完成数据源、变量池和规则配置，再执行一次校验"
        :min-height="180"
      />
    </div>

    <template v-else-if="!shouldShowPersonalReadyState">
      <div class="grid grid-cols-4 gap-4">
        <MetricCard
          v-for="card in summaryCards"
          :key="card.label"
          :label="card.label"
          :value="card.value"
          :status-label="card.statusLabel"
          :status-type="card.statusType"
          :icon-tone="card.iconTone"
        />
      </div>

      <slot name="extra" />

      <div
        v-if="store.executionMeta"
        class="flex items-center justify-between gap-4 rounded-card border border-line bg-card px-4 py-3"
      >
        <div>
          <div class="text-[14px] font-semibold text-ink-900">结果导出</div>
          <div class="mt-1 text-[12px] text-ink-500">
            导出当前执行结果的统计摘要与全部异常明细，不受分页影响。
          </div>
        </div>
        <SecondaryButton
          size="sm"
          :disabled="!canExportResults"
          :loading="store.isResultExporting"
          @click="handleExportResults"
        >
          导出 Excel
        </SecondaryButton>
      </div>

      <div
        v-loading="store.isResultPageLoading"
        element-loading-text="正在加载结果页"
        class="flex flex-col gap-4"
      >
        <DataTable aria-label="执行结果表">
        <template #head>
          <tr>
            <th class="w-[18%]">命中规则</th>
            <th class="w-[20%]">定位</th>
            <th class="w-[80px]">行号</th>
            <th class="w-[120px]">原始值</th>
            <th class="w-[120px]">级别</th>
            <th>说明</th>
          </tr>
        </template>
        <template #body>
          <tr v-if="store.isExecuting">
            <td colspan="6" class="bg-card">
              <EmptyState
                variant="table"
                icon-tone="result"
                title="正在执行校验"
                description="结果刷新中，请稍候。"
                :min-height="160"
              >
                <template #icon>
                  <svg class="h-4 w-4 animate-spin text-ink-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 4a8 8 0 1 1-8 8" />
                  </svg>
                </template>
              </EmptyState>
            </td>
          </tr>
          <tr v-else-if="!store.executionMeta">
            <td colspan="6" class="bg-card">
              <EmptyState
                variant="table"
                icon-tone="result"
                title="结果面板已就绪"
                description="先完成数据源、变量池和规则配置，再执行一次校验"
                :min-height="180"
              />
            </td>
          </tr>
          <tr v-else-if="!store.abnormalResultTotal">
            <td colspan="6" class="bg-card">
              <EmptyState
                variant="table"
                icon-tone="result"
                title="本轮未发现异常结果"
                description="扫描统计已完成，当前没有命中异常数据。"
                :min-height="180"
              />
            </td>
          </tr>
          <template v-else>
            <tr
              v-for="row in store.abnormalResults"
              :key="`${row.rule_name}-${row.location}-${row.row_index}-${String(row.raw_value)}`"
              class="bg-card text-ink-700"
            >
              <td class="align-top font-medium text-ink-900">
                {{ getRuleTitle(row.rule_name) }}
              </td>
              <td class="align-top font-mono text-[12px] text-ink-700">
                {{ row.location }}
              </td>
              <td class="align-top font-mono text-[12px] text-ink-700">
                {{ row.row_index }}
              </td>
              <td class="align-top font-mono text-[12px] text-ink-700">
                {{ displayRawValue(row.raw_value) }}
              </td>
              <td class="align-top">
                <el-tag :type="getLevelType(row.level)" effect="light" round>
                  {{ row.level }}
                </el-tag>
              </td>
              <td class="align-top text-[13px] text-ink-700">
                {{ row.message }}
              </td>
            </tr>
          </template>
        </template>
        </DataTable>

        <div
          v-if="store.executionMeta"
          class="flex items-center justify-between gap-4"
        >
          <div class="text-[13px] text-ink-500">
            共 {{ store.abnormalResultTotal }} 条异常
          </div>
          <el-pagination
            v-if="shouldShowPagination"
            background
            layout="prev, pager, next"
            :current-page="store.resultCurrentPage"
            :page-size="store.resultPageSize"
            :total="store.abnormalResultTotal"
            @current-change="handlePageChange"
          />
        </div>
      </div>
    </template>
  </div>
</template>

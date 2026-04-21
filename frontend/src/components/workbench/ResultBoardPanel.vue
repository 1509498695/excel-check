<script setup lang="ts">
import { computed } from 'vue'

import DataTable from '../shell/DataTable.vue'
import EmptyState from '../shell/EmptyState.vue'
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
  resultCurrentPage: number
  resultPageSize: number
  resultPageCount: number
  loadResultPage: (page: number) => Promise<void>
}

const props = defineProps<{
  store?: ResultBoardStoreLike
  ruleCount: number
}>()

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

const summaryCards = computed(() => [
  { label: '扫描总行数', value: resultStats.value.scanned },
  { label: '失败数据源', value: resultStats.value.failedSources },
  { label: '异常结果', value: resultStats.value.total },
  { label: '执行耗时', value: `${resultStats.value.durationMs}ms` },
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
</script>

<template>
  <div class="flex flex-col gap-5">
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
      v-if="!ruleCount"
      class="rounded-card border border-dashed border-line bg-subtle/60 px-6 py-10 text-center"
    >
      <div class="text-[15px] font-semibold text-ink-900">结果面板已就绪</div>
      <p class="mt-2 text-[13px] text-ink-500">先完成数据源、变量池和规则配置，再执行一次校验。</p>
    </div>

    <template v-else>
      <div class="grid grid-cols-4 gap-4">
        <article
          v-for="card in summaryCards"
          :key="card.label"
          class="rounded-field bg-subtle px-5 py-4"
        >
          <div class="text-[12px] font-medium text-ink-500">{{ card.label }}</div>
          <div class="mt-3 font-mono text-[16px] font-semibold leading-none text-ink-900">
            {{ card.value }}
          </div>
        </article>
      </div>

      <slot name="extra" />

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
              <EmptyState title="正在执行校验" description="结果刷新中，请稍候。">
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
              <EmptyState title="等待执行结果" description="执行完成后，异常结果会在这里展示。" />
            </td>
          </tr>
          <tr v-else-if="!store.abnormalResultTotal">
            <td colspan="6" class="bg-card">
              <EmptyState title="本轮未发现异常结果" description="扫描统计已完成，当前没有命中异常数据。">
                <template #icon>
                  <svg class="h-4 w-4 text-ink-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M5 13l4 4L19 7" />
                  </svg>
                </template>
              </EmptyState>
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

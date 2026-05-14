<script setup lang="ts">
import { computed, ref } from 'vue'
import { Delete, MagicStick, Refresh, Setting } from '@element-plus/icons-vue'

import PrimaryButton from '../shell/PrimaryButton.vue'
import SecondaryButton from '../shell/SecondaryButton.vue'
import type { VariableTag } from '../../types/workbench'

const props = defineProps<{
  description: string
  selectedVariableTags: string[]
  allowAutoComplete: boolean
  variables: VariableTag[]
  providerLabel: string
  isConfigured: boolean
  isGenerating: boolean
  isOptimizing: boolean
  canGenerate: boolean
  maxLength: number
  promptText: string
}>()

const emit = defineEmits<{
  (e: 'update:description', value: string): void
  (e: 'update:selectedVariableTags', value: string[]): void
  (e: 'update:allowAutoComplete', value: boolean): void
  (e: 'optimize'): void
  (e: 'generate'): void
  (e: 'clear'): void
  (e: 'refresh-history'): void
  (e: 'model-config'): void
  (e: 'load-example'): void
  (e: 'copy-prompt'): void
}>()

const showPrompt = ref(false)

const descriptionCount = computed(() => props.description.length)
const placeholder = `推荐格式：
筛选DESC3=升级p1建筑到p2级p4次,完成p2等级的p1科研，两种类型。STR_ABSwitch字段=GreenServer:0 or SLG2:0。

也可以写：目标字段不能为空 / 字段不能重复 / 字段只能是 A,B,C / 按 Key 对比两组配置是否相等。`

const variableOptions = computed(() =>
  props.variables.map((variable) => ({
    value: variable.tag,
    label: variable.tag,
    detail: buildVariableDetail(variable),
  })),
)

function updateDescription(value: string): void {
  emit('update:description', value)
}

function updateAllowAutoComplete(value: string | number | boolean): void {
  emit('update:allowAutoComplete', Boolean(value))
}

function buildVariableDetail(variable: VariableTag): string {
  const sheet = variable.sheet ? `${variable.sheet} / ` : ''
  if ((variable.variable_kind ?? 'single') === 'composite') {
    const columns = (variable.columns ?? []).map((item) => item.trim()).filter(Boolean).join(', ')
    return `组合 ${sheet}${columns || '未配置列'}`
  }
  return `${sheet}${variable.column || '未配置字段'}`
}
</script>

<template>
  <section class="smart-rule-card smart-rule-input-card">
    <div class="smart-rule-card__header">
      <div class="min-w-0">
        <h3>智能添加规则</h3>
        <div class="smart-rule-connection" :class="{ 'is-muted': !isConfigured }">
          <span class="smart-rule-connection__dot"></span>
          <span>连接状态</span>
          <span class="smart-rule-connection__model">{{ providerLabel }}</span>
        </div>
      </div>
      <div class="smart-rule-card__actions">
        <SecondaryButton size="sm" @click="emit('load-example')">载入案例</SecondaryButton>
        <SecondaryButton size="sm" @click="showPrompt = !showPrompt">
          {{ showPrompt ? '收起提示词' : '通用提示词' }}
        </SecondaryButton>
        <SecondaryButton size="sm" @click="emit('model-config')">
          <template #icon><Setting /></template>
          模型配置
        </SecondaryButton>
      </div>
    </div>

    <div v-if="!isConfigured" class="smart-rule-warning">
      当前账号还没有 AI 模型配置，请先进入个人设置完成 API Key 和模型配置。
      <button type="button" class="ec-action-link" @click="emit('model-config')">前往配置</button>
    </div>

    <div class="smart-rule-target-select">
      <div class="smart-rule-target-select__label">
        <span>目标变量</span>
        <small>
          {{
            allowAutoComplete
              ? '可不选择目标变量，AI 会根据描述和元数据尝试补齐'
              : '只使用这里选择的变量池变量'
          }}
        </small>
      </div>
      <div class="smart-rule-auto-complete-toggle">
        <span>允许 AI 自动补齐数据源/变量</span>
        <el-switch
          :model-value="allowAutoComplete"
          size="small"
          @update:model-value="updateAllowAutoComplete"
        />
      </div>
      <el-select
        :model-value="selectedVariableTags"
        multiple
        filterable
        clearable
        collapse-tags
        collapse-tags-tooltip
        :placeholder="allowAutoComplete ? '可选：优先使用的变量池变量' : '请选择一个或多个变量池变量'"
        @update:model-value="(value: string[]) => emit('update:selectedVariableTags', value)"
      >
        <el-option
          v-for="option in variableOptions"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        >
          <div class="smart-rule-variable-option">
            <span class="smart-rule-variable-option__tag">{{ option.label }}</span>
            <span class="smart-rule-variable-option__detail">{{ option.detail }}</span>
          </div>
        </el-option>
      </el-select>
    </div>

    <div v-if="showPrompt" class="smart-rule-prompt">
      <div class="smart-rule-prompt__head">
        <span>固定工作流通用提示词</span>
        <button type="button" class="ec-action-link" @click="emit('copy-prompt')">复制</button>
      </div>
      <pre>{{ promptText }}</pre>
    </div>

    <div class="smart-rule-textarea-wrap">
      <el-input
        :model-value="description"
        type="textarea"
        :rows="6"
        resize="vertical"
        :maxlength="maxLength"
        :placeholder="placeholder"
        @update:model-value="updateDescription"
      />
      <div class="smart-rule-counter">{{ descriptionCount }} / {{ maxLength }}</div>
    </div>

    <div class="smart-rule-input-actions">
      <SecondaryButton
        :disabled="isGenerating || isOptimizing"
        :loading="isOptimizing"
        title="将当前规则描述优化为更清晰的结构化表达，提高 AI 校验成功率。"
        @click="emit('optimize')"
      >
        <template #icon><MagicStick /></template>
        {{ isOptimizing ? '优化中...' : '优化输入' }}
      </SecondaryButton>
      <PrimaryButton :disabled="!canGenerate || isGenerating" :loading="isGenerating" @click="emit('generate')">
        <template #icon><MagicStick /></template>
        {{ isGenerating ? 'AI 校验中…' : 'AI 校验' }}
      </PrimaryButton>
      <SecondaryButton :disabled="isGenerating" @click="emit('clear')">
        <template #icon><Delete /></template>
        清空输入
      </SecondaryButton>
      <SecondaryButton :disabled="isGenerating" @click="emit('refresh-history')">
        <template #icon><Refresh /></template>
        刷新历史
      </SecondaryButton>
    </div>
  </section>
</template>

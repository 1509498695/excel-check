<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'

import { useWorkbenchStore } from '../../store/workbench'
import type { ValidationRule } from '../../types/workbench'
import {
  getRuleLevelTone,
  getRuleTitle,
  STATIC_RULE_TEMPLATES,
} from '../../utils/workbenchMeta'

const store = useWorkbenchStore()
const dynamicParamsPlaceholder = '{\n  "target_tags": ["[items-id]"]\n}'

const variableOptions = computed(() =>
  store.singleVariables.map((variable) => ({
    label: `${variable.tag} · ${variable.sheet}/${variable.column ?? ''}`,
    value: variable.tag,
  })),
)

function addStaticRule(ruleType: string): void {
  store.addStaticRule(ruleType)
  ElMessage.success('静态规则已加入编排区。')
}

function addDynamicRule(): void {
  store.addDynamicRule()
  ElMessage.success('动态规则编辑器已创建。')
}

function removeRule(ruleId?: string): void {
  store.removeRule(ruleId)
  ElMessage.success('规则已移除。')
}

function getTargetTags(rule: ValidationRule): string[] {
  return Array.isArray(rule.params.target_tags)
    ? rule.params.target_tags.filter((item): item is string => typeof item === 'string')
    : []
}

function updateTargetTags(rule: ValidationRule, values: string[]): void {
  store.updateRuleParams(rule.rule_id ?? '', {
    target_tags: values,
  })
}

function getCrossValue(rule: ValidationRule, key: 'dict_tag' | 'target_tag'): string {
  return typeof rule.params[key] === 'string' ? rule.params[key] : ''
}

function updateCrossValue(rule: ValidationRule, key: 'dict_tag' | 'target_tag', value: string): void {
  store.updateRuleParams(rule.rule_id ?? '', {
    ...rule.params,
    [key]: value,
  })
}

function getDynamicParamsText(rule: ValidationRule): string {
  if (rule.draftState?.paramsText) {
    return rule.draftState.paramsText
  }

  return JSON.stringify(rule.params, null, 2)
}

function updateDynamicParamsText(rule: ValidationRule, value: string): void {
  store.updateRuleDraftText(rule.rule_id ?? '', value)
}

function getDynamicError(rule: ValidationRule): string {
  const ruleType = rule.rule_type.trim()
  if (!ruleType) {
    return '请先填写动态 rule_type。'
  }

  const raw = getDynamicParamsText(rule).trim()
  if (!raw) {
    return ''
  }

  try {
    const parsed = JSON.parse(raw) as unknown
    if (parsed === null || Array.isArray(parsed) || typeof parsed !== 'object') {
      return 'params 必须是 JSON 对象。'
    }
    return ''
  } catch (error) {
    return error instanceof Error ? error.message : 'JSON 解析失败。'
  }
}

function isRuleReady(rule: ValidationRule): boolean {
  if (rule.mode === 'dynamic') {
    return rule.rule_type.trim().length > 0 && !getDynamicError(rule)
  }

  if (rule.rule_type === 'not_null' || rule.rule_type === 'unique') {
    return getTargetTags(rule).length > 0
  }

  if (rule.rule_type === 'cross_table_mapping') {
    return Boolean(getCrossValue(rule, 'dict_tag') && getCrossValue(rule, 'target_tag'))
  }

  return true
}

const readyRuleCount = computed(() => store.rules.filter(isRuleReady).length)
const pendingRuleCount = computed(() => store.rules.length - readyRuleCount.value)

const ruleGuide = computed(() => {
  if (!store.singleVariables.length) {
    const onlyComposite = store.variables.length > 0
    return {
      type: 'warning' as const,
      title: onlyComposite ? '当前只有组合变量，静态规则暂不可用' : '请先完成步骤 2 的单变量配置',
      description: onlyComposite
        ? '组合变量已可用于后续 JSON 类扩展，但当前 not_null、unique、cross_table_mapping 仍需至少一个单个变量。'
        : '至少准备一个单个变量标签后，再开始添加静态规则或动态规则，能明显减少无效配置。',
    }
  }

  if (!store.rules.length) {
    return {
      type: 'info' as const,
      title: '规则编排区还没有内容',
      description:
        '建议先从 not_null、unique、cross_table_mapping 这三条静态规则模板开始，最快形成完整闭环。',
    }
  }

  if (pendingRuleCount.value > 0) {
    return {
      type: 'warning' as const,
      title: `还有 ${pendingRuleCount.value} 条规则待完善`,
      description: '补齐目标变量、字典变量或动态规则 JSON 后，就可以直接执行完整校验。',
    }
  }

  return {
    type: 'success' as const,
    title: '规则已具备执行条件',
    description: `当前共 ${store.rules.length} 条规则，已经可以直接执行一次完整校验。`,
  }
})
</script>

<template>
  <div class="rule-layout">
    <div class="rule-template-panel">
      <div class="panel-toolbar">
        <div class="toolbar-copy">
          <strong>静态规则模板</strong>
          <span>优先使用已落地的后端规则，快速完成常见校验配置。</span>
        </div>
      </div>

      <el-alert
        :title="ruleGuide.title"
        :description="ruleGuide.description"
        :type="ruleGuide.type"
        :closable="false"
        show-icon
      />

      <div class="template-grid">
        <button
          v-for="template in STATIC_RULE_TEMPLATES"
          :key="template.ruleType"
          type="button"
          class="template-tile"
          @click="addStaticRule(template.ruleType)"
        >
          <div class="tile-topline">
            <el-tag :type="getRuleLevelTone(template.ruleType)" effect="light" round>
              {{ template.level }}
            </el-tag>
            <span>点击添加</span>
          </div>
          <strong>{{ template.title }}</strong>
          <p>{{ template.description }}</p>
        </button>
      </div>

      <div class="rule-group">
        <div class="group-heading">
          <div>
            <h3>静态规则配置区</h3>
            <p>模板规则会自动生成后端所需的标准参数结构，当前已就绪 {{ readyRuleCount }} 条。</p>
          </div>
        </div>

        <div v-if="!store.staticRules.length" class="empty-rule-state">
          还没有静态规则，请先从上方模板中选择一条。
        </div>

        <article v-for="rule in store.staticRules" :key="rule.rule_id" class="rule-card">
          <div class="rule-card-head">
            <div>
              <div class="rule-title-line">
                <h4>{{ getRuleTitle(rule.rule_type) }}</h4>
                <el-tag :type="getRuleLevelTone(rule.rule_type)" effect="plain" round>
                  {{ rule.rule_type }}
                </el-tag>
              </div>
              <p>规则 ID：{{ rule.rule_id }}</p>
            </div>
            <el-button link type="danger" @click="removeRule(rule.rule_id)">移除</el-button>
          </div>

          <div v-if="rule.rule_type === 'not_null' || rule.rule_type === 'unique'" class="rule-fields">
            <label>目标变量</label>
            <el-select
              :model-value="getTargetTags(rule)"
              multiple
              filterable
              collapse-tags
              collapse-tags-tooltip
              class="full-width"
              placeholder="选择一个或多个单变量标签"
              @update:model-value="updateTargetTags(rule, $event)"
            >
              <el-option
                v-for="option in variableOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </div>

          <div v-else-if="rule.rule_type === 'cross_table_mapping'" class="rule-grid">
            <div class="rule-fields">
              <label>字典变量</label>
              <el-select
                :model-value="getCrossValue(rule, 'dict_tag')"
                filterable
                class="full-width"
                placeholder="选择字典列"
                @update:model-value="updateCrossValue(rule, 'dict_tag', $event)"
              >
                <el-option
                  v-for="option in variableOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </div>

            <div class="rule-fields">
              <label>目标变量</label>
              <el-select
                :model-value="getCrossValue(rule, 'target_tag')"
                filterable
                class="full-width"
                placeholder="选择待校验列"
                @update:model-value="updateCrossValue(rule, 'target_tag', $event)"
              >
                <el-option
                  v-for="option in variableOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </div>
          </div>
        </article>
      </div>
    </div>

    <aside class="dynamic-rule-panel">
      <div class="panel-toolbar">
        <div class="toolbar-copy">
          <strong>动态规则配置</strong>
          <span>为未来扩展保留自定义 rule_type 和 params JSON 的编辑入口。</span>
        </div>
        <div class="toolbar-actions">
          <el-button type="primary" plain @click="addDynamicRule">新增动态规则</el-button>
        </div>
      </div>

      <div v-if="!store.dynamicRules.length" class="empty-rule-state">
        当前没有动态规则。只有在你要验证自定义后端规则时，才需要使用这里。
      </div>

      <article v-for="rule in store.dynamicRules" :key="rule.rule_id" class="dynamic-card">
        <div class="rule-card-head">
          <div>
            <h4>动态规则</h4>
            <p>直接维护 <code>rule_type + params</code>，提交前会自动执行 JSON 校验。</p>
          </div>
          <el-button link type="danger" @click="removeRule(rule.rule_id)">移除</el-button>
        </div>

        <div class="rule-fields">
          <label>rule_type</label>
          <el-input
            :model-value="rule.rule_type"
            placeholder="例如：regex、numeric_range"
            @update:model-value="store.updateRuleType(rule.rule_id ?? '', $event)"
          />
        </div>

        <div class="rule-fields">
          <label>params(JSON)</label>
          <el-input
            :model-value="getDynamicParamsText(rule)"
            type="textarea"
            :rows="8"
            :placeholder="dynamicParamsPlaceholder"
            @update:model-value="updateDynamicParamsText(rule, $event)"
          />
        </div>

        <el-alert
          v-if="getDynamicError(rule)"
          :title="getDynamicError(rule)"
          type="warning"
          :closable="false"
          show-icon
        />
      </article>
    </aside>
  </div>
</template>

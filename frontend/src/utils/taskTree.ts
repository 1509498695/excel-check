import type { DataSource, TaskTree, ValidationRule, VariableTag } from '../types/workbench'

function trimValue(value?: string | null): string {
  return value?.trim() ?? ''
}

function createCleanObject<T extends Record<string, unknown>>(value: T): T {
  const entries = Object.entries(value).filter(([, item]) => item !== undefined && item !== '')

  return Object.fromEntries(entries) as T
}

function normalizeSource(source: DataSource): DataSource {
  const id = trimValue(source.id)
  const pathOrUrl = trimValue(source.pathOrUrl ?? source.path ?? source.url)
  const token = trimValue(source.token)

  if (!id) {
    throw new Error('步骤 1 中存在未填写的数据源标识。')
  }

  if (!pathOrUrl) {
    throw new Error(`数据源 "${id}" 缺少路径或链接。`)
  }

  if (source.type === 'feishu') {
    return createCleanObject({
      id,
      type: source.type,
      url: pathOrUrl,
      pathOrUrl,
      token: token || undefined,
    })
  }

  return createCleanObject({
    id,
    type: source.type,
    path: pathOrUrl,
    pathOrUrl,
    token: token || undefined,
  })
}

function normalizeVariable(variable: VariableTag, sourceIds: Set<string>): VariableTag {
  const tag = trimValue(variable.tag)
  const sourceId = trimValue(variable.source_id)
  const sheet = trimValue(variable.sheet)
  const column = trimValue(variable.column)

  if (!tag) {
    throw new Error('步骤 2 中存在未填写的变量标签。')
  }

  if (!sourceId) {
    throw new Error(`变量 "${tag}" 缺少 source_id。`)
  }

  if (!sourceIds.has(sourceId)) {
    throw new Error(`变量 "${tag}" 引用了不存在的数据源 "${sourceId}"。`)
  }

  if (!sheet) {
    throw new Error(`变量 "${tag}" 缺少 sheet。`)
  }

  if (!column) {
    throw new Error(`变量 "${tag}" 缺少 column。`)
  }

  return createCleanObject({
    tag,
    source_id: sourceId,
    sheet,
    column,
    expected_type: variable.expected_type ?? undefined,
  })
}

function normalizeKnownRule(rule: ValidationRule, availableTags: Set<string>): ValidationRule {
  if (rule.rule_type === 'not_null' || rule.rule_type === 'unique') {
    const rawTags = rule.params.target_tags
    if (!Array.isArray(rawTags) || rawTags.length === 0) {
      throw new Error(`规则 "${rule.rule_type}" 需要至少选择一个目标变量。`)
    }

    const targetTags = rawTags
      .map((item) => (typeof item === 'string' ? item.trim() : ''))
      .filter(Boolean)

    if (targetTags.length === 0) {
      throw new Error(`规则 "${rule.rule_type}" 需要至少选择一个目标变量。`)
    }

    const unknownTag = targetTags.find((item) => !availableTags.has(item))
    if (unknownTag) {
      throw new Error(`规则 "${rule.rule_type}" 引用了不存在的变量 "${unknownTag}"。`)
    }

    return {
      rule_id: rule.rule_id,
      rule_type: rule.rule_type,
      params: { target_tags: targetTags },
    }
  }

  if (rule.rule_type === 'cross_table_mapping') {
    const dictTag = typeof rule.params.dict_tag === 'string' ? rule.params.dict_tag.trim() : ''
    const targetTag =
      typeof rule.params.target_tag === 'string' ? rule.params.target_tag.trim() : ''

    if (!dictTag) {
      throw new Error('规则 "cross_table_mapping" 缺少字典变量。')
    }

    if (!targetTag) {
      throw new Error('规则 "cross_table_mapping" 缺少目标变量。')
    }

    if (!availableTags.has(dictTag)) {
      throw new Error(`规则 "cross_table_mapping" 引用了不存在的变量 "${dictTag}"。`)
    }

    if (!availableTags.has(targetTag)) {
      throw new Error(`规则 "cross_table_mapping" 引用了不存在的变量 "${targetTag}"。`)
    }

    return {
      rule_id: rule.rule_id,
      rule_type: rule.rule_type,
      params: { dict_tag: dictTag, target_tag: targetTag },
    }
  }

  return rule
}

function normalizeDynamicRule(rule: ValidationRule): ValidationRule {
  const ruleType = trimValue(rule.rule_type)
  if (!ruleType) {
    throw new Error('动态规则缺少 rule_type。')
  }

  const rawText = trimValue(rule.draftState?.paramsText ?? '')
  if (!rawText) {
    return {
      rule_id: rule.rule_id,
      rule_type: ruleType,
      params: {},
    }
  }

  let parsed: unknown
  try {
    parsed = JSON.parse(rawText)
  } catch (error) {
    throw new Error(
      `动态规则 "${ruleType}" 的参数 JSON 不合法：${error instanceof Error ? error.message : '无法解析'}。`,
    )
  }

  if (parsed === null || Array.isArray(parsed) || typeof parsed !== 'object') {
    throw new Error(`动态规则 "${ruleType}" 的参数必须是 JSON 对象。`)
  }

  return {
    rule_id: rule.rule_id,
    rule_type: ruleType,
    params: parsed as Record<string, unknown>,
  }
}

export function buildTaskTreePayload(
  sources: DataSource[],
  variables: VariableTag[],
  rules: ValidationRule[],
): TaskTree {
  const normalizedSources = sources.map(normalizeSource)
  const sourceIds = new Set<string>()

  normalizedSources.forEach((source) => {
    if (sourceIds.has(source.id)) {
      throw new Error(`数据源标识 "${source.id}" 重复，请保持唯一。`)
    }
    sourceIds.add(source.id)
  })

  const normalizedVariables = variables.map((variable) => normalizeVariable(variable, sourceIds))
  const variableTags = new Set<string>()

  normalizedVariables.forEach((variable) => {
    if (variableTags.has(variable.tag)) {
      throw new Error(`变量标签 "${variable.tag}" 重复，请保持唯一。`)
    }
    variableTags.add(variable.tag)
  })

  const normalizedRules = rules.map((rule) => {
    if (rule.mode === 'dynamic') {
      return normalizeDynamicRule(rule)
    }

    return normalizeKnownRule(rule, variableTags)
  })

  return {
    sources: normalizedSources,
    variables: normalizedVariables,
    rules: normalizedRules,
  }
}

export function createRuleId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

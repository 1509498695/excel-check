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
  const variableKind = variable.variable_kind ?? 'single'
  const expectedType = variableKind === 'composite' ? 'json' : variable.expected_type ?? undefined

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

  if (variableKind === 'composite') {
    const columns = Array.isArray(variable.columns)
      ? [...new Set(variable.columns.map((item) => trimValue(item)).filter(Boolean))]
      : []
    const keyColumn = trimValue(variable.key_column)

    if (columns.length < 2) {
      throw new Error(`组合变量 "${tag}" 至少需要选择 2 列。`)
    }

    if (!keyColumn) {
      throw new Error(`组合变量 "${tag}" 缺少 key_column。`)
    }

    if (!columns.includes(keyColumn)) {
      throw new Error(`组合变量 "${tag}" 的 key_column 必须包含在 columns 中。`)
    }

    return createCleanObject({
      tag,
      source_id: sourceId,
      sheet,
      variable_kind: 'composite' as const,
      columns,
      key_column: keyColumn,
      expected_type: 'json' as const,
    })
  }

  const column = trimValue(variable.column)
  if (!column) {
    throw new Error(`变量 "${tag}" 缺少 column。`)
  }

  return createCleanObject({
    tag,
    source_id: sourceId,
    sheet,
    variable_kind: 'single' as const,
    column,
    expected_type: expectedType,
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

    const params: Record<string, unknown> = { target_tags: targetTags }
    const ruleName = rule.params.rule_name
    if (typeof ruleName === 'string' && ruleName.trim()) {
      params.rule_name = ruleName.trim()
    }
    const location = rule.params.location
    if (typeof location === 'string' && location.trim()) {
      params.location = location.trim()
    }

    return {
      rule_id: rule.rule_id,
      rule_type: rule.rule_type,
      params,
    }
  }

  if (rule.rule_type === 'fixed_value_compare') {
    const targetTag = typeof rule.params.target_tag === 'string' ? rule.params.target_tag.trim() : ''
    const operator = typeof rule.params.operator === 'string' ? rule.params.operator.trim() : ''
    const expectedValue =
      typeof rule.params.expected_value === 'string' ? rule.params.expected_value.trim() : ''
    const ruleName = typeof rule.params.rule_name === 'string' ? rule.params.rule_name.trim() : ''
    const location = typeof rule.params.location === 'string' ? rule.params.location.trim() : ''

    if (!targetTag) {
      throw new Error('规则 "fixed_value_compare" 缺少 target_tag。')
    }
    if (!availableTags.has(targetTag)) {
      throw new Error(`规则 "fixed_value_compare" 引用了不存在的变量 "${targetTag}"。`)
    }
    if (!['eq', 'ne', 'gt', 'lt'].includes(operator)) {
      throw new Error(`规则 "fixed_value_compare" 的 operator 无效。`)
    }
    if (!expectedValue) {
      throw new Error('规则 "fixed_value_compare" 缺少 expected_value。')
    }
    if ((operator === 'gt' || operator === 'lt') && Number.isNaN(Number(expectedValue))) {
      throw new Error('规则 "fixed_value_compare" 的大于/小于阈值必须是合法数字。')
    }
    if (!ruleName) {
      throw new Error('规则 "fixed_value_compare" 缺少 rule_name。')
    }

    return {
      rule_id: rule.rule_id,
      rule_type: rule.rule_type,
      params: {
        target_tag: targetTag,
        operator,
        expected_value: expectedValue,
        rule_name: ruleName,
        location: location || undefined,
      },
    }
  }

  if (rule.rule_type === 'composite_condition_check') {
    const targetTag = typeof rule.params.target_tag === 'string' ? rule.params.target_tag.trim() : ''
    const ruleName = typeof rule.params.rule_name === 'string' ? rule.params.rule_name.trim() : ''
    const compositeConfig = rule.params.composite_config

    if (!targetTag) {
      throw new Error('规则 "composite_condition_check" 缺少 target_tag。')
    }
    if (!availableTags.has(targetTag)) {
      throw new Error(`规则 "composite_condition_check" 引用了不存在的变量 "${targetTag}"。`)
    }
    if (!ruleName) {
      throw new Error('规则 "composite_condition_check" 缺少 rule_name。')
    }
    if (compositeConfig == null || typeof compositeConfig !== 'object') {
      throw new Error('规则 "composite_condition_check" 缺少 composite_config。')
    }

    return {
      rule_id: rule.rule_id,
      rule_type: rule.rule_type,
      params: {
        target_tag: targetTag,
        rule_name: ruleName,
        composite_config: compositeConfig as Record<string, unknown>,
      },
    }
  }

  if (rule.rule_type === 'cross_table_mapping') {
    const dictTag = typeof rule.params.dict_tag === 'string' ? rule.params.dict_tag.trim() : ''
    const targetTag =
      typeof rule.params.target_tag === 'string' ? rule.params.target_tag.trim() : ''
    const ruleName = typeof rule.params.rule_name === 'string' ? rule.params.rule_name.trim() : ''
    const location = typeof rule.params.location === 'string' ? rule.params.location.trim() : ''

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
      params: createCleanObject({
        dict_tag: dictTag,
        target_tag: targetTag,
        rule_name: ruleName || undefined,
        location: location || undefined,
      }),
    }
  }

  return rule
}

export function buildTaskTreePayload(
  sources: DataSource[],
  variables: VariableTag[],
  rules: ValidationRule[],
  selectedRuleIds?: string[],
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

  const normalizedRules = rules
    .filter((rule) => rule.mode !== 'dynamic')
    .map((rule) => normalizeKnownRule(rule, variableTags))

  const payload: TaskTree = {
    sources: normalizedSources,
    variables: normalizedVariables,
    rules: normalizedRules,
  }

  if (selectedRuleIds) {
    const normalizedSelectedRuleIds = [...new Set(selectedRuleIds.map(trimValue).filter(Boolean))]
    payload.selected_rule_ids = normalizedSelectedRuleIds
  }

  return payload
}

export function createRuleId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

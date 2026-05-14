export const SERVER_CONFIG_EXAMPLE_REGEX =
  '^(?:(?:all|\\d+(?:-\\d+)?):[01](;(?:all|\\d+(?:-\\d+)?):[01])*)?$'

export interface ExtractedSmartRuleHints {
  ruleTypeHint?: string
  targetVariableTag?: string
  referenceVariableTag?: string
  leftVariableTag?: string
  rightVariableTag?: string
  sourceId?: string
  sourceUrl?: string
  sheet?: string
  targetField?: string
  filterField?: string
  filterOperator?: string
  filterValue?: string
  assertionField?: string
  assertionOperator?: string
  assertionValue?: string
  operator?: string
  expectedValue?: string
  expectedValueMode?: string
  displayField?: string
  regexPattern?: string
  sequenceDirection?: string
  sequenceStep?: string
  sequenceStartMode?: string
  sequenceStartValue?: string
  keyColumn?: string
  compositeColumns?: string
  leftFilterField?: string
  leftFilterOperator?: string
  leftFilterValue?: string
  rightFilterField?: string
  rightFilterOperator?: string
  rightFilterValue?: string
  leftKeyField?: string
  rightKeyField?: string
  compareFields?: string
}

export function extractSmartRuleWorkflowHints(text: string): ExtractedSmartRuleHints {
  const normalizedText = normalizeText(text)
  const sourceUrl = extractSourceUrl(normalizedText)
  const sourceId = deriveSourceId(sourceUrl)
  const sheet = extractSheet(normalizedText)
  let ruleTypeHint = inferRuleType(normalizedText)
  const targetVariableTag = extractLabeledVariableTag(normalizedText, ['目标变量', '变量'])
  const referenceVariableTag = extractLabeledVariableTag(normalizedText, ['引用变量', '字典变量'])
  const leftVariableTag = extractLabeledVariableTag(normalizedText, ['左侧变量', '基准变量'])
  const rightVariableTag = extractLabeledVariableTag(normalizedText, ['右侧变量', '对比变量'])
  const dualFilters = extractDualFilters(normalizedText)
  const filter = extractFilter(normalizedText)
  const filterOperator = extractFilterOperator(normalizedText, filter.filterField, filter.filterValue)
  let displayField = extractDisplayField(normalizedText)
  let keyColumn = extractKeyColumn(normalizedText)
  const compareFields = extractCompareFields(normalizedText, {
    keyColumn,
    filterFields: [filter.filterField, dualFilters.leftFilterField, dualFilters.rightFilterField],
    displayField,
  })
  const targetField = extractTargetField(normalizedText, {
    filterField: filter.filterField,
    displayField,
    keyColumn: ruleTypeHint === 'dual_composite_compare' ? undefined : keyColumn,
    compareFields,
  })
  let regexPattern = extractRegexPattern(normalizedText)
  let filterField = ruleTypeHint === 'dual_composite_compare' ? undefined : filter.filterField
  let filterValue = ruleTypeHint === 'dual_composite_compare' ? undefined : filter.filterValue
  let normalizedFilterOperator = ruleTypeHint === 'dual_composite_compare' ? undefined : filterOperator
  const fixedValue = extractFixedValueCompare(normalizedText)
  const assertion = extractAssertionCompare(normalizedText, filterField)
  if (
    ruleTypeHint !== 'dual_composite_compare' &&
    filterField &&
    filterValue &&
    assertion.assertionField &&
    assertion.assertionValue
  ) {
    ruleTypeHint = 'composite_condition_check'
  }
  const sequence = extractSequence(normalizedText)

  if (sourceId === 'server_config' && sheet === 'switch' && targetField === 'STR_ServersParam') {
    ruleTypeHint = 'composite_condition_check'
    keyColumn ||= 'INT_Id'
    displayField ||= 'STR_Func'
    filterField ||= 'DES'
    filterValue ||= '废弃'
    normalizedFilterOperator ||= 'not_contains'
    regexPattern ||= SERVER_CONFIG_EXAMPLE_REGEX
  }

  const compositeColumns = buildCompositeColumns({
    keyColumn,
    displayField,
    targetField,
    filterField,
    leftFilterField: dualFilters.leftFilterField,
    rightFilterField: dualFilters.rightFilterField,
    assertionField: assertion.assertionField,
    compareFields,
  }).join(',')

  return compactHints({
    ruleTypeHint,
    targetVariableTag: targetVariableTag || leftVariableTag,
    referenceVariableTag: referenceVariableTag || rightVariableTag,
    leftVariableTag,
    rightVariableTag,
    sourceId,
    sourceUrl,
    sheet,
    targetField: ruleTypeHint === 'dual_composite_compare' ? targetField || keyColumn : targetField,
    filterField,
    filterOperator: normalizedFilterOperator,
    filterValue,
    assertionField: assertion.assertionField,
    assertionOperator: assertion.assertionOperator,
    assertionValue: assertion.assertionValue,
    displayField,
    operator: fixedValue.operator,
    expectedValue: fixedValue.expectedValue,
    expectedValueMode: fixedValue.expectedValueMode,
    regexPattern,
    sequenceDirection: sequence.sequenceDirection,
    sequenceStep: sequence.sequenceStep,
    sequenceStartMode: sequence.sequenceStartMode,
    sequenceStartValue: sequence.sequenceStartValue,
    keyColumn,
    compositeColumns,
    leftFilterField: dualFilters.leftFilterField,
    leftFilterOperator: dualFilters.leftFilterField && dualFilters.leftFilterValue ? 'eq' : undefined,
    leftFilterValue: dualFilters.leftFilterValue,
    rightFilterField: dualFilters.rightFilterField,
    rightFilterOperator: dualFilters.rightFilterField && dualFilters.rightFilterValue ? 'eq' : undefined,
    rightFilterValue: dualFilters.rightFilterValue,
    leftKeyField: ruleTypeHint === 'dual_composite_compare' ? keyColumn : undefined,
    rightKeyField: ruleTypeHint === 'dual_composite_compare' ? keyColumn : undefined,
    compareFields: compareFields.join(','),
  })
}

function normalizeText(text: string): string {
  return text
    .replaceAll('\r', ' ')
    .replaceAll('\n', ' ')
    .replaceAll('“', '"')
    .replaceAll('”', '"')
    .replaceAll('‘', "'")
    .replaceAll('’', "'")
    .trim()
}

function extractSourceUrl(text: string): string | undefined {
  return text.match(/https?:\/\/[A-Za-z0-9_./:%?=&~#+-]+\.xls[xm]?/i)?.[0]
}

function extractSheet(text: string): string | undefined {
  return firstMatch(text, [
    /\$?\s*([A-Za-z][A-Za-z0-9_]*)\s*(?:分页|页签|工作表|sheet|Sheet)/i,
    /(?:Sheet|sheet)\s*[：:=为是]?\s*([A-Za-z][A-Za-z0-9_]*)/i,
  ])
}

function extractFilter(text: string): { filterField?: string; filterValue?: string } {
  const patterns = [
    /(?:筛选|过滤)\s*([A-Za-z][A-Za-z0-9_]*)\s*=\s*([^。；;\n\r]+)/i,
    /(?:筛选|过滤)[^。；;\n\r]*?([A-Za-z][A-Za-z0-9_]*)\s*(?:等于|为|是)\s*([^。；;\n\r]+)/i,
    /(?:过滤掉|过滤|排除)[^，。；;]*?([A-Za-z][A-Za-z0-9_]*)\s*字段[^，。；;]*?(?:包含|含有)\s*["']?([^"'，。；;、\s]+)/i,
    /([A-Za-z][A-Za-z0-9_]*)\s*字段[^，。；;]*?(?:包含|含有)\s*["']?([^"'，。；;、\s]+)[^，。；;]*?(?:过滤|排除)/i,
  ]
  for (const pattern of patterns) {
    const match = text.match(pattern)
    if (match?.[1] && match[2]) {
      return {
        filterField: match[1].trim(),
        filterValue: cleanFilterValue(trimFilterTail(match[2])),
      }
    }
  }
  return {}
}

function extractFilterOperator(
  text: string,
  filterField?: string,
  filterValue?: string,
): string | undefined {
  if (!filterField || !filterValue) return undefined
  if (text.includes('不包含') || text.includes('过滤掉') || text.includes('排除')) return 'not_contains'
  if (text.includes('包含') || text.includes('含有')) return 'contains'
  if (text.includes('不等于') || text.includes('!=')) return 'ne'
  return 'eq'
}

function cleanFilterValue(value: string): string {
  const cleaned = cleanSetValue(value)
  return cleaned.replace(/(?:的)?(?:字段|列|行|数据|记录|配置)$/, '').trim() || cleaned
}

function trimFilterTail(value: string): string {
  return value
    .trim()
    .split(/(?:[,，]\s*)?(?:以|按)\s*[A-Za-z][A-Za-z0-9_]*\s*(?:字段)?\s*(?:为|作为)?\s*(?:Key|key|主键|唯一键)/, 1)[0]
    .split(/(?:[,，]\s*)?(?:判断|比较|比对|校验|检查)\s*[：:]/, 1)[0]
    .trim()
}

function extractAssertionCompare(
  text: string,
  filterField?: string,
): { assertionField?: string; assertionOperator?: string; assertionValue?: string } {
  const patterns = [
    /([A-Za-z][A-Za-z0-9_]*)\s*字段\s*=\s*([^。；;\n\r]+)/i,
    /(?:校验|验证|检查)\s*([A-Za-z][A-Za-z0-9_]*)\s*字段\s*(?:等于|为|是)\s*([^。；;\n\r]+)/i,
    /([A-Za-z][A-Za-z0-9_]*)\s*字段\s*(?:等于|为|是)\s*([^。；;\n\r]+)/i,
  ]
  for (const pattern of patterns) {
    const match = text.match(pattern)
    if (!match?.[1] || !match[2]) continue
    const field = match[1].trim()
    if (filterField && field === filterField) continue
    return {
      assertionField: field,
      assertionOperator: 'eq',
      assertionValue: cleanSetValue(match[2]),
    }
  }
  return {}
}

function cleanSetValue(value: string): string {
  return value
    .trim()
    .replace(/^["']|["']$/g, '')
    .replace(/\s+(?:or|OR)\s+/g, ',')
    .replaceAll('，', ',')
    .replaceAll('、', ',')
    .replace(/(?:,\s*)?(?:两种类型|两个类型|两类|两种|这些类型|这几种类型|多个类型|多个值)$/, '')
    .replace(/\s+/g, '')
    .replace(/,+/g, ',')
    .replace(/^,|,$/g, '')
}

function extractDisplayField(text: string): string | undefined {
  return firstMatch(text, [
    /(?:结果显示|显示字段|展示字段|结果字段)\s*[：:=为是]?\s*([A-Za-z][A-Za-z0-9_]*)/i,
    /([A-Za-z][A-Za-z0-9_]*)\s*(?:作为|为)\s*(?:结果显示|展示字段)/i,
  ])
}

function extractTargetField(
  text: string,
  excluded: {
    filterField?: string
    displayField?: string
    keyColumn?: string
    compareFields?: string[]
  },
): string | undefined {
  const explicit = firstMatch(text, [
    /(?:校验|验证|检查)\s*([A-Za-z][A-Za-z0-9_]*)\s*字段/i,
    /([A-Za-z][A-Za-z0-9_]*)\s*字段[^，。；;]*?(?:配置数据格式|配置格式|格式)/i,
    /(?:目标字段|目标列名|校验字段)\s*[：:=为是]?\s*([A-Za-z][A-Za-z0-9_]*)/i,
  ])
  if (explicit) return explicit

  const excludedValues = new Set(
    [excluded.filterField, excluded.displayField, excluded.keyColumn, ...(excluded.compareFields ?? [])].filter(
      Boolean,
    ),
  )
  for (const match of text.matchAll(/([A-Za-z][A-Za-z0-9_]*)\s*字段/g)) {
    const candidate = match[1]
    if (!excludedValues.has(candidate)) return candidate
  }
  return undefined
}

function extractKeyColumn(text: string): string | undefined {
  const candidate =
    firstMatch(text, [
      /(?:Key|key|索引|主键|唯一键)\s*(?:列|字段)?\s*[：:=为是]?\s*([A-Za-z][A-Za-z0-9_]*)/i,
      /([A-Za-z][A-Za-z0-9_]*)\s*字段\s*(?:作为|为)\s*(?:Key|key|索引|主键|唯一键)/i,
      /([A-Za-z][A-Za-z0-9_]*)\s*(?:作为|为)\s*(?:Key|key|索引|主键|唯一键)/i,
    ]) ?? text.match(/\bINT_Id\b/)?.[0]
  return candidate && !isPlaceholderKeyColumn(candidate) ? candidate : undefined
}

function extractRegexPattern(text: string): string | undefined {
  if (text.includes('冒号') && (text.includes('只能配置 1 或 0') || text.includes('只能配置1或0'))) {
    return SERVER_CONFIG_EXAMPLE_REGEX
  }
  if ((text.includes('冒号') || text.includes(':')) && /(?:1\s*(?:或|or|\/)\s*0|0\s*(?:或|or|\/)\s*1)/i.test(text)) {
    return SERVER_CONFIG_EXAMPLE_REGEX
  }
  if (/\d+\s*:\s*[01](?:\s*;\s*\d+\s*:\s*[01])+/.test(text)) {
    return SERVER_CONFIG_EXAMPLE_REGEX
  }
  return undefined
}

function inferRuleType(text: string): string | undefined {
  const explicit = firstMatch(text, [
    /(?:规则类型|rule_type)\s*[：:=]\s*([A-Za-z_]+)/i,
    /(?:规则类型|rule_type)\s+([A-Za-z_]+)/i,
  ])
  if (
    explicit &&
    [
      'not_null',
      'unique',
      'regex_check',
      'sequence_order_check',
      'fixed_value_compare',
      'cross_table_mapping',
      'composite_condition_check',
      'dual_composite_compare',
      'multi_composite_pipeline_check',
      'multi_composite_mapping_check',
    ].includes(explicit)
  ) {
    return explicit
  }
  const lower = text.toLowerCase()
  if (/(公式|聚合|平均|求和|脚本|计算后|跨行统计)/.test(text)) return undefined
  if (/(两组|两个配置|两份配置|是不是相等|是否相等)/.test(text) && /(以|key|Key|筛选)/.test(text)) {
    return 'dual_composite_compare'
  }
  if (/(多组串行|多节点串行|多级链路|链路|pipeline)/.test(text)) return 'multi_composite_pipeline_check'
  if (/(多组映射|多节点映射|映射校验|mapping)/.test(text)) return 'multi_composite_mapping_check'
  if (/(存在于|字典表|字典变量|包含\(in\)| in )/.test(text) && /(另一|引用|字典|表)/.test(text)) {
    return 'cross_table_mapping'
  }
  if (/(筛选|过滤|当|如果)/.test(text) && /(校验|检查|判断|必须|格式|正则)/.test(text)) {
    return 'composite_condition_check'
  }
  if (/(不能为空|非空|必填|not null|not_null)/i.test(text)) return 'not_null'
  if (/(唯一|不能重复|不可重复|unique)/i.test(text)) return 'unique'
  if (/(升序|降序|递增|递减|连续|步长|顺序|sequence)/i.test(text)) return 'sequence_order_check'
  if (/(正则|格式|匹配|regex)/i.test(text)) return 'regex_check'
  if (/(等于|不等于|大于|小于|只能是|必须是|=|!=|>|<)/.test(text)) return 'fixed_value_compare'
  if (lower.includes('not_null')) return 'not_null'
  if (lower.includes('unique')) return 'unique'
  return undefined
}

function extractLabeledVariableTag(text: string, labels: string[]): string | undefined {
  const labelPattern = labels.map((label) => label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')
  return firstMatch(text, [
    new RegExp(`(?:${labelPattern})\\s*[：:=]\\s*(\\[[^\\]\\r\\n]+\\])`, 'i'),
  ])
}

function extractDualFilters(text: string): {
  leftFilterField?: string
  leftFilterValue?: string
  rightFilterField?: string
  rightFilterValue?: string
} {
  const patterns = [
    /筛选\s*([A-Za-z][A-Za-z0-9_]*)\s*=\s*([^和，。；;\s]+)\s*和\s*\1\s*=\s*([^，。；;\s]+)/i,
    /筛选[^，。；;]*?([A-Za-z][A-Za-z0-9_]*)\s*(?:等于|为|是)\s*([^和，。；;\s]+)\s*和\s*\1\s*(?:等于|为|是)\s*([^，。；;\s]+)/i,
  ]
  for (const pattern of patterns) {
    const match = text.match(pattern)
    if (match?.[1] && match[2] && match[3]) {
      return {
        leftFilterField: match[1].trim(),
        leftFilterValue: cleanFilterValue(match[2]),
        rightFilterField: match[1].trim(),
        rightFilterValue: cleanFilterValue(match[3]),
      }
    }
  }
  const values = Array.from(text.matchAll(/([A-Za-z][A-Za-z0-9_]*)\s*=\s*([^和，。；;\s]+)/g))
  if (values.length >= 2 && values[0][1] === values[1][1]) {
    return {
      leftFilterField: values[0][1].trim(),
      leftFilterValue: cleanFilterValue(values[0][2]),
      rightFilterField: values[1][1].trim(),
      rightFilterValue: cleanFilterValue(values[1][2]),
    }
  }
  return {}
}

function extractCompareFields(
  text: string,
  excluded: {
    keyColumn?: string
    filterFields?: Array<string | undefined>
    displayField?: string
  },
): string[] {
  const explicit =
    firstMatch(text, [
      /(?:判断|比较|比对|校验)([^。；;]*?)(?:这|的)?(?:四个|多个|这些)?字段/i,
      /(?:四个|多个|这些)字段[：:=为是]?\s*([^。；;]+)/i,
    ]) ?? text
  const excludedValues = new Set(
    [excluded.keyColumn, excluded.displayField, ...(excluded.filterFields ?? [])].filter(Boolean),
  )
  const result: string[] = []
  for (const match of explicit.matchAll(/\b[A-Z][A-Za-z0-9]*_[A-Za-z0-9_]+\b/g)) {
    const candidate = match[0]
    if (!excludedValues.has(candidate) && !result.includes(candidate)) {
      result.push(candidate)
    }
  }
  return result
}

function extractFixedValueCompare(text: string): {
  operator?: string
  expectedValue?: string
  expectedValueMode?: string
} {
  const patterns: Array<[RegExp, string]> = [
    [/(?:只能是|必须是|等于|为|是)\s*["']?([^"'，。；;、\s]+)/i, 'eq'],
    [/(?:不等于|不能是|不可为|!=)\s*["']?([^"'，。；;、\s]+)/i, 'ne'],
    [/(?:大于|>)\s*["']?([^"'，。；;、\s]+)/i, 'gt'],
    [/(?:小于|<)\s*["']?([^"'，。；;、\s]+)/i, 'lt'],
  ]
  for (const [pattern, operator] of patterns) {
    const match = text.match(pattern)
    if (match?.[1]) {
      const expectedValue = match[1].trim().replaceAll('，', ',')
      if (looksLikeMetaExpectedValue(expectedValue)) {
        continue
      }
      return {
        operator,
        expectedValue,
        expectedValueMode: /[,，或]/.test(match[1]) ? 'set' : 'single',
      }
    }
  }
  return {}
}

function looksLikeMetaExpectedValue(value: string): boolean {
  return value.startsWith('更适合') || value.startsWith('适合') || ['AI', 'ai', '解析'].includes(value)
}

function extractSequence(text: string): {
  sequenceDirection?: string
  sequenceStep?: string
  sequenceStartMode?: string
  sequenceStartValue?: string
} {
  const sequenceDirection = /(降序|递减)/.test(text)
    ? 'desc'
    : /(升序|递增|连续|顺序)/.test(text)
      ? 'asc'
      : undefined
  const sequenceStep = text.match(/步长\s*[：:=为是]?\s*(\d+)/)?.[1]
  const sequenceStartValue = text.match(/(?:起始值|从)\s*[：:=为是]?\s*(\d+)/)?.[1]
  return {
    sequenceDirection,
    sequenceStep,
    sequenceStartMode: sequenceStartValue ? 'manual' : sequenceDirection ? 'auto' : undefined,
    sequenceStartValue,
  }
}

function buildCompositeColumns(values: {
  keyColumn?: string
  displayField?: string
  targetField?: string
  filterField?: string
  leftFilterField?: string
  rightFilterField?: string
  assertionField?: string
  compareFields?: string[]
}): string[] {
  const result: string[] = []
  for (const value of [
    values.keyColumn,
    values.displayField,
    values.targetField,
    values.filterField,
    values.assertionField,
    values.leftFilterField,
    values.rightFilterField,
    ...(values.compareFields ?? []),
  ]) {
    if (value && !isPlaceholderKeyColumn(value) && !result.includes(value)) {
      result.push(value)
    }
  }
  return result
}

function isPlaceholderKeyColumn(value?: string): boolean {
  if (!value?.trim()) return false
  if (value.includes('未识别') || value.includes('需要用户确认')) return true
  const compact = value.replace(/[\s:：=为是列字段、，。；;]/g, '').toLowerCase()
  return ['key', '关联key', '业务key', '比对key', '对齐key', '主键', '唯一键', '索引'].includes(compact)
}

function firstMatch(text: string, patterns: RegExp[]): string | undefined {
  for (const pattern of patterns) {
    const match = text.match(pattern)
    if (match?.[1]) {
      return match[1].trim()
    }
  }
  return undefined
}

function deriveSourceId(sourceUrl?: string): string | undefined {
  if (!sourceUrl) return undefined
  const fileName = sourceUrl.split(/[?#]/)[0].split('/').pop() ?? ''
  const stem = fileName.includes('.') ? fileName.slice(0, fileName.lastIndexOf('.')) : fileName
  const sourceId = stem.replace(/[^A-Za-z0-9_]+/g, '_').replace(/^_+|_+$/g, '')
  return sourceId || undefined
}

function compactHints(hints: ExtractedSmartRuleHints): ExtractedSmartRuleHints {
  return Object.fromEntries(
    Object.entries(hints).filter(([, value]) => typeof value === 'string' && value.trim()),
  ) as ExtractedSmartRuleHints
}

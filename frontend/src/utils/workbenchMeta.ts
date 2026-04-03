import type { ExpectedType, SourceType } from '../types/workbench'

export const SOURCE_TYPE_OPTIONS: Array<{ label: string; value: SourceType }> = [
  { label: '本地 Excel', value: 'local_excel' },
  { label: '本地 CSV', value: 'local_csv' },
  { label: '飞书表格', value: 'feishu' },
  { label: 'SVN 配置目录', value: 'svn' },
]

export const EXPECTED_TYPE_OPTIONS: Array<{ label: string; value: ExpectedType }> = [
  { label: '字符串', value: 'str' },
  { label: 'JSON', value: 'json' },
]

export const STATIC_RULE_TEMPLATES = [
  {
    ruleType: 'not_null',
    title: '批量非空校验',
    description: '检查目标字段是否存在空值、空字符串或仅包含空白符的内容。',
    level: 'error',
  },
  {
    ruleType: 'unique',
    title: '批量唯一性校验',
    description: '检查目标字段是否存在重复值，空值默认不参与重复判断。',
    level: 'warning',
  },
  {
    ruleType: 'cross_table_mapping',
    title: '跨表映射校验',
    description: '检查目标列的值是否全部出现在字典列中，适合做外键存在性校验。',
    level: 'error',
  },
] as const

export const SAMPLE_SOURCE_PATH = 'D:/project/excel-check/backend/tests/data/minimal_rules.xlsx'

export function getSourceTypeLabel(type: SourceType): string {
  return SOURCE_TYPE_OPTIONS.find((item) => item.value === type)?.label ?? type
}

export function getRuleTitle(ruleType: string): string {
  return STATIC_RULE_TEMPLATES.find((item) => item.ruleType === ruleType)?.title ?? ruleType
}

export function getRuleLevelTone(ruleType: string): 'danger' | 'warning' | 'primary' {
  if (ruleType === 'not_null' || ruleType === 'cross_table_mapping') {
    return 'danger'
  }

  if (ruleType === 'unique') {
    return 'warning'
  }

  return 'primary'
}

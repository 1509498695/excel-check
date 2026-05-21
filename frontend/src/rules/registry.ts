import type { FixedRuleSelection, FixedRuleType } from '../types/fixedRules'
import {
  RULE_ENTRY_TYPE_OPTIONS,
  RULE_SELECTION_NAME_MAP,
  RULE_SELECTION_OPTIONS,
  RULE_TYPE_NAME_MAP,
  type RuleEntryType,
} from './constants'

export interface RuleRegistryItem {
  ruleType: FixedRuleType
  selection: FixedRuleSelection
  entryType: RuleEntryType
  label: string
}

export const RULE_REGISTRY: RuleRegistryItem[] = [
  { ruleType: 'fixed_value_compare', selection: 'eq', entryType: 'single', label: '固定值比较' },
  { ruleType: 'regex_check', selection: 'regex_check', entryType: 'single', label: '正则校验' },
  { ruleType: 'not_null', selection: 'not_null', entryType: 'single', label: '非空校验' },
  { ruleType: 'unique', selection: 'unique', entryType: 'single', label: '唯一校验' },
  {
    ruleType: 'sequence_order_check',
    selection: 'sequence_order_check',
    entryType: 'single',
    label: '顺序校验',
  },
  { ruleType: 'cross_table_mapping', selection: 'in', entryType: 'single', label: '包含校验' },
  {
    ruleType: 'composite_condition_check',
    selection: 'composite_condition_check',
    entryType: 'composite',
    label: RULE_TYPE_NAME_MAP.composite_condition_check,
  },
  {
    ruleType: 'dual_composite_compare',
    selection: 'dual_composite_compare',
    entryType: 'dual_composite',
    label: RULE_TYPE_NAME_MAP.dual_composite_compare,
  },
  {
    ruleType: 'multi_composite_pipeline_check',
    selection: 'multi_composite_pipeline_check',
    entryType: 'multi_composite_pipeline',
    label: RULE_TYPE_NAME_MAP.multi_composite_pipeline_check,
  },
  {
    ruleType: 'multi_composite_mapping_check',
    selection: 'multi_composite_mapping_check',
    entryType: 'multi_composite_mapping',
    label: RULE_TYPE_NAME_MAP.multi_composite_mapping_check,
  },
]

export function getRuleEntryTypeBySelection(selection: FixedRuleSelection): RuleEntryType {
  return RULE_REGISTRY.find((item) => item.selection === selection)?.entryType ?? 'single'
}

export function getRegistryRuleSelectionName(selection: FixedRuleSelection): string {
  return RULE_SELECTION_NAME_MAP[selection]
}

export { RULE_ENTRY_TYPE_OPTIONS, RULE_SELECTION_OPTIONS }

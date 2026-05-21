import type {
  ExpectedValueMode,
  FixedRuleSelection,
} from '../../types/fixedRules'
import type { RuleEntryType } from '../../rules'

export interface RuleFormState {
  rule_id: string
  group_id: string
  rule_name: string
  rule_entry_type: RuleEntryType
  target_variable_tag: string
  display_field: string
  selected_rule: FixedRuleSelection
  expected_value: string
  expected_value_mode: ExpectedValueMode
  reference_variable_tag: string
  sequence_direction: 'asc' | 'desc'
  sequence_step: string
  sequence_start_mode: 'auto' | 'manual'
  sequence_start_value: string
  key_check_mode: 'baseline_only' | 'bidirectional'
  left_key_field: string
  right_key_field: string
}

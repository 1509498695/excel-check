import { reactive, ref } from 'vue'

import type {
  CompositeCondition,
  CompositeRuleConfig,
  DualCompositeComparison,
  MultiCompositeMappingConfig,
  MultiCompositePipelineConfig,
} from '../../types/fixedRules'
import { KEY_FIELD } from '../../rules'
import type { RuleFormState } from './types'

export function createDefaultRuleForm(): RuleFormState {
  return {
    rule_id: '',
    group_id: 'ungrouped',
    rule_name: '',
    rule_entry_type: 'single',
    target_variable_tag: '',
    display_field: '',
    selected_rule: 'gt',
    expected_value: '0',
    expected_value_mode: 'single',
    reference_variable_tag: '',
    sequence_direction: 'asc',
    sequence_step: '1',
    sequence_start_mode: 'auto',
    sequence_start_value: '',
    key_check_mode: 'baseline_only',
    left_key_field: KEY_FIELD,
    right_key_field: KEY_FIELD,
  }
}

export function resetRuleForm(ruleForm: RuleFormState): void {
  Object.assign(ruleForm, createDefaultRuleForm())
}

export function useRuleForm() {
  const ruleForm = reactive<RuleFormState>(createDefaultRuleForm())
  const compositeRuleForm = reactive<CompositeRuleConfig>({
    global_filters: [],
    branches: [],
  })
  const dualCompositeComparisons = ref<DualCompositeComparison[]>([])
  const dualCompositeLeftFilters = ref<CompositeCondition[]>([])
  const dualCompositeRightFilters = ref<CompositeCondition[]>([])
  const pipelineRuleForm = reactive<MultiCompositePipelineConfig>({
    nodes: [],
  })
  const mappingRuleForm = reactive<MultiCompositeMappingConfig>({
    nodes: [],
  })

  return {
    ruleForm,
    compositeRuleForm,
    dualCompositeComparisons,
    dualCompositeLeftFilters,
    dualCompositeRightFilters,
    pipelineRuleForm,
    mappingRuleForm,
  }
}

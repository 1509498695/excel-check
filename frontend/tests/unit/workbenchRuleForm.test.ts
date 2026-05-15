import { describe, expect, it } from 'vitest'

import type {
  CompositeRuleConfig,
  FixedRuleDefinition,
  MultiCompositeMappingConfig,
  MultiCompositePipelineConfig,
} from '../../src/types/fixedRules'
import type { DataSource, VariableTag } from '../../src/types/workbench'
import {
  KEY_FIELD,
  buildCompositeFieldOptions,
  buildDefaultRuleName,
  buildRuleCompareValueSummary,
  buildRuleCondition,
  buildRuleSelectionSummary,
  buildRuleSourcePathSummary,
  buildRuleVariableSummary,
  buildWorkbenchRuleFromForm,
  createDefaultWorkbenchRuleFormState,
  createEditWorkbenchRuleDialogState,
  normalizeCompositeConfig,
  normalizeDualCompositeComparisons,
  normalizeDualCompositeFilters,
  normalizeMappingConfig,
  normalizePipelineConfig,
  validateWorkbenchRuleForm,
  type WorkbenchRuleFormState,
} from '../../src/utils/workbenchRuleForm'

const sources: DataSource[] = [
  {
    id: 'src_items',
    type: 'local_excel',
    pathOrUrl: 'C:/data/items.xlsx',
  },
]

const singleVariable: VariableTag = {
  tag: '[items-id]',
  source_id: 'src_items',
  sheet: 'items',
  variable_kind: 'single',
  column: 'ID',
  expected_type: 'int',
}

const referenceVariable: VariableTag = {
  tag: '[items-name]',
  source_id: 'src_items',
  sheet: 'items',
  variable_kind: 'single',
  column: 'Name',
  expected_type: 'str',
}

const compositeVariable: VariableTag = {
  tag: '[items-composite]',
  source_id: 'src_items',
  sheet: 'items',
  variable_kind: 'composite',
  key_column: 'ID',
  columns: ['ID', 'Type', 'Reward'],
  expected_type: 'json',
}

const referenceCompositeVariable: VariableTag = {
  tag: '[drops-composite]',
  source_id: 'src_items',
  sheet: 'drops',
  variable_kind: 'composite',
  key_column: 'ID',
  columns: ['ID', 'Type', 'Reward'],
  expected_type: 'json',
}

const variables = [
  singleVariable,
  referenceVariable,
  compositeVariable,
  referenceCompositeVariable,
]
const compositeVariables = [compositeVariable, referenceCompositeVariable]
const variableMap = new Map(variables.map((variable) => [variable.tag, variable] as const))
const sourceMap = new Map(sources.map((source) => [source.id, source] as const))

function fixedRule(overrides: Partial<FixedRuleDefinition>): FixedRuleDefinition {
  return {
    rule_id: overrides.rule_id ?? 'rule',
    group_id: overrides.group_id ?? 'group',
    rule_name: overrides.rule_name ?? 'Rule',
    target_variable_tag: overrides.target_variable_tag ?? '[items-id]',
    rule_type: overrides.rule_type ?? 'fixed_value_compare',
    operator: overrides.operator ?? 'gt',
    expected_value: overrides.expected_value ?? '0',
    ...overrides,
  }
}

function compositeConfig(): CompositeRuleConfig {
  return {
    global_filters: [
      {
        condition_id: 'global-filter',
        field: 'Type',
        operator: 'contains',
        expected_value: 'A',
      },
    ],
    branches: [
      {
        branch_id: 'branch-1',
        filters: [],
        assertions: [
          {
            condition_id: 'assert-1',
            field: 'Reward',
            operator: 'not_null',
          },
        ],
      },
    ],
  }
}

function pipelineConfig(): MultiCompositePipelineConfig {
  return {
    nodes: [
      {
        node_id: 'pipeline-node-1',
        variable_tag: '[items-composite]',
        filters: [],
        assertions: [
          {
            condition_id: 'pipeline-assert-1',
            field: 'Reward',
            operator: 'not_null',
          },
        ],
      },
    ],
  }
}

function mappingConfig(): MultiCompositeMappingConfig {
  return {
    nodes: [
      {
        node_id: 'mapping-node-1',
        variable_tag: '[items-composite]',
        filters: [
          {
            condition_id: 'mapping-filter-1',
            field: 'Type',
            operator: 'eq',
            expected_value: 'A',
            value_source: 'literal',
            exclusion_ranges: [
              {
                range_id: 'mapping-range-1',
                start_row: 2,
                end_row: 3,
                expected_value: 'skip',
              },
            ],
          },
        ],
      },
    ],
  }
}

function validationInput(
  form: WorkbenchRuleFormState,
  overrides: Partial<Parameters<typeof validateWorkbenchRuleForm>[0]> = {},
): Parameters<typeof validateWorkbenchRuleForm>[0] {
  const selectedRuleVariable = variableMap.get(form.target_variable_tag) ?? null
  const selectedReferenceVariable = variableMap.get(form.reference_variable_tag) ?? null
  const isSingleRuleEntry = form.rule_entry_type === 'single'
  const isDualCompositeRule = form.rule_entry_type === 'dual_composite'
  return {
    form,
    selectedRuleVariable,
    selectedReferenceVariable,
    shouldShowTopTargetVariable:
      form.rule_entry_type !== 'multi_composite_pipeline' &&
      form.rule_entry_type !== 'multi_composite_mapping',
    isSingleRuleEntry,
    isCompositeRuleEntry: !isSingleRuleEntry,
    isDualCompositeRule,
    isSameDualCompositeVariable:
      isDualCompositeRule &&
      form.target_variable_tag.trim() !== '' &&
      form.target_variable_tag === form.reference_variable_tag,
    referenceVariableOptions: variables.filter(
      (variable) =>
        (variable.variable_kind ?? 'single') === 'single' &&
        variable.tag !== form.target_variable_tag,
    ),
    compositeFieldOptions: buildCompositeFieldOptions(selectedRuleVariable),
    referenceCompositeFieldOptions: buildCompositeFieldOptions(selectedReferenceVariable),
    compositeConfig: normalizeCompositeConfig(undefined),
    dualComparisons: normalizeDualCompositeComparisons(undefined),
    dualLeftFilters: normalizeDualCompositeFilters(undefined),
    dualRightFilters: normalizeDualCompositeFilters(undefined),
    pipelineConfig: normalizePipelineConfig(undefined, compositeVariables),
    mappingConfig: normalizeMappingConfig(undefined, compositeVariables),
    variableMap,
    ...overrides,
  }
}

describe('workbench rule form helpers', () => {
  it('creates the same default rule form state used by the personal rule dialog', () => {
    expect(createDefaultWorkbenchRuleFormState('group-a', '[items-id]')).toMatchObject({
      rule_id: '',
      group_id: 'group-a',
      rule_name: '',
      rule_entry_type: 'single',
      target_variable_tag: '[items-id]',
      selected_rule: 'gt',
      expected_value: '0',
      expected_value_mode: 'single',
      sequence_direction: 'asc',
      sequence_step: '1',
      sequence_start_mode: 'auto',
      key_check_mode: 'baseline_only',
      left_key_field: KEY_FIELD,
      right_key_field: KEY_FIELD,
    })
  })

  it('derives edit snapshots for the supported rule families', () => {
    expect(
      createEditWorkbenchRuleDialogState(
        fixedRule({
          rule_type: 'fixed_value_compare',
          operator: 'eq',
          expected_value: '0,1',
          expected_value_mode: 'set',
        }),
        compositeVariables,
      ).form,
    ).toMatchObject({ rule_entry_type: 'single', selected_rule: 'eq', expected_value_mode: 'set' })

    expect(
      createEditWorkbenchRuleDialogState(
        fixedRule({ rule_type: 'regex_check', expected_value: '^A+$' }),
        compositeVariables,
      ).form,
    ).toMatchObject({ selected_rule: 'regex_check', expected_value: '^A+$' })

    expect(
      createEditWorkbenchRuleDialogState(
        fixedRule({
          rule_type: 'cross_table_mapping',
          reference_variable_tag: '[items-name]',
          operator: undefined,
          expected_value: undefined,
        }),
        compositeVariables,
      ).form,
    ).toMatchObject({ selected_rule: 'in', reference_variable_tag: '[items-name]' })

    expect(
      createEditWorkbenchRuleDialogState(
        fixedRule({
          rule_type: 'sequence_order_check',
          sequence_direction: 'desc',
          sequence_step: '2',
          sequence_start_mode: 'manual',
          sequence_start_value: '10',
          operator: undefined,
          expected_value: undefined,
        }),
        compositeVariables,
      ).form,
    ).toMatchObject({
      selected_rule: 'sequence_order_check',
      sequence_direction: 'desc',
      sequence_step: '2',
      sequence_start_mode: 'manual',
      sequence_start_value: '10',
    })

    expect(
      createEditWorkbenchRuleDialogState(
        fixedRule({
          rule_type: 'composite_condition_check',
          target_variable_tag: '[items-composite]',
          composite_config: compositeConfig(),
          operator: undefined,
          expected_value: undefined,
        }),
        compositeVariables,
      ).form,
    ).toMatchObject({ rule_entry_type: 'composite', selected_rule: 'composite_condition_check' })

    expect(
      createEditWorkbenchRuleDialogState(
        fixedRule({
          rule_type: 'dual_composite_compare',
          target_variable_tag: '[items-composite]',
          reference_variable_tag: '[drops-composite]',
          key_check_mode: 'bidirectional',
          comparisons: [
            {
              comparison_id: 'cmp-1',
              left_field: 'Reward',
              operator: 'eq',
              right_field: 'Reward',
            },
          ],
          operator: undefined,
          expected_value: undefined,
        }),
        compositeVariables,
      ).form,
    ).toMatchObject({
      rule_entry_type: 'dual_composite',
      selected_rule: 'dual_composite_compare',
      reference_variable_tag: '[drops-composite]',
      key_check_mode: 'bidirectional',
    })

    expect(
      createEditWorkbenchRuleDialogState(
        fixedRule({
          rule_type: 'multi_composite_pipeline_check',
          target_variable_tag: '[items-composite]',
          pipeline_config: pipelineConfig(),
          operator: undefined,
          expected_value: undefined,
        }),
        compositeVariables,
      ).form,
    ).toMatchObject({
      rule_entry_type: 'multi_composite_pipeline',
      selected_rule: 'multi_composite_pipeline_check',
    })

    expect(
      createEditWorkbenchRuleDialogState(
        fixedRule({
          rule_type: 'multi_composite_mapping_check',
          target_variable_tag: '[items-composite]',
          mapping_config: mappingConfig(),
          operator: undefined,
          expected_value: undefined,
        }),
        compositeVariables,
      ).form,
    ).toMatchObject({
      rule_entry_type: 'multi_composite_mapping',
      selected_rule: 'multi_composite_mapping_check',
    })
  })

  it('returns existing warning copy for important invalid form states', () => {
    const emptyNameForm = createDefaultWorkbenchRuleFormState('group-a', '[items-id]')
    expect(validateWorkbenchRuleForm(validationInput(emptyNameForm))).toMatchObject({
      valid: false,
      message: '规则名称不能为空。',
    })

    const typeMismatchForm = {
      ...createDefaultWorkbenchRuleFormState('group-a', '[items-id]'),
      rule_name: 'Composite on single',
      rule_entry_type: 'composite' as const,
      selected_rule: 'composite_condition_check' as const,
    }
    expect(validateWorkbenchRuleForm(validationInput(typeMismatchForm))).toMatchObject({
      valid: false,
      message: '当前规则类型只能选择组合变量。',
    })

    const sequenceForm = {
      ...createDefaultWorkbenchRuleFormState('group-a', '[items-id]'),
      rule_name: 'Bad sequence',
      selected_rule: 'sequence_order_check' as const,
      sequence_step: '0',
    }
    expect(validateWorkbenchRuleForm(validationInput(sequenceForm))).toMatchObject({
      valid: false,
      message: '步长必须是大于 0 的合法数字。',
    })

    const mappingForm = {
      ...createDefaultWorkbenchRuleFormState('group-a', '[items-id]'),
      rule_name: 'Self mapping',
      selected_rule: 'in' as const,
      reference_variable_tag: '[items-id]',
    }
    expect(validateWorkbenchRuleForm(validationInput(mappingForm))).toMatchObject({
      valid: false,
      message: '基础字典变量不能与目标变量相同。',
    })

    const dualForm = {
      ...createDefaultWorkbenchRuleFormState('group-a', '[items-composite]'),
      rule_name: 'Same dual',
      rule_entry_type: 'dual_composite' as const,
      selected_rule: 'dual_composite_compare' as const,
      reference_variable_tag: '[items-composite]',
      left_key_field: KEY_FIELD,
      right_key_field: KEY_FIELD,
    }
    expect(validateWorkbenchRuleForm(validationInput(dualForm))).toMatchObject({
      valid: false,
      message: '同一组合变量筛选对比时，左右筛选条件都不能为空。',
    })

    const mappingRuleForm = {
      ...createDefaultWorkbenchRuleFormState('group-a', ''),
      rule_name: 'Bad mapping range',
      rule_entry_type: 'multi_composite_mapping' as const,
      selected_rule: 'multi_composite_mapping_check' as const,
    }
    expect(
      validateWorkbenchRuleForm(
        validationInput(mappingRuleForm, {
          mappingConfig: {
            nodes: [
              {
                node_id: 'mapping-node-1',
                variable_tag: '[items-composite]',
                filters: [
                  {
                    condition_id: 'mapping-filter-1',
                    field: 'Type',
                    operator: 'eq',
                    expected_value: 'A',
                    value_source: 'literal',
                    exclusion_ranges: [
                      {
                        range_id: 'mapping-range-1',
                        start_row: 4,
                        end_row: 3,
                        expected_value: 'A',
                      },
                    ],
                  },
                ],
              },
            ],
          },
        }),
      ),
    ).toMatchObject({
      valid: false,
      message: '映射节点 1 的筛选条件 1 的第 1 段排除范围：起始行号不能大于结束行号。',
    })
  })

  it('builds fixed rule payloads without changing existing wire semantics', () => {
    const common = {
      compositeConfig: compositeConfig(),
      dualComparisons: normalizeDualCompositeComparisons(undefined),
      dualLeftFilters: normalizeDualCompositeFilters(undefined),
      dualRightFilters: normalizeDualCompositeFilters(undefined),
      pipelineConfig: pipelineConfig(),
      mappingConfig: mappingConfig(),
      compositeFieldOptions: buildCompositeFieldOptions(compositeVariable),
      referenceCompositeFieldOptions: buildCompositeFieldOptions(referenceCompositeVariable),
      compositeVariables,
    }

    expect(
      buildWorkbenchRuleFromForm({
        ...common,
        form: {
          ...createDefaultWorkbenchRuleFormState('group-a', '[items-id]'),
          rule_id: 'rule-fixed',
          rule_name: 'ID > 0',
          selected_rule: 'gt',
          expected_value: '0',
        },
      }).rule,
    ).toEqual({
      rule_id: 'rule-fixed',
      group_id: 'group-a',
      rule_name: 'ID > 0',
      target_variable_tag: '[items-id]',
      display_field: '',
      rule_type: 'fixed_value_compare',
      operator: 'gt',
      expected_value: '0',
      expected_value_mode: undefined,
    })

    expect(
      buildWorkbenchRuleFromForm({
        ...common,
        form: {
          ...createDefaultWorkbenchRuleFormState('group-a', '[items-id]'),
          rule_name: 'ID regex',
          selected_rule: 'regex_check',
          expected_value: '^\\d+$',
        },
      }).rule,
    ).toMatchObject({ rule_type: 'regex_check', expected_value: '^\\d+$' })

    expect(
      buildWorkbenchRuleFromForm({
        ...common,
        form: {
          ...createDefaultWorkbenchRuleFormState('group-a', '[items-id]'),
          rule_name: 'ID in Name',
          selected_rule: 'in',
          reference_variable_tag: '[items-name]',
        },
      }).rule,
    ).toMatchObject({ rule_type: 'cross_table_mapping', reference_variable_tag: '[items-name]' })

    expect(
      buildWorkbenchRuleFromForm({
        ...common,
        form: {
          ...createDefaultWorkbenchRuleFormState('group-a', '[items-id]'),
          rule_name: 'ID sequence',
          selected_rule: 'sequence_order_check',
          sequence_direction: 'desc',
          sequence_step: '2',
          sequence_start_mode: 'manual',
          sequence_start_value: '10',
        },
      }).rule,
    ).toMatchObject({
      rule_type: 'sequence_order_check',
      sequence_direction: 'desc',
      sequence_step: '2',
      sequence_start_mode: 'manual',
      sequence_start_value: '10',
    })

    expect(
      buildWorkbenchRuleFromForm({
        ...common,
        form: {
          ...createDefaultWorkbenchRuleFormState('group-a', '[items-composite]'),
          rule_name: 'Composite branch',
          rule_entry_type: 'composite',
          selected_rule: 'composite_condition_check',
        },
      }).rule,
    ).toMatchObject({ rule_type: 'composite_condition_check', composite_config: compositeConfig() })

    expect(
      buildWorkbenchRuleFromForm({
        ...common,
        form: {
          ...createDefaultWorkbenchRuleFormState('group-a', '[items-composite]'),
          rule_name: 'Dual compare',
          rule_entry_type: 'dual_composite',
          selected_rule: 'dual_composite_compare',
          reference_variable_tag: '[drops-composite]',
        },
        dualComparisons: [
          {
            comparison_id: 'cmp-1',
            left_field: 'Reward',
            operator: 'eq',
            right_field: 'Reward',
          },
        ],
      }).rule,
    ).toMatchObject({
      rule_type: 'dual_composite_compare',
      reference_variable_tag: '[drops-composite]',
      comparisons: [{ comparison_id: 'cmp-1', left_field: 'Reward', operator: 'eq', right_field: 'Reward' }],
    })

    expect(
      buildWorkbenchRuleFromForm({
        ...common,
        form: {
          ...createDefaultWorkbenchRuleFormState('group-a', ''),
          rule_name: 'Pipeline',
          rule_entry_type: 'multi_composite_pipeline',
          selected_rule: 'multi_composite_pipeline_check',
        },
      }),
    ).toMatchObject({
      normalizedTargetTag: '[items-composite]',
      rule: { rule_type: 'multi_composite_pipeline_check', target_variable_tag: '[items-composite]' },
    })

    expect(
      buildWorkbenchRuleFromForm({
        ...common,
        form: {
          ...createDefaultWorkbenchRuleFormState('group-a', ''),
          rule_name: 'Mapping',
          rule_entry_type: 'multi_composite_mapping',
          selected_rule: 'multi_composite_mapping_check',
        },
      }),
    ).toMatchObject({
      normalizedTargetTag: '[items-composite]',
      rule: { rule_type: 'multi_composite_mapping_check', target_variable_tag: '[items-composite]' },
    })
  })

  it('keeps default names and list summaries stable', () => {
    const defaultName = buildDefaultRuleName({
      variable: singleVariable,
      selectedRule: 'gt',
      expectedValue: '0',
      variableMap,
    })
    expect(defaultName).toBe('items-ID-大于-0')

    const dualDefaultName = buildDefaultRuleName({
      variable: compositeVariable,
      selectedRule: 'dual_composite_compare',
      expectedValue: '',
      referenceVariableTag: '[items-composite]',
      variableMap,
      dualCompositeComparisons: [
        {
          comparison_id: 'cmp-1',
          left_field: 'Reward',
          operator: 'eq',
          right_field: 'Type',
        },
      ],
    })
    expect(dualDefaultName).toBe('同变量筛选对比-[items-composite]-Reward vs Type')

    const sequenceRule = fixedRule({
      rule_type: 'sequence_order_check',
      sequence_direction: 'desc',
      sequence_step: '2',
      sequence_start_mode: 'manual',
      sequence_start_value: '10',
      operator: undefined,
      expected_value: undefined,
    })
    expect(buildRuleCondition(sequenceRule, variableMap)).toBe(
      'ID 顺序校验（降序，步长 2，起始值 10）',
    )
    expect(buildRuleSelectionSummary(sequenceRule)).toBe('顺序校验（降序，步长 2，起始值 10）')
    expect(buildRuleVariableSummary(sequenceRule, variableMap)).toBe('src_items / items / ID')
    expect(buildRuleSourcePathSummary(sequenceRule, variableMap, sourceMap)).toBe(
      'C:/data/items.xlsx',
    )
    expect(
      buildRuleCompareValueSummary(
        fixedRule({ rule_type: 'cross_table_mapping', reference_variable_tag: '[items-name]' }),
        variableMap,
      ),
    ).toBe('[items-name]')
  })
})

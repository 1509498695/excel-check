import { describe, expect, it } from 'vitest'

import type {
  CompositeRuleConfig,
  FixedRuleDefinition,
} from '../../src/types/fixedRules'
import type { VariableTag } from '../../src/types/workbench'
import { orchestrationRulesToValidationRules } from '../../src/utils/workbenchOrchestrationRules'

const variables: VariableTag[] = [
  {
    tag: '[items-id]',
    source_id: 'src_items',
    sheet: 'items',
    variable_kind: 'single',
    column: 'ID',
  },
  {
    tag: '[items-name]',
    source_id: 'src_items',
    sheet: 'items',
    variable_kind: 'single',
    column: 'Name',
  },
  {
    tag: '[items-composite-a]',
    source_id: 'src_items',
    sheet: 'items',
    variable_kind: 'composite',
    columns: ['ID', 'Name'],
    key_column: 'ID',
  },
  {
    tag: '[items-composite-b]',
    source_id: 'src_items',
    sheet: 'items',
    variable_kind: 'composite',
    columns: ['ID', 'Name'],
    key_column: 'ID',
  },
]

function rule(base: Partial<FixedRuleDefinition>): FixedRuleDefinition {
  return {
    rule_id: base.rule_id ?? 'rule',
    group_id: base.group_id ?? 'group',
    rule_name: base.rule_name ?? 'Rule',
    target_variable_tag: base.target_variable_tag ?? '[items-id]',
    rule_type: base.rule_type ?? 'not_null',
    ...base,
  }
}

describe('orchestrationRulesToValidationRules', () => {
  it('maps single-variable rule params with stable locations', () => {
    const validationRules = orchestrationRulesToValidationRules(variables, [
      rule({
        rule_id: 'fixed',
        rule_name: 'ID > 0',
        rule_type: 'fixed_value_compare',
        operator: 'gt',
        expected_value: '0',
        display_field: 'ID',
      }),
      rule({
        rule_id: 'regex',
        rule_name: 'Name format',
        target_variable_tag: '[items-name]',
        rule_type: 'regex_check',
        expected_value: '^[A-Za-z]+$',
      }),
      rule({
        rule_id: 'cross',
        rule_name: 'ID in names',
        rule_type: 'cross_table_mapping',
        reference_variable_tag: '[items-name]',
      }),
      rule({
        rule_id: 'sequence',
        rule_name: 'ID asc',
        rule_type: 'sequence_order_check',
        sequence_direction: 'asc',
        sequence_step: '1',
        sequence_start_mode: 'manual',
        sequence_start_value: '1',
      }),
    ])

    expect(validationRules[0].params).toMatchObject({
      target_tag: '[items-id]',
      operator: 'gt',
      expected_value: '0',
      rule_name: 'ID > 0',
      location: 'items -> ID',
      display_field: 'ID',
    })
    expect(validationRules[1].params).toMatchObject({
      target_tag: '[items-name]',
      pattern: '^[A-Za-z]+$',
      location: 'items -> Name',
    })
    expect(validationRules[2].params).toMatchObject({
      dict_tag: '[items-name]',
      target_tag: '[items-id]',
    })
    expect(validationRules[3].params).toMatchObject({
      direction: 'asc',
      step: '1',
      start_mode: 'manual',
      start_value: '1',
    })
  })

  it('deep copies composite config and maps node-driven rules from first node', () => {
    const compositeConfig: CompositeRuleConfig = {
      global_filters: [],
      branches: [
        {
          branch_id: 'branch-a',
          filters: [],
          assertions: [
            {
              condition_id: 'assert-a',
              field: 'Name',
              operator: 'not_null',
            },
          ],
        },
      ],
    }

    const validationRules = orchestrationRulesToValidationRules(variables, [
      rule({
        rule_id: 'composite',
        rule_type: 'composite_condition_check',
        target_variable_tag: '[items-composite-a]',
        composite_config: compositeConfig,
      }),
      rule({
        rule_id: 'pipeline',
        rule_type: 'multi_composite_pipeline_check',
        target_variable_tag: '',
        pipeline_config: {
          nodes: [
            {
              node_id: 'node-a',
              variable_tag: '[items-composite-a]',
              filters: [],
              assertions: [],
            },
          ],
        },
      }),
      rule({
        rule_id: 'mapping',
        rule_type: 'multi_composite_mapping_check',
        target_variable_tag: '',
        mapping_config: {
          nodes: [
            {
              node_id: 'node-b',
              variable_tag: '[items-composite-b]',
              filters: [],
            },
          ],
        },
      }),
    ])

    expect(validationRules[0].params.composite_config).toEqual(compositeConfig)
    expect(validationRules[0].params.composite_config).not.toBe(compositeConfig)
    compositeConfig.branches[0].assertions[0].field = 'ID'
    expect(
      (
        validationRules[0].params.composite_config as CompositeRuleConfig
      ).branches[0].assertions[0].field,
    ).toBe('Name')

    expect(validationRules[1].params).toMatchObject({
      target_tag: '[items-composite-a]',
      pipeline_config: {
        nodes: [{ variable_tag: '[items-composite-a]' }],
      },
    })
    expect(validationRules[2].params).toMatchObject({
      target_tag: '[items-composite-b]',
      mapping_config: {
        nodes: [{ variable_tag: '[items-composite-b]' }],
      },
    })
  })
})

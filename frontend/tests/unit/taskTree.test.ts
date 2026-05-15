import { describe, expect, it } from 'vitest'

import type { DataSource, ValidationRule, VariableTag } from '../../src/types/workbench'
import { buildTaskTreePayload } from '../../src/utils/taskTree'

const localSource: DataSource = {
  id: 'src_items',
  type: 'local_excel',
  pathOrUrl: 'C:/data/items.xlsx',
}

const variables: VariableTag[] = [
  {
    tag: '[items-id]',
    source_id: 'src_items',
    sheet: 'items',
    variable_kind: 'single',
    column: 'ID',
    expected_type: 'int',
  },
  {
    tag: '[items-name]',
    source_id: 'src_items',
    sheet: 'items',
    variable_kind: 'single',
    column: 'Name',
    expected_type: 'str',
  },
  {
    tag: '[items-composite]',
    source_id: 'src_items',
    sheet: 'items',
    variable_kind: 'composite',
    columns: ['ID', 'Name'],
    key_column: 'ID',
  },
]

describe('buildTaskTreePayload', () => {
  it('normalizes sources, variables, rules, selected ids, and paging', () => {
    const rules: ValidationRule[] = [
      {
        rule_id: 'rule-fixed',
        rule_type: 'fixed_value_compare',
        params: {
          target_tag: ' [items-id] ',
          operator: 'gt',
          expected_value: ' 0 ',
          rule_name: ' ID > 0 ',
          location: ' items -> ID ',
        },
      },
      {
        rule_id: 'rule-regex',
        rule_type: 'regex_check',
        params: {
          target_tag: '[items-name]',
          pattern: ' ^[A-Za-z]+$ ',
          rule_name: ' Name format ',
        },
      },
      {
        rule_id: 'rule-cross',
        rule_type: 'cross_table_mapping',
        params: {
          dict_tag: '[items-name]',
          target_tag: '[items-id]',
          rule_name: 'ID in dict',
        },
      },
      {
        rule_id: 'rule-pipeline',
        rule_type: 'multi_composite_pipeline_check',
        params: {
          target_tag: '[items-composite]',
          rule_name: 'Pipeline',
          pipeline_config: { nodes: [{ node_id: 'n1', variable_tag: '[items-composite]' }] },
        },
      },
      {
        rule_id: 'rule-dynamic',
        rule_type: 'not_null',
        mode: 'dynamic',
        params: { target_tags: ['[items-id]'] },
      },
    ]

    const payload = buildTaskTreePayload(
      [localSource],
      variables,
      rules,
      [' rule-fixed ', 'rule-fixed', 'rule-regex'],
      2,
      50,
    )

    expect(payload.sources).toEqual([
      {
        id: 'src_items',
        type: 'local_excel',
        path: 'C:/data/items.xlsx',
        pathOrUrl: 'C:/data/items.xlsx',
      },
    ])
    expect(payload.variables[2]).toMatchObject({
      tag: '[items-composite]',
      variable_kind: 'composite',
      expected_type: 'json',
    })
    expect(payload.rules.map((rule) => rule.rule_id)).toEqual([
      'rule-fixed',
      'rule-regex',
      'rule-cross',
      'rule-pipeline',
    ])
    expect(payload.rules[0].params).toMatchObject({
      target_tag: '[items-id]',
      operator: 'gt',
      expected_value: '0',
      rule_name: 'ID > 0',
      location: 'items -> ID',
    })
    expect(payload.selected_rule_ids).toEqual(['rule-fixed', 'rule-regex'])
    expect(payload.page).toBe(2)
    expect(payload.size).toBe(50)
  })

  it('rejects duplicate sources, unknown variable references, and invalid composite keys', () => {
    expect(() =>
      buildTaskTreePayload(
        [localSource, { ...localSource }],
        variables,
        [],
      ),
    ).toThrow('数据源标识 "src_items" 重复')

    expect(() =>
      buildTaskTreePayload([localSource], variables, [
        {
          rule_id: 'rule-missing',
          rule_type: 'fixed_value_compare',
          params: {
            target_tag: '[missing]',
            operator: 'gt',
            expected_value: '1',
            rule_name: 'Missing',
          },
        },
      ]),
    ).toThrow('引用了不存在的变量 "[missing]"')

    expect(() =>
      buildTaskTreePayload(
        [localSource],
        [
          {
            tag: '[bad-composite]',
            source_id: 'src_items',
            sheet: 'items',
            variable_kind: 'composite',
            columns: ['ID', 'Name'],
            key_column: 'Missing',
          },
        ],
        [],
      ),
    ).toThrow('key_column 必须包含在 columns 中')
  })
})

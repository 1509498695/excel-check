import { describe, expect, it } from 'vitest'

import type { FixedRuleDefinition } from '../../src/types/fixedRules'
import type { AiRuleDraftPayload } from '../../src/types/ai'
import type { DataSource, VariableTag } from '../../src/types/workbench'
import {
  buildAiDraftPreviewTaskTreePayload,
  getAiDraftRulesToApply,
} from '../../src/utils/aiDraftWorkflow'

const existingSources: DataSource[] = [
  {
    id: 'src_existing',
    type: 'local_excel',
    pathOrUrl: 'C:/old/items.xlsx',
  },
  {
    id: 'src_unused',
    type: 'local_excel',
    pathOrUrl: 'C:/old/unused.xlsx',
  },
]

const existingVariables: VariableTag[] = [
  {
    tag: '[existing-id]',
    source_id: 'src_existing',
    sheet: 'items',
    variable_kind: 'single',
    column: 'ID',
    expected_type: 'int',
  },
  {
    tag: '[unused-name]',
    source_id: 'src_unused',
    sheet: 'unused',
    variable_kind: 'single',
    column: 'Name',
    expected_type: 'str',
  },
]

function fixedRule(overrides: Partial<FixedRuleDefinition>): FixedRuleDefinition {
  return {
    rule_id: overrides.rule_id ?? 'rule',
    group_id: overrides.group_id ?? 'group',
    rule_name: overrides.rule_name ?? 'Rule',
    target_variable_tag: overrides.target_variable_tag ?? '[existing-id]',
    rule_type: overrides.rule_type ?? 'fixed_value_compare',
    operator: overrides.operator ?? 'gt',
    expected_value: overrides.expected_value ?? '0',
    ...overrides,
  }
}

describe('AI draft workflow helpers', () => {
  it('builds a preview TaskTree from merged draft sources and referenced variables only', () => {
    const draft: AiRuleDraftPayload = {
      sources_to_add: [
        {
          id: 'src_existing',
          type: 'local_excel',
          pathOrUrl: 'C:/new/items.xlsx',
        },
        {
          id: 'src_added',
          type: 'local_excel',
          pathOrUrl: 'C:/new/added.xlsx',
        },
      ],
      variables_to_add: [
        {
          tag: '[existing-id]',
          source_id: 'src_existing',
          sheet: 'items',
          variable_kind: 'single',
          column: 'ID2',
          expected_type: 'int',
        },
        {
          tag: '[added-composite]',
          source_id: 'src_added',
          sheet: 'items',
          variable_kind: 'composite',
          columns: ['ID', 'Name'],
          key_column: 'ID',
          expected_type: 'json',
        },
        {
          tag: '[mapping-composite]',
          source_id: 'src_added',
          sheet: 'items',
          variable_kind: 'composite',
          columns: ['ID', 'Name'],
          key_column: 'ID',
          expected_type: 'json',
        },
      ],
      rules_to_add: [
        fixedRule({ rule_id: 'fixed-existing', target_variable_tag: '[existing-id]' }),
        fixedRule({
          rule_id: 'pipeline-added',
          target_variable_tag: '',
          rule_type: 'multi_composite_pipeline_check',
          operator: undefined,
          expected_value: undefined,
          pipeline_config: {
            nodes: [
              {
                node_id: 'node-a',
                variable_tag: '[added-composite]',
                filters: [],
                assertions: [],
              },
            ],
          },
        }),
        fixedRule({
          rule_id: 'mapping-added',
          target_variable_tag: '',
          rule_type: 'multi_composite_mapping_check',
          operator: undefined,
          expected_value: undefined,
          mapping_config: {
            nodes: [
              {
                node_id: 'node-b',
                variable_tag: '[mapping-composite]',
                filters: [],
              },
            ],
          },
        }),
      ],
      reuse_variable_tags: ['[existing-id]'],
    }

    const payload = buildAiDraftPreviewTaskTreePayload(
      existingSources,
      existingVariables,
      draft,
      25,
    )

    expect(payload.sources).toEqual([
      {
        id: 'src_existing',
        type: 'local_excel',
        path: 'C:/new/items.xlsx',
        pathOrUrl: 'C:/new/items.xlsx',
      },
      {
        id: 'src_added',
        type: 'local_excel',
        path: 'C:/new/added.xlsx',
        pathOrUrl: 'C:/new/added.xlsx',
      },
    ])
    expect(payload.variables.map((variable) => variable.tag)).toEqual([
      '[existing-id]',
      '[added-composite]',
      '[mapping-composite]',
    ])
    expect(payload.variables[0]).toMatchObject({ column: 'ID2' })
    expect(payload.rules.map((rule) => rule.rule_id)).toEqual([
      'fixed-existing',
      'pipeline-added',
      'mapping-added',
    ])
    expect(payload.selected_rule_ids).toEqual([
      'fixed-existing',
      'pipeline-added',
      'mapping-added',
    ])
    expect(payload.page).toBe(1)
    expect(payload.size).toBe(25)
  })

  it('filters duplicate draft rules before applying them', () => {
    const existingRule = fixedRule({
      rule_id: 'existing-rule',
      rule_name: 'Existing rule',
    })
    const duplicateCandidate = fixedRule({
      rule_id: 'duplicate-candidate',
      rule_name: 'Different generated name',
    })
    const newCandidate = fixedRule({
      rule_id: 'new-candidate',
      rule_type: 'unique',
      operator: undefined,
      expected_value: undefined,
    })

    expect(getAiDraftRulesToApply([existingRule], [duplicateCandidate, newCandidate])).toEqual([
      newCandidate,
    ])
    expect(getAiDraftRulesToApply([existingRule], [duplicateCandidate])).toEqual([])
  })
})

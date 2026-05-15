import { describe, expect, it } from 'vitest'

import type { VariableTag } from '../../src/types/workbench'
import {
  applyAiRuleTemplate,
  getAiRuleTemplates,
  getAvailableAiRuleTemplates,
  getRecommendedAiRuleTemplates,
} from '../../src/utils/aiRuleTemplates'

const singleId: VariableTag = {
  tag: '[items-id]',
  source_id: 'src_items',
  sheet: 'items',
  variable_kind: 'single',
  column: 'ID',
}

const singleName: VariableTag = {
  tag: '[items-name]',
  source_id: 'src_items',
  sheet: 'items',
  variable_kind: 'single',
  column: 'Name',
}

const singleStatus: VariableTag = {
  tag: '[items-status]',
  source_id: 'src_items',
  sheet: 'items',
  variable_kind: 'single',
  column: 'Status',
  expected_type: 'int',
}

const compositeA: VariableTag = {
  tag: '[reward-a]',
  source_id: 'src_reward',
  sheet: 'reward',
  variable_kind: 'composite',
  key_column: 'INT_Level',
  columns: ['INT_Level', 'INT_Index', 'INT_Count', 'STR_Name'],
}

const compositeB: VariableTag = {
  tag: '[reward-b]',
  source_id: 'src_reward',
  sheet: 'reward',
  variable_kind: 'composite',
  key_column: 'INT_Level',
  columns: ['INT_Level', 'INT_Index', 'INT_Count', 'STR_Name'],
}

describe('aiRuleTemplates', () => {
  it('filters and applies single-variable templates with target hints', () => {
    const templates = getAvailableAiRuleTemplates({
      selectedVariables: [singleId],
      allowAutoComplete: false,
    })

    expect(templates.map((item) => item.id)).toEqual(
      expect.arrayContaining([
        'single-not-null',
        'single-unique',
        'single-fixed-set',
        'single-regex',
        'single-sequence',
      ]),
    )
    expect(templates.map((item) => item.id)).not.toContain('auto-complete-source-variable')

    const result = applyAiRuleTemplate('single-fixed-set', templates, [singleId])

    expect(result.description).toContain('ID')
    expect(result.workflowHints).toMatchObject({
      rule_type_hint: 'fixed_value_compare',
      target_variable_tag: '[items-id]',
      source_id: 'src_items',
      sheet: 'items',
      target_field: 'ID',
      operator: 'eq',
      expected_value: '0,1,2',
      expected_value_mode: 'set',
    })
    expect(result.allowAutoComplete).toBe(false)
  })

  it('applies cross-table templates with a reference variable', () => {
    const templates = getAvailableAiRuleTemplates({
      selectedVariables: [singleId, singleName],
      allowAutoComplete: false,
    })

    const result = applyAiRuleTemplate('single-cross-table-mapping', templates, [
      singleId,
      singleName,
    ])

    expect(result.description).toContain('[items-name]')
    expect(result.workflowHints).toMatchObject({
      rule_type_hint: 'cross_table_mapping',
      target_variable_tag: '[items-id]',
      reference_variable_tag: '[items-name]',
      target_field: 'ID',
      reference_field: 'Name',
    })
  })

  it('filters and applies composite templates with key and member fields', () => {
    const templates = getAvailableAiRuleTemplates({
      selectedVariables: [compositeA],
      allowAutoComplete: false,
    })

    expect(templates.map((item) => item.id)).toContain('composite-condition-not-null')

    const result = applyAiRuleTemplate('composite-condition-not-null', templates, [compositeA])

    expect(result.description).toContain('INT_Index')
    expect(result.workflowHints).toMatchObject({
      rule_type_hint: 'composite_condition_check',
      target_variable_tag: '[reward-a]',
      key_column: 'INT_Level',
      composite_columns: ['INT_Level', 'INT_Index', 'INT_Count', 'STR_Name'],
      filter_field: 'INT_Index',
      assertion_field: 'INT_Count',
      assertion_operator: 'not_null',
    })
  })

  it('applies dual-composite templates with left/right variables and keys', () => {
    const templates = getAvailableAiRuleTemplates({
      selectedVariables: [compositeA, compositeB],
      allowAutoComplete: false,
    })

    const result = applyAiRuleTemplate('dual-composite-compare', templates, [
      compositeA,
      compositeB,
    ])

    expect(result.workflowHints).toMatchObject({
      rule_type_hint: 'dual_composite_compare',
      left_variable_tag: '[reward-a]',
      right_variable_tag: '[reward-b]',
      left_key_field: 'INT_Level',
      right_key_field: 'INT_Level',
      left_filter_field: 'INT_Index',
      right_filter_field: 'INT_Index',
      compare_fields: ['INT_Index', 'INT_Count'],
    })
  })

  it('shows auto-complete templates when enabled without selected variables', () => {
    const templates = getAvailableAiRuleTemplates({
      selectedVariables: [],
      allowAutoComplete: true,
    })

    const result = applyAiRuleTemplate('auto-complete-source-variable', templates, [])

    expect(templates.map((item) => item.id)).toContain('auto-complete-source-variable')
    expect(result.allowAutoComplete).toBe(true)
    expect(result.workflowHints).toMatchObject({
      rule_type_hint: 'composite_condition_check',
      filter_operator: 'eq',
      assertion_operator: 'not_null',
    })
  })

  it('returns cloned templates and hints so applying a template cannot mutate the catalog', () => {
    const [template] = getAiRuleTemplates()
    const result = applyAiRuleTemplate(template.id, [template], [singleId])

    result.workflowHints.rule_type_hint = 'unique'

    const [freshTemplate] = getAiRuleTemplates()
    expect(freshTemplate.workflowHints.rule_type_hint).toBe('not_null')
    expect(freshTemplate.workflowHints).not.toBe(template.workflowHints)
  })

  it('recommends identity-field rules from a selected single variable', () => {
    const recommendations = getRecommendedAiRuleTemplates([singleId])
    const ids = recommendations.map((item) => item.id)

    expect(ids).toEqual(
      expect.arrayContaining([
        'recommended-single-not-null-items-id',
        'recommended-single-unique-items-id',
        'recommended-single-regex-items-id',
      ]),
    )

    const unique = recommendations.find((item) => item.id === 'recommended-single-unique-items-id')
    expect(unique?.recommendReason).toContain('ID')
    expect(unique?.workflowHints).toMatchObject({
      rule_type_hint: 'unique',
      target_variable_tag: '[items-id]',
      target_field: 'ID',
    })
  })

  it('prioritizes enum and numeric recommendations from field names and expected type', () => {
    const recommendations = getRecommendedAiRuleTemplates([singleStatus])
    const fixed = recommendations.find((item) => item.id === 'recommended-single-fixed-set-items-status')
    const sequence = recommendations.find((item) => item.id === 'recommended-single-sequence-items-status')

    expect(fixed?.descriptionTemplate).toContain('0,1')
    expect(fixed?.workflowHints).toMatchObject({
      rule_type_hint: 'fixed_value_compare',
      expected_value_mode: 'set',
      expected_value: '0,1',
    })
    expect(sequence?.workflowHints).toMatchObject({
      rule_type_hint: 'sequence_order_check',
      sequence_direction: 'asc',
      sequence_step: '1',
    })
  })

  it('recommends cross-table mapping from two single variables', () => {
    const recommendations = getRecommendedAiRuleTemplates([singleId, singleName])
    const mapping = recommendations.find((item) => item.id === 'recommended-cross-items-id-items-name')

    expect(mapping?.descriptionTemplate).toContain('[items-name]')
    expect(mapping?.workflowHints).toMatchObject({
      rule_type_hint: 'cross_table_mapping',
      target_variable_tag: '[items-id]',
      reference_variable_tag: '[items-name]',
      reference_field: 'Name',
    })
  })

  it('recommends composite condition without using the key as default assertion field', () => {
    const recommendations = getRecommendedAiRuleTemplates([compositeA])
    const composite = recommendations.find((item) => item.id === 'recommended-composite-condition-reward-a')

    expect(composite?.workflowHints).toMatchObject({
      rule_type_hint: 'composite_condition_check',
      target_variable_tag: '[reward-a]',
      key_column: 'INT_Level',
      filter_field: 'INT_Index',
      assertion_field: 'INT_Count',
    })
    expect(composite?.workflowHints.assertion_field).not.toBe('INT_Level')
  })

  it('recommends dual and multi-composite rules from shared keys and columns', () => {
    const recommendations = getRecommendedAiRuleTemplates([compositeA, compositeB])
    const dual = recommendations.find((item) => item.id === 'recommended-dual-composite-reward-a-reward-b')
    const pipeline = recommendations.find((item) => item.id === 'recommended-multi-pipeline-reward-a-reward-b')
    const mapping = recommendations.find((item) => item.id === 'recommended-multi-mapping-reward-a-reward-b')

    expect(dual?.workflowHints).toMatchObject({
      rule_type_hint: 'dual_composite_compare',
      left_variable_tag: '[reward-a]',
      right_variable_tag: '[reward-b]',
      left_key_field: 'INT_Level',
      right_key_field: 'INT_Level',
      compare_fields: ['INT_Index', 'INT_Count', 'STR_Name'],
    })
    expect(pipeline?.workflowHints.pipeline_nodes).toHaveLength(2)
    expect(mapping?.workflowHints.mapping_nodes).toHaveLength(2)
  })

  it('applies recommended cards from their own embedded hints and returns clones', () => {
    const recommendations = getRecommendedAiRuleTemplates([compositeA, compositeB])
    const result = applyAiRuleTemplate(
      'recommended-dual-composite-reward-a-reward-b',
      recommendations,
      [],
    )

    expect(result.description).toContain('[reward-a]')
    expect(result.workflowHints).toMatchObject({
      rule_type_hint: 'dual_composite_compare',
      left_variable_tag: '[reward-a]',
      right_variable_tag: '[reward-b]',
    })

    result.workflowHints.compare_fields = ['Changed']
    const fresh = getRecommendedAiRuleTemplates([compositeA, compositeB]).find(
      (item) => item.id === 'recommended-dual-composite-reward-a-reward-b',
    )
    expect(fresh?.workflowHints.compare_fields).toEqual(['INT_Index', 'INT_Count', 'STR_Name'])
  })
})

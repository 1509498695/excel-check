/**
 * 将工作台步骤 3 的 FixedRuleDefinition 列表映射为引擎 TaskTree 所需的 ValidationRule。
 * 字段形状与后端 fixed_rules/service._build_fixed_rule_params 及 rule_fixed 执行器一致。
 */

import type { FixedRuleDefinition } from '../types/fixedRules'
import type { ValidationRule, VariableTag } from '../types/workbench'

function locationForSingle(variable: VariableTag): string {
  const column = variable.column?.trim() ?? ''
  return `${variable.sheet} -> ${column}`
}

export function orchestrationRulesToValidationRules(
  variables: VariableTag[],
  rules: FixedRuleDefinition[],
): ValidationRule[] {
  const variableMap = new Map(variables.map((v) => [v.tag, v] as const))

  return rules.map((rule) => {
    const variable = variableMap.get(rule.target_variable_tag.trim())
    if (!variable) {
      return {
        rule_id: rule.rule_id,
        rule_type: rule.rule_type,
        params: {},
      }
    }

    if (rule.rule_type === 'composite_condition_check') {
      return {
        rule_id: rule.rule_id,
        rule_type: 'composite_condition_check',
        params: {
          target_tag: variable.tag,
          rule_name: rule.rule_name,
          composite_config: rule.composite_config
            ? JSON.parse(JSON.stringify(rule.composite_config))
            : undefined,
        },
      }
    }

    if (rule.rule_type === 'fixed_value_compare') {
      return {
        rule_id: rule.rule_id,
        rule_type: 'fixed_value_compare',
        params: {
          target_tag: variable.tag,
          operator: rule.operator ?? 'gt',
          expected_value: rule.expected_value ?? '',
          rule_name: rule.rule_name,
          location: locationForSingle(variable),
        },
      }
    }

    return {
      rule_id: rule.rule_id,
      rule_type: rule.rule_type,
      params: {
        target_tags: [variable.tag],
        rule_name: rule.rule_name,
        location: locationForSingle(variable),
      },
    }
  })
}

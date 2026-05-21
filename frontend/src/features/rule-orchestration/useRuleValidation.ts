import { invalid, parseExpectedValueSet, valid, type RuleValidationResult } from '../../rules'

export function validateRequiredText(value: string, message: string): RuleValidationResult {
  return value.trim() ? valid() : invalid(message)
}

export function validateRuleSetValue(value: string): RuleValidationResult {
  return parseExpectedValueSet(value).length > 0
    ? valid()
    : invalid('规则集至少需要填写一个固定值。')
}

export function useRuleValidation() {
  return {
    validateRequiredText,
    validateRuleSetValue,
  }
}

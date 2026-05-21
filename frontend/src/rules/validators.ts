export interface RuleValidationResult {
  ok: boolean
  message: string
}

export function valid(): RuleValidationResult {
  return { ok: true, message: '' }
}

export function invalid(message: string): RuleValidationResult {
  return { ok: false, message }
}

export function parseExpectedValueSet(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

export function validatePositiveNumber(value: string, message: string): RuleValidationResult {
  if (!value.trim() || Number.isNaN(Number(value)) || Number(value) <= 0) {
    return invalid(message)
  }
  return valid()
}

export function validateNumber(value: string, message: string): RuleValidationResult {
  if (!value.trim() || Number.isNaN(Number(value))) {
    return invalid(message)
  }
  return valid()
}

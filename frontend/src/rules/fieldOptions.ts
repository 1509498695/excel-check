import type { VariableTag } from '../types/workbench'
import { KEY_FIELD } from './constants'

export interface FieldOption {
  label: string
  value: string
}

export function buildCompositeFieldOptions(variable: VariableTag | null): FieldOption[] {
  if (!variable || (variable.variable_kind ?? 'single') !== 'composite') {
    return []
  }

  const keyColumn = variable.key_column ?? ''
  const options: FieldOption[] = [
    {
      label: keyColumn ? `${keyColumn} (内部 Key)` : 'Key(映射键)',
      value: KEY_FIELD,
    },
  ]
  if (keyColumn.trim()) {
    options.push({ label: `${keyColumn} (原始列)`, value: keyColumn })
  }
  ;(variable.columns ?? [])
    .filter((column) => column && column !== keyColumn)
    .forEach((column) => options.push({ label: column, value: column }))

  return options
}

export function buildDisplayFieldOptions(variable: VariableTag | null): FieldOption[] {
  if (!variable) {
    return []
  }
  if ((variable.variable_kind ?? 'single') === 'composite') {
    return buildCompositeFieldOptions(variable)
  }
  const column = variable.column?.trim()
  return column ? [{ label: column, value: column }] : []
}

export function resolveFieldOptionValue(
  options: FieldOption[],
  requestedValue: string | undefined,
): string | null {
  const rawValue = requestedValue ?? ''
  if (options.some((option) => option.value === rawValue)) {
    return rawValue
  }
  const normalizedValue = rawValue.trim()
  if (!normalizedValue) {
    return null
  }
  const matchedOptions = options.filter((option) => option.value.trim() === normalizedValue)
  return matchedOptions.length === 1 ? matchedOptions[0].value : null
}

export function getCompositeFieldLabel(field: string, variable: VariableTag | null): string {
  const options = buildCompositeFieldOptions(variable)
  const resolvedField = resolveFieldOptionValue(options, field)
  const matchedOption = options.find((option) => option.value === resolvedField)
  if (matchedOption) {
    return matchedOption.label
  }
  return field === KEY_FIELD ? `${variable?.key_column || 'Key'} (Key)` : field
}

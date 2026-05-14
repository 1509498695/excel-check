import type { FixedRuleDefinition } from '../types/fixedRules'

const GENERATED_KEYS = new Set([
  'rule_id',
  'rule_name',
  'group_id',
  'display_field',
  'condition_id',
  'branch_id',
  'comparison_id',
  'node_id',
  'range_id',
  'check_id',
])

type JsonLike = null | boolean | number | string | JsonLike[] | { [key: string]: JsonLike }

function normalizeValue(value: unknown): JsonLike | undefined {
  if (value === undefined || value === null) {
    return undefined
  }
  if (typeof value === 'string') {
    return value.trim()
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return value
  }
  if (Array.isArray(value)) {
    return value
      .map((item) => normalizeValue(item))
      .filter((item): item is JsonLike => item !== undefined)
      .sort((left, right) => JSON.stringify(left).localeCompare(JSON.stringify(right)))
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
      .filter(([key]) => !GENERATED_KEYS.has(key))
      .map(([key, item]) => [key, normalizeValue(item)] as const)
      .filter((entry): entry is readonly [string, JsonLike] => entry[1] !== undefined)
      .sort(([left], [right]) => left.localeCompare(right))

    const normalized: Record<string, JsonLike> = {}
    entries.forEach(([key, item]) => {
      normalized[key] = item
    })
    return normalized
  }
  return String(value).trim()
}

export function getFixedRuleFingerprint(rule: FixedRuleDefinition): string {
  return JSON.stringify(normalizeValue(rule) ?? {})
}

export function getFixedRuleDuplicateSet(
  existingRules: FixedRuleDefinition[],
  candidateRules: FixedRuleDefinition[],
): Set<string> {
  const existingFingerprints = new Set(existingRules.map(getFixedRuleFingerprint))
  const seenCandidateFingerprints = new Set<string>()
  const duplicateIds = new Set<string>()

  candidateRules.forEach((rule) => {
    const fingerprint = getFixedRuleFingerprint(rule)
    if (existingFingerprints.has(fingerprint) || seenCandidateFingerprints.has(fingerprint)) {
      duplicateIds.add(rule.rule_id)
      return
    }
    seenCandidateFingerprints.add(fingerprint)
  })

  return duplicateIds
}

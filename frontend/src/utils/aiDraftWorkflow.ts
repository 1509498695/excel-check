import type { FixedRuleDefinition } from '../types/fixedRules'
import type { AiRuleDraftPayload } from '../types/ai'
import type { DataSource, TaskTree, VariableTag } from '../types/workbench'
import { getFixedRuleDuplicateSet } from './ruleFingerprint'
import { buildTaskTreePayload } from './taskTree'
import { orchestrationRulesToValidationRules } from './workbenchOrchestrationRules'

function upsertSourceSnapshot(sources: DataSource[], source: DataSource): void {
  const index = sources.findIndex((item) => item.id === source.id)
  const nextSource = { ...source }
  if (index >= 0) {
    sources.splice(index, 1, { ...sources[index], ...nextSource })
    return
  }
  sources.push(nextSource)
}

function upsertVariableSnapshot(variables: VariableTag[], variable: VariableTag): void {
  const index = variables.findIndex((item) => item.tag === variable.tag)
  const nextVariable = { ...variable }
  if (index >= 0) {
    variables.splice(index, 1, { ...variables[index], ...nextVariable })
    return
  }
  variables.push(nextVariable)
}

function collectRuleDependencyTags(rule: FixedRuleDefinition): string[] {
  const tags = new Set<string>()

  if (rule.target_variable_tag?.trim()) {
    tags.add(rule.target_variable_tag.trim())
  }
  if (rule.reference_variable_tag?.trim()) {
    tags.add(rule.reference_variable_tag.trim())
  }
  rule.pipeline_config?.nodes.forEach((node) => {
    if (node.variable_tag.trim()) {
      tags.add(node.variable_tag.trim())
    }
  })
  rule.mapping_config?.nodes.forEach((node) => {
    if (node.variable_tag.trim()) {
      tags.add(node.variable_tag.trim())
    }
  })

  return [...tags]
}

export function getAiDraftRulesToApply(
  existingRules: FixedRuleDefinition[],
  candidateRules: FixedRuleDefinition[],
): FixedRuleDefinition[] {
  const duplicateIds = getFixedRuleDuplicateSet(existingRules, candidateRules)
  return candidateRules.filter((rule) => !duplicateIds.has(rule.rule_id))
}

export function buildAiDraftPreviewTaskTreePayload(
  sources: DataSource[],
  variables: VariableTag[],
  draft: AiRuleDraftPayload,
  pageSize: number,
): TaskTree {
  const combinedSources = sources.map((source) => ({ ...source }))
  const combinedVariables = variables.map((variable) => ({ ...variable }))

  draft.sources_to_add.forEach((source) => {
    upsertSourceSnapshot(combinedSources, source)
  })
  draft.variables_to_add.forEach((variable) => {
    upsertVariableSnapshot(combinedVariables, variable)
  })

  const requiredTags = new Set<string>()
  draft.rules_to_add.forEach((rule) => {
    collectRuleDependencyTags(rule).forEach((tag) => requiredTags.add(tag))
  })

  const previewVariables = combinedVariables.filter((variable) => requiredTags.has(variable.tag))
  const requiredSourceIds = new Set(previewVariables.map((variable) => variable.source_id))
  const previewSources = combinedSources.filter((source) => requiredSourceIds.has(source.id))
  const previewRuleIds = draft.rules_to_add.map((rule) => rule.rule_id).filter(Boolean)
  const validationRules = orchestrationRulesToValidationRules(previewVariables, draft.rules_to_add)

  return buildTaskTreePayload(
    previewSources,
    previewVariables,
    validationRules,
    previewRuleIds,
    1,
    pageSize,
  )
}

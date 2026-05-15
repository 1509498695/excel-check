import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { createServer } from 'vite'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(scriptDir, '..')
const repoRoot = path.resolve(frontendRoot, '..')
const goldenPath = path.join(repoRoot, 'contracts', 'rule_params_golden.json')

function stableRules(rules) {
  return JSON.parse(JSON.stringify(rules)).sort((left, right) =>
    left.rule_id.localeCompare(right.rule_id),
  )
}

function ruleMap(rules) {
  return new Map(rules.map((rule) => [rule.rule_id, rule]))
}

function formatRuleDiff(actualRules, expectedRules) {
  const actualById = ruleMap(actualRules)
  const expectedById = ruleMap(expectedRules)
  const ruleIds = [...new Set([...actualById.keys(), ...expectedById.keys()])].sort()

  return ruleIds
    .map((ruleId) => {
      const actual = actualById.get(ruleId)
      const expected = expectedById.get(ruleId)
      try {
        assert.deepStrictEqual(actual, expected)
        return null
      } catch {
        return [
          `rule_id=${ruleId}`,
          `actual=${JSON.stringify(actual, null, 2)}`,
          `expected=${JSON.stringify(expected, null, 2)}`,
        ].join('\n')
      }
    })
    .filter(Boolean)
    .join('\n\n')
}

const golden = JSON.parse(await readFile(goldenPath, 'utf8'))
const config = golden.fixed_rules_config

const server = await createServer({
  root: frontendRoot,
  logLevel: 'error',
  optimizeDeps: {
    noDiscovery: true,
  },
  server: { middlewareMode: true },
  appType: 'custom',
})

try {
  const { orchestrationRulesToValidationRules } = await server.ssrLoadModule(
    '/src/utils/workbenchOrchestrationRules.ts',
  )
  const { buildTaskTreePayload } = await server.ssrLoadModule('/src/utils/taskTree.ts')

  const actualRules = stableRules(
    orchestrationRulesToValidationRules(config.variables, config.rules),
  )
  const expectedRules = stableRules(golden.expected_validation_rules)

  try {
    assert.deepStrictEqual(actualRules, expectedRules)
  } catch (error) {
    console.error('Rule contract mismatch between frontend mapper and golden fixture.')
    console.error(formatRuleDiff(actualRules, expectedRules))
    throw error
  }

  const payload = buildTaskTreePayload(config.sources, config.variables, actualRules)
  assert.equal(payload.rules.length, expectedRules.length)

  const payloadRuleIds = new Set(payload.rules.map((rule) => rule.rule_id))
  for (const rule of expectedRules) {
    assert.ok(payloadRuleIds.has(rule.rule_id), `TaskTree payload is missing ${rule.rule_id}`)
  }

  console.log(`Rule contract check passed for ${expectedRules.length} rules.`)
} finally {
  await server.close()
}

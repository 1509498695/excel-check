interface SmartRuleGenerateBlockedMessageOptions {
  isConfigured: boolean
  allowAutoComplete: boolean
  autoCompleteMissingItems: string[]
  hasRuleDescription: boolean
}

export function getSmartRuleGenerateBlockedMessage(
  options: SmartRuleGenerateBlockedMessageOptions,
): string {
  if (!options.isConfigured) {
    return '请先配置 AI 模型。'
  }
  if (options.allowAutoComplete && options.autoCompleteMissingItems.length) {
    return `请先补齐：${options.autoCompleteMissingItems.join('、')}。`
  }
  if (!options.hasRuleDescription) {
    return '请先输入规则描述。'
  }
  return '请先选择变量池变量，或开启 AI 自动补齐数据源/变量。'
}

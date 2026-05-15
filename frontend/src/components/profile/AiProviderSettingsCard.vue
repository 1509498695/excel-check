<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import PrimaryButton from '../shell/PrimaryButton.vue'
import SecondaryButton from '../shell/SecondaryButton.vue'
import StatusBadge from '../shell/StatusBadge.vue'
import { useAiStore } from '../../store/ai'
import type { AiProviderConfigInput, AiProviderPreset } from '../../types/ai'

const aiStore = useAiStore()

const providerOptions: Array<{
  label: string
  value: AiProviderPreset
  protocol: string
  baseUrl: string
  model: string
}> = [
  {
    label: 'OpenAI',
    value: 'openai',
    protocol: 'OpenAI-compatible',
    baseUrl: 'https://api.openai.com/v1',
    model: 'gpt-5.4-mini',
  },
  {
    label: 'Anthropic Claude',
    value: 'anthropic',
    protocol: 'Messages API',
    baseUrl: 'https://api.anthropic.com/v1',
    model: 'claude-sonnet-4-5',
  },
  {
    label: 'Google Gemini',
    value: 'gemini',
    protocol: 'generateContent',
    baseUrl: 'https://generativelanguage.googleapis.com/v1beta',
    model: 'gemini-2.5-flash',
  },
  {
    label: 'DeepSeek',
    value: 'deepseek',
    protocol: 'OpenAI-compatible',
    baseUrl: 'https://api.deepseek.com',
    model: 'deepseek-v4-flash',
  },
  {
    label: '通义千问 DashScope',
    value: 'qwen',
    protocol: 'OpenAI-compatible',
    baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    model: 'qwen-plus',
  },
  {
    label: 'Kimi',
    value: 'kimi',
    protocol: 'OpenAI-compatible',
    baseUrl: 'https://api.moonshot.ai/v1',
    model: 'kimi-k2-turbo-preview',
  },
  {
    label: '智谱 GLM',
    value: 'zhipu',
    protocol: 'OpenAI-compatible',
    baseUrl: 'https://open.bigmodel.cn/api/paas/v4',
    model: 'glm-4.7-flash',
  },
  {
    label: 'OpenRouter',
    value: 'openrouter',
    protocol: 'OpenAI-compatible',
    baseUrl: 'https://openrouter.ai/api/v1',
    model: 'openai/gpt-5-mini',
  },
  {
    label: '小米 MiMo',
    value: 'xiaomi_mimo',
    protocol: 'OpenAI-compatible',
    baseUrl: 'https://api.xiaomimimo.com/v1',
    model: 'mimo-v2.5-pro',
  },
  {
    label: '小米 MiMo 会员',
    value: 'xiaomi_mimo_token_plan',
    protocol: 'OpenAI-compatible',
    baseUrl: 'https://token-plan-cn.xiaomimimo.com/v1',
    model: 'mimo-v2.5-pro',
  },
  {
    label: '自定义 OpenAI 兼容',
    value: 'custom_openai',
    protocol: 'OpenAI-compatible',
    baseUrl: '',
    model: '',
  },
]

const form = reactive({
  provider_preset: 'deepseek' as AiProviderPreset,
  base_url: 'https://api.deepseek.com',
  model: 'deepseek-v4-flash',
  api_key: '',
  extra_headers_json: '{}',
})
const advancedVisible = ref(false)

const currentOption = computed(
  () => providerOptions.find((option) => option.value === form.provider_preset) ?? providerOptions[0],
)
const statusLabel = computed(() =>
  aiStore.provider ? `${currentOption.value.label} / ${aiStore.provider.model}` : '未配置',
)
const hasSavedApiKey = computed(() => Boolean(aiStore.provider?.api_key_masked))

onMounted(async () => {
  await aiStore.loadProvider()
  hydrateFormFromProvider()
})

watch(
  () => aiStore.provider,
  () => hydrateFormFromProvider(),
)

function hydrateFormFromProvider(): void {
  if (!aiStore.provider) {
    return
  }
  form.provider_preset = aiStore.provider.provider_preset
  form.base_url = aiStore.provider.base_url
  form.model = aiStore.provider.model
  form.api_key = ''
}

function handleProviderChange(value: AiProviderPreset): void {
  const option = providerOptions.find((item) => item.value === value)
  if (!option) {
    return
  }
  form.provider_preset = value
  form.base_url = option.baseUrl
  form.model = option.model
}

function handleProviderValueChange(value: string | number | boolean): void {
  handleProviderChange(value as AiProviderPreset)
}

function buildPayload(requireApiKey: boolean): AiProviderConfigInput | null {
  if (!form.base_url.trim()) {
    ElMessage.warning('请填写 Base URL。')
    return null
  }
  if (!form.model.trim()) {
    ElMessage.warning('请填写模型名称。')
    return null
  }
  if (requireApiKey && !form.api_key.trim()) {
    ElMessage.warning('请填写 API Key。')
    return null
  }

  let extraHeaders: Record<string, string>
  try {
    const parsed = JSON.parse(form.extra_headers_json || '{}') as unknown
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error('extra_headers 必须是 JSON 对象。')
    }
    extraHeaders = Object.fromEntries(
      Object.entries(parsed as Record<string, unknown>).map(([key, value]) => [
        key,
        String(value ?? ''),
      ]),
    )
  } catch (error) {
    ElMessage.warning(error instanceof Error ? error.message : '高级请求头 JSON 不合法。')
    return null
  }

  return {
    provider_preset: form.provider_preset,
    base_url: form.base_url.trim(),
    model: form.model.trim(),
    api_key: form.api_key.trim() || null,
    extra_headers: extraHeaders,
  }
}

async function handleSave(): Promise<void> {
  const payload = buildPayload(!hasSavedApiKey.value)
  if (!payload) {
    return
  }
  await aiStore.saveProvider(payload)
  form.api_key = ''
  ElMessage.success('AI 模型配置已保存。')
}

async function handleTest(): Promise<void> {
  const payload = buildPayload(!hasSavedApiKey.value)
  if (!payload) {
    return
  }
  const result = await aiStore.testProvider(payload)
  ElMessage.success(`连接成功${result.latency_ms ? `，耗时 ${result.latency_ms}ms` : ''}。`)
}

async function handleDelete(): Promise<void> {
  if (!aiStore.provider) {
    return
  }
  await ElMessageBox.confirm('删除后智能添加规则将无法调用大模型。', '删除 AI 配置', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning',
  })
  await aiStore.deleteProvider()
  form.api_key = ''
  ElMessage.success('AI 模型配置已删除。')
}
</script>

<template>
  <div class="profile-settings-card__body">
    <div class="mb-4 flex items-center justify-between gap-3">
      <div class="flex items-center gap-2">
        <StatusBadge :type="aiStore.provider ? 'success' : 'neutral'" :label="statusLabel" />
        <span v-if="aiStore.provider?.api_key_masked" class="text-[12px] text-ink-500">
          Key {{ aiStore.provider.api_key_masked }}
        </span>
      </div>
      <button type="button" class="ec-action-link" @click="advancedVisible = !advancedVisible">
        {{ advancedVisible ? '收起高级项' : '展开高级项' }}
      </button>
    </div>

    <div class="grid grid-cols-3 gap-4">
      <div class="profile-form-field">
        <label class="mb-1.5 block text-[12px] font-medium text-ink-500">供应商</label>
        <el-select
          v-model="form.provider_preset"
          class="w-full"
          @update:model-value="handleProviderValueChange"
        >
          <el-option
            v-for="option in providerOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          >
            <span class="font-medium">{{ option.label }}</span>
            <span class="ml-2 text-[12px] text-ink-500">{{ option.protocol }}</span>
          </el-option>
        </el-select>
      </div>

      <div class="profile-form-field">
        <label class="mb-1.5 block text-[12px] font-medium text-ink-500">模型</label>
        <el-input v-model="form.model" placeholder="例如 deepseek-v4-flash" />
      </div>

      <div class="profile-form-field">
        <label class="mb-1.5 block text-[12px] font-medium text-ink-500">API Key</label>
        <el-input
          v-model="form.api_key"
          type="password"
          show-password
          :placeholder="hasSavedApiKey ? '已保存，留空测试/保存均复用已保存 Key' : '请输入 API Key'"
        />
      </div>
    </div>

    <div v-if="advancedVisible" class="mt-4 grid grid-cols-2 gap-4">
      <div class="profile-form-field">
        <label class="mb-1.5 block text-[12px] font-medium text-ink-500">Base URL</label>
        <el-input v-model="form.base_url" placeholder="https://.../v1" />
      </div>
      <div class="profile-form-field">
        <label class="mb-1.5 block text-[12px] font-medium text-ink-500">额外请求头 JSON</label>
        <el-input
          v-model="form.extra_headers_json"
          type="textarea"
          :rows="2"
          placeholder="{&quot;HTTP-Referer&quot;:&quot;...&quot;}"
        />
      </div>
    </div>

    <div class="mt-5 flex items-center justify-between">
      <div class="text-[12px] text-ink-500">
        API Key 只会加密保存在后端，智能规则生成只发送数据结构元信息。
      </div>
      <div class="flex items-center gap-2">
        <SecondaryButton
          :disabled="aiStore.isProviderTesting"
          @click="handleTest"
        >
          {{ aiStore.isProviderTesting ? '测试中…' : '测试连接' }}
        </SecondaryButton>
        <SecondaryButton
          v-if="aiStore.provider"
          :disabled="aiStore.isProviderSaving"
          @click="handleDelete"
        >
          删除配置
        </SecondaryButton>
        <PrimaryButton
          :disabled="aiStore.isProviderSaving"
          @click="handleSave"
        >
          {{ aiStore.isProviderSaving ? '保存中…' : '保存配置' }}
        </PrimaryButton>
      </div>
    </div>
  </div>
</template>

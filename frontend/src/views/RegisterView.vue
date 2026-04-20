<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { apiListProjectsPublic } from '../api/auth'
import { useAuthStore } from '../store/auth'
import type { ProjectPublic } from '../types/auth'

// 保持原有逻辑不变：注册校验、项目列表加载与成功后的登录态处理不做改动。
const router = useRouter()
const auth = useAuthStore()

const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const selectedProjectId = ref<number | null>(null)
const projects = ref<ProjectPublic[]>([])
const isLoading = ref(false)

onMounted(async () => {
  try {
    const response = await apiListProjectsPublic()
    projects.value = response.data
    if (projects.value.length) {
      selectedProjectId.value = projects.value[0].id
    }
  } catch {
    ElMessage.warning('暂无可用项目，请联系管理员创建项目后再注册')
  }
})

async function handleRegister(): Promise<void> {
  if (!username.value.trim()) {
    ElMessage.warning('请填写用户名')
    return
  }
  if (username.value.trim().length < 2) {
    ElMessage.warning('用户名至少 2 个字符')
    return
  }
  if (!password.value || password.value.length < 4) {
    ElMessage.warning('密码至少 4 个字符')
    return
  }
  if (password.value !== confirmPassword.value) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }
  if (selectedProjectId.value === null) {
    ElMessage.warning('请选择归属项目')
    return
  }

  isLoading.value = true
  try {
    await auth.register(username.value.trim(), password.value, selectedProjectId.value)
    ElMessage.success('注册成功')
    router.push('/')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '注册失败')
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-header">
        <span class="auth-brand">EC</span>
        <h1>注册 Excel Check</h1>
        <p>创建您的账户</p>
      </div>

      <el-form class="auth-form" @submit.prevent="handleRegister">
        <el-form-item>
          <el-input
            v-model="username"
            placeholder="用户名（至少 2 个字符）"
            size="large"
            autofocus
          />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="password"
            type="password"
            placeholder="密码（至少 4 个字符）"
            size="large"
            show-password
          />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="confirmPassword"
            type="password"
            placeholder="确认密码"
            size="large"
            show-password
          />
        </el-form-item>
        <el-form-item>
          <el-select
            v-model="selectedProjectId"
            placeholder="选择归属项目"
            size="large"
            class="full-width"
          >
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          :loading="isLoading"
          :disabled="!projects.length"
          class="auth-submit"
          native-type="submit"
        >
          注册
        </el-button>
      </el-form>

      <div class="auth-footer">
        <span>已有账号？</span>
        <router-link to="/login">返回登录</router-link>
      </div>
    </div>
  </div>
</template>

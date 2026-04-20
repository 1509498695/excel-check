<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '../store/auth'

// 保持原有逻辑不变：登录校验、鉴权调用与跳转链路保持现状。
const router = useRouter()
const auth = useAuthStore()

const username = ref('')
const password = ref('')
const isLoading = ref(false)

async function handleLogin(): Promise<void> {
  if (!username.value.trim() || !password.value) {
    ElMessage.warning('请填写用户名和密码')
    return
  }

  isLoading.value = true
  try {
    // 保留原有业务逻辑：登录继续调用原 auth store 鉴权链路。
    await auth.login(username.value.trim(), password.value)
    ElMessage.success('登录成功')
    router.push('/')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '登录失败')
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
        <h1>登录 Excel Check</h1>
        <p>配置表校验工作台</p>
      </div>

      <el-form class="auth-form" @submit.prevent="handleLogin">
        <el-form-item>
          <el-input
            v-model="username"
            placeholder="用户名"
            size="large"
            autofocus
          />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="password"
            type="password"
            placeholder="密码"
            size="large"
            show-password
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          :loading="isLoading"
          class="auth-submit"
          native-type="submit"
        >
          登录
        </el-button>
      </el-form>

      <div class="auth-footer">
        <span>还没有账号？</span>
        <router-link to="/register">立即注册</router-link>
      </div>
    </div>
  </div>
</template>

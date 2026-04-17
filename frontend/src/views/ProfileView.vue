<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { apiChangePassword } from '../api/auth'
import { useAuthStore } from '../store/auth'
import { useFixedRulesStore } from '../store/fixedRules'
import { useWorkbenchStore } from '../store/workbench'

const auth = useAuthStore()
const router = useRouter()

const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const isChanging = ref(false)

async function handleChangePassword(): Promise<void> {
  if (!oldPassword.value) {
    ElMessage.warning('请输入原密码')
    return
  }
  if (newPassword.value.length < 4) {
    ElMessage.warning('新密码至少 4 个字符')
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }

  isChanging.value = true
  try {
    await apiChangePassword(oldPassword.value, newPassword.value)
    ElMessage.success('密码修改成功')
    oldPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '修改失败')
  } finally {
    isChanging.value = false
  }
}

async function handleSwitchProject(projectId: number): Promise<void> {
  try {
    await auth.switchProject(projectId)
    const workbench = useWorkbenchStore()
    const fixedRules = useFixedRulesStore()
    fixedRules.resetState()
    await Promise.all([
      workbench.loadFromServer(),
      fixedRules.loadConfig().catch(() => {}),
    ])
    ElMessage.success('项目已切换')
    router.push('/')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '切换失败')
  }
}
</script>

<template>
  <div class="profile-page">
    <header class="profile-header">
      <h1>个人设置</h1>
      <p>管理您的账户信息</p>
    </header>

    <div class="profile-layout">
      <section class="profile-section">
        <h2>账户信息</h2>
        <div class="profile-info">
          <div class="profile-field">
            <span>用户名</span>
            <strong>{{ auth.user?.username ?? '-' }}</strong>
          </div>
          <div class="profile-field">
            <span>角色</span>
            <strong>
              {{ auth.isSuperAdmin ? '超级管理员' : auth.currentRole === 'admin' ? '项目管理员' : '普通用户' }}
            </strong>
          </div>
          <div class="profile-field">
            <span>当前项目</span>
            <strong>{{ auth.currentProjectName || '未选择' }}</strong>
          </div>
        </div>
      </section>

      <section class="profile-section" v-if="auth.userProjects.length > 1">
        <h2>切换项目</h2>
        <div class="project-switch-list">
          <div
            v-for="project in auth.userProjects"
            :key="project.project_id"
            class="project-switch-item"
            :class="{ 'is-current': project.project_id === auth.currentProjectId }"
          >
            <div>
              <strong>{{ project.project_name }}</strong>
              <span>{{ project.role === 'admin' ? '管理员' : '普通用户' }}</span>
            </div>
            <el-button
              v-if="project.project_id !== auth.currentProjectId"
              type="primary"
              plain
              size="small"
              @click="handleSwitchProject(project.project_id)"
            >
              切换
            </el-button>
            <el-tag v-else type="success" effect="light" round>当前</el-tag>
          </div>
        </div>
      </section>

      <section class="profile-section">
        <h2>修改密码</h2>
        <el-form class="profile-form" @submit.prevent="handleChangePassword">
          <el-form-item>
            <el-input
              v-model="oldPassword"
              type="password"
              placeholder="原密码"
              show-password
            />
          </el-form-item>
          <el-form-item>
            <el-input
              v-model="newPassword"
              type="password"
              placeholder="新密码（至少 4 个字符）"
              show-password
            />
          </el-form-item>
          <el-form-item>
            <el-input
              v-model="confirmPassword"
              type="password"
              placeholder="确认新密码"
              show-password
            />
          </el-form-item>
          <el-button
            type="primary"
            :loading="isChanging"
            native-type="submit"
          >
            修改密码
          </el-button>
        </el-form>
      </section>
    </div>
  </div>
</template>

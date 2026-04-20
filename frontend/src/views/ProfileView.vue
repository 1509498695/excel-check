<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { apiChangePassword } from '../api/auth'
import { useAuthStore } from '../store/auth'
import { useFixedRulesStore } from '../store/fixedRules'
import { useWorkbenchStore } from '../store/workbench'

// 保持原有逻辑不变：密码修改与项目切换行为维持原实现。
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
    // 保留原有业务逻辑：密码修改继续走原有认证接口。
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
    // 保留原有业务逻辑：项目切换与相关 store 重载保持原链路不变。
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
      <p>左侧看账户摘要，右侧处理切换与安全设置。</p>
    </header>

    <div class="profile-layout profile-desktop-layout">
      <aside class="profile-summary-panel">
        <section class="profile-section profile-section-hero">
          <div class="profile-hero-avatar">
            {{ auth.user?.username?.charAt(0)?.toUpperCase() ?? 'U' }}
          </div>
          <div class="profile-hero-copy">
            <strong>{{ auth.user?.username ?? '-' }}</strong>
            <span>
              {{ auth.isSuperAdmin ? '超级管理员' : auth.currentRole === 'admin' ? '项目管理员' : '普通用户' }}
            </span>
          </div>
        </section>

        <section class="profile-section">
          <h2>账户摘要</h2>
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
      </aside>

      <section class="profile-workspace-panel">
        <h2>账户信息</h2>
        <section class="profile-section" v-if="auth.userProjects.length > 1">
          <div class="profile-section-head">
            <h2>切换项目</h2>
            <el-tag type="info" effect="light" round>{{ auth.userProjects.length }} 个项目</el-tag>
          </div>
          <div class="project-switch-list">
            <!-- // 保留原有业务逻辑：项目列表仍基于 auth.userProjects 遍历并继续调用原切换逻辑 -->
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
          <div class="profile-section-head">
            <h2>修改密码</h2>
            <el-tag type="warning" effect="light" round>安全设置</el-tag>
          </div>
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
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Setting, SwitchButton, User as UserIcon } from '@element-plus/icons-vue'

import { useAuthStore } from './store/auth'
import { useFixedRulesStore } from './store/fixedRules'
import { useWorkbenchStore } from './store/workbench'

// 保持原有逻辑不变：仅做共享壳层的视觉重构，不调整认证、项目切换或路由跳转行为。
const auth = useAuthStore()
const router = useRouter()

const showShell = computed(() => auth.isLoggedIn)

function handleLogout(): void {
  auth.logout()
  router.push('/login')
  ElMessage.success('已退出登录')
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
  <div class="app-shell" v-if="showShell">
    <header class="app-shell-header">
      <div class="app-shell-brand">
        <span class="app-shell-brand-mark">EC</span>
        <div>
          <strong>Excel Check</strong>
          <p>配置表校验工作台</p>
        </div>
      </div>

      <nav class="app-shell-nav" aria-label="主导航">
        <RouterLink to="/" class="app-shell-link" active-class="is-active">
          工作台
        </RouterLink>
        <RouterLink to="/fixed-rules" class="app-shell-link" active-class="is-active">
          固定规则检查
        </RouterLink>
        <RouterLink
          v-if="auth.isProjectAdmin"
          to="/admin"
          class="app-shell-link"
          active-class="is-active"
        >
          管理后台
        </RouterLink>
      </nav>

      <div class="app-shell-user">
        <el-dropdown trigger="click">
          <button type="button" class="user-trigger">
            <span class="user-avatar">{{ auth.user?.username?.charAt(0)?.toUpperCase() ?? 'U' }}</span>
            <span class="user-name">{{ auth.user?.username ?? '' }}</span>
            <span v-if="auth.currentProjectName" class="user-project">{{ auth.currentProjectName }}</span>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item :icon="UserIcon" @click="router.push('/profile')">
                个人设置
              </el-dropdown-item>
              <el-dropdown-item
                v-for="project in auth.userProjects"
                :key="project.project_id"
                :icon="Setting"
                :disabled="project.project_id === auth.currentProjectId"
                @click="handleSwitchProject(project.project_id)"
              >
                {{ project.project_name }}
                {{ project.project_id === auth.currentProjectId ? '（当前）' : '' }}
              </el-dropdown-item>
              <el-dropdown-item divided :icon="SwitchButton" @click="handleLogout">
                退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <main class="app-shell-page">
      <router-view />
    </main>
  </div>

  <router-view v-else />
</template>

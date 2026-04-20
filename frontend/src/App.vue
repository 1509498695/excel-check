<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  DataBoard,
  Setting,
  SetUp,
  SwitchButton,
  User as UserIcon,
} from '@element-plus/icons-vue'

import { useAuthStore } from './store/auth'
import { useFixedRulesStore } from './store/fixedRules'
import { useWorkbenchStore } from './store/workbench'

// 保持原有逻辑不变：仅做共享壳层的视觉重构，不调整认证、项目切换或路由跳转行为。
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const showShell = computed(() => auth.isLoggedIn)
const currentWorkspaceLabel = computed(() => {
  if (route.name === 'fixed-rules-board') {
    return '固定规则检查'
  }
  if (route.name === 'admin') {
    return '管理后台'
  }
  if (route.name === 'profile') {
    return '个人设置'
  }
  return '工作台'
})
const currentRoleLabel = computed(() => {
  if (auth.isSuperAdmin) {
    return '超级管理员'
  }
  if (auth.currentRole === 'admin') {
    return '项目管理员'
  }
  return '普通用户'
})

function handleLogout(): void {
  auth.logout()
  router.push('/login')
  ElMessage.success('已退出登录')
}

async function handleSwitchProject(projectId: number): Promise<void> {
  try {
    // 保留原有业务逻辑：项目切换仍复用原有鉴权接口与前端状态刷新链路。
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
    <aside class="app-shell-sidebar">
      <div class="app-shell-brand">
        <span class="app-shell-brand-mark">EC</span>
        <div>
          <strong>Excel Check</strong>
          <p>桌面校验工作台</p>
        </div>
      </div>

      <nav class="app-shell-nav" aria-label="主导航">
        <RouterLink to="/" class="app-shell-link" active-class="is-active">
          <DataBoard class="app-shell-link-icon" />
          <span>工作台</span>
        </RouterLink>
        <RouterLink to="/fixed-rules" class="app-shell-link" active-class="is-active">
          <SetUp class="app-shell-link-icon" />
          <span>固定规则</span>
        </RouterLink>
        <RouterLink
          v-if="auth.isProjectAdmin"
          to="/admin"
          class="app-shell-link"
          active-class="is-active"
        >
          <Setting class="app-shell-link-icon" />
          <span>管理后台</span>
        </RouterLink>
        <RouterLink to="/profile" class="app-shell-link" active-class="is-active">
          <UserIcon class="app-shell-link-icon" />
          <span>个人设置</span>
        </RouterLink>
      </nav>

      <div class="app-shell-sidebar-footer">
        <div class="app-shell-project-card">
          <span>当前项目</span>
          <strong>{{ auth.currentProjectName || '未选择项目' }}</strong>
          <small>{{ currentRoleLabel }}</small>
        </div>

        <div class="app-shell-user">
          <el-dropdown trigger="click">
            <button type="button" class="user-trigger">
              <span class="user-avatar">{{ auth.user?.username?.charAt(0)?.toUpperCase() ?? 'U' }}</span>
              <span class="user-name">{{ auth.user?.username ?? '' }}</span>
              <span class="user-project">{{ currentWorkspaceLabel }}</span>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item :icon="UserIcon" @click="router.push('/profile')">
                  个人设置
                </el-dropdown-item>
                <!-- // 保留原有业务逻辑：项目列表仍基于 auth.userProjects 遍历，点击继续走原有切换链路 -->
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
      </div>
    </aside>

    <section class="app-shell-main">
      <header class="app-shell-toolbar">
        <div class="app-shell-toolbar-copy">
          <span class="app-shell-toolbar-label">当前空间</span>
          <strong>{{ currentWorkspaceLabel }}</strong>
        </div>
        <div class="app-shell-toolbar-meta">
          <el-tag type="info" effect="light" round>{{ currentRoleLabel }}</el-tag>
          <el-tag v-if="auth.currentProjectName" type="success" effect="light" round>
            {{ auth.currentProjectName }}
          </el-tag>
        </div>
      </header>

      <main class="app-shell-page">
        <router-view />
      </main>
    </section>
  </div>

  <router-view v-else />
</template>

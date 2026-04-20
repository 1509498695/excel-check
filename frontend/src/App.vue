<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAuthStore } from './store/auth'
import { useFixedRulesStore } from './store/fixedRules'
import { useWorkbenchStore } from './store/workbench'

// 保持原有逻辑不变：仅做共享壳层的视觉重构，不调整认证、项目切换或路由跳转行为。
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const showShell = computed(() => auth.isLoggedIn)

const currentRoleLabel = computed(() => {
  if (auth.isSuperAdmin) {
    return '超级管理员'
  }
  if (auth.currentRole === 'admin') {
    return '项目管理员'
  }
  return '普通用户'
})

const navItems = computed(() => {
  const items: Array<{
    to: string
    label: string
    routeName: string
    show: boolean
    icon: string
  }> = [
    {
      to: '/',
      label: '工作台',
      routeName: 'main-board',
      show: true,
      icon: 'M3 12l9-9 9 9 M5 10v10h14V10',
    },
    {
      to: '/fixed-rules',
      label: '固定规则',
      routeName: 'fixed-rules-board',
      show: true,
      icon: 'M5 5h14v14H5z M9 11h6 M9 15h6',
    },
    {
      to: '/admin',
      label: '管理后台',
      routeName: 'admin',
      show: auth.isProjectAdmin,
      icon: 'M3 5h18 M3 12h18 M3 19h18',
    },
    {
      to: '/profile',
      label: '个人设置',
      routeName: 'profile',
      show: true,
      icon: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8',
    },
  ]
  return items.filter((item) => item.show)
})

function isActive(routeName: string): boolean {
  return route.name === routeName
}

function handleLogout(): void {
  // 保留原有业务逻辑：退出仍走原 auth store 链路。
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
  <div
    v-if="showShell"
    class="grid h-screen w-screen grid-cols-[260px_minmax(0,1fr)] gap-0 overflow-hidden bg-canvas font-sans text-ink-700"
  >
    <!-- ============= 左侧固定边栏 ============= -->
    <aside class="flex h-full flex-col border-r border-line bg-card">
      <!-- 品牌：主色方块 + 表格 SVG -->
      <div class="flex items-center gap-3 px-6 py-5">
        <div class="flex h-8 w-8 items-center justify-center rounded-md bg-accent text-white">
          <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 5h16v14H4z M4 10h16 M9 5v14" />
          </svg>
        </div>
        <div class="leading-tight">
          <div class="text-[15px] font-semibold text-ink-900">Excel Check</div>
          <div class="text-[12px] text-ink-500">配置表校验工作台</div>
        </div>
      </div>

      <!-- 主导航 -->
      <nav class="flex-1 overflow-y-auto px-3 pb-4" aria-label="主导航">
        <div class="px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-ink-500">
          主菜单
        </div>
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="mb-1 flex items-center gap-3 rounded-md px-3 py-2.5 text-[14px] transition"
          :class="
            isActive(item.routeName)
              ? 'bg-accent-soft font-medium text-accent-ink'
              : 'text-ink-700 hover:bg-canvas'
          "
        >
          <svg
            class="h-4 w-4 shrink-0 transition"
            :class="isActive(item.routeName) ? 'text-accent-ink' : 'text-ink-500'"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path :d="item.icon" />
          </svg>
          {{ item.label }}
        </RouterLink>
      </nav>

      <!-- 底部项目卡 + 用户菜单 -->
      <div class="border-t border-line p-4">
        <div class="rounded-md bg-canvas p-3">
          <div class="text-[11px] font-medium uppercase tracking-wider text-ink-500">当前项目</div>
          <div class="mt-1 text-[14px] font-semibold text-ink-900 truncate">
            {{ auth.currentProjectName || '未选择项目' }}
          </div>
          <div class="text-[12px] text-ink-500">{{ currentRoleLabel }}</div>
        </div>

        <div class="mt-3">
          <el-dropdown trigger="click" placement="top-start">
            <button
              type="button"
              class="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left transition hover:bg-canvas"
            >
              <span
                class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent text-[12px] font-semibold text-white"
              >
                {{ auth.user?.username?.charAt(0)?.toUpperCase() ?? 'U' }}
              </span>
              <span class="flex-1 truncate text-[13px] text-ink-700">
                {{ auth.user?.username ?? '' }}
              </span>
              <span class="text-[12px] text-ink-500">···</span>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="router.push('/profile')">个人设置</el-dropdown-item>
                <!-- // 保留原有业务逻辑：项目列表仍基于 auth.userProjects 遍历，点击继续走原有切换链路 -->
                <el-dropdown-item
                  v-for="project in auth.userProjects"
                  :key="project.project_id"
                  :disabled="project.project_id === auth.currentProjectId"
                  @click="handleSwitchProject(project.project_id)"
                >
                  {{ project.project_name }}
                  {{ project.project_id === auth.currentProjectId ? '（当前）' : '' }}
                </el-dropdown-item>
                <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </aside>

    <!-- ============= 右侧主区：纯 router-view，TopBar 由各页面自己提供 ============= -->
    <main class="flex h-full flex-col overflow-hidden bg-canvas">
      <router-view />
    </main>
  </div>

  <router-view v-else />
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { apiChangePassword } from '../api/auth'
import { useAuthStore } from '../store/auth'
import { useFixedRulesStore } from '../store/fixedRules'
import { useWorkbenchStore } from '../store/workbench'
import PageHeader from '../components/shell/PageHeader.vue'
import SectionHeader from '../components/shell/SectionHeader.vue'

// 保持原有逻辑不变：密码修改与项目切换行为维持原实现。
const auth = useAuthStore()
const router = useRouter()

const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const isChanging = ref(false)

const roleLabel = computed(() => {
  if (auth.isSuperAdmin) {
    return '超级管理员'
  }
  if (auth.currentRole === 'admin') {
    return '项目管理员'
  }
  return '普通用户'
})

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
  <div class="flex h-full flex-col bg-canvas font-sans text-ink-700">
    <PageHeader breadcrumb="主菜单 / 个人设置" title="个人设置" />

    <div class="flex-1 overflow-y-auto px-8 py-10">
      <div class="mx-auto w-full max-w-[720px] flex flex-col">
        <!-- 段 1：账号信息 -->
        <section class="border-b border-line py-8 first:pt-0">
          <SectionHeader title="账号信息" description="账户基础属性与当前登录态" />

          <dl class="mt-5 grid grid-cols-2 gap-x-8 gap-y-4 text-[14px]">
            <div>
              <dt class="text-[12px] text-ink-500">用户名</dt>
              <dd class="mt-1 font-medium text-ink-900">{{ auth.user?.username ?? '—' }}</dd>
            </div>
            <div>
              <dt class="text-[12px] text-ink-500">角色</dt>
              <dd class="mt-1 font-medium text-ink-900">{{ roleLabel }}</dd>
            </div>
            <div>
              <dt class="text-[12px] text-ink-500">当前项目</dt>
              <dd class="mt-1 font-medium text-ink-900">{{ auth.currentProjectName || '未选择' }}</dd>
            </div>
            <div>
              <dt class="text-[12px] text-ink-500">可访问项目</dt>
              <dd class="mt-1 font-medium text-ink-900">{{ auth.userProjects.length }} 个</dd>
            </div>
          </dl>
        </section>

        <!-- 段 2：修改密码 -->
        <section class="border-b border-line py-8">
          <SectionHeader title="修改密码" description="新密码至少 4 个字符" />

          <form class="mt-5 flex flex-col gap-4" @submit.prevent="handleChangePassword">
            <div>
              <label class="mb-1.5 block text-[12px] font-medium text-ink-500">原密码</label>
              <el-input
                v-model="oldPassword"
                type="password"
                placeholder="原密码"
                show-password
              />
            </div>
            <div>
              <label class="mb-1.5 block text-[12px] font-medium text-ink-500">新密码</label>
              <el-input
                v-model="newPassword"
                type="password"
                placeholder="新密码（至少 4 个字符）"
                show-password
              />
            </div>
            <div>
              <label class="mb-1.5 block text-[12px] font-medium text-ink-500">确认新密码</label>
              <el-input
                v-model="confirmPassword"
                type="password"
                placeholder="确认新密码"
                show-password
              />
            </div>

            <div class="flex justify-end">
              <button
                type="submit"
                class="ec-btn ec-btn-primary"
                :disabled="isChanging"
              >
                {{ isChanging ? '保存中…' : '保存新密码' }}
              </button>
            </div>
          </form>
        </section>

        <!-- 段 3：我的项目 -->
        <section v-if="auth.userProjects.length" class="py-8">
          <SectionHeader title="我的项目" :description="`共 ${auth.userProjects.length} 个项目`" />

          <div class="mt-5 flex flex-col">
            <!-- // 保留原有业务逻辑：项目列表仍基于 auth.userProjects 遍历并继续调用原切换逻辑 -->
            <div
              v-for="project in auth.userProjects"
              :key="project.project_id"
              class="flex items-center justify-between gap-4 border-b border-line py-3 last:border-b-0"
            >
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <span class="text-[14px] font-medium text-ink-900 truncate">
                    {{ project.project_name }}
                  </span>
                  <span
                    v-if="project.project_id === auth.currentProjectId"
                    class="inline-flex items-center gap-1 rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent-ink"
                  >
                    <span class="h-1.5 w-1.5 rounded-full bg-accent"></span>
                    当前
                  </span>
                </div>
                <div class="mt-0.5 text-[12px] text-ink-500">
                  {{ project.role === 'admin' ? '项目管理员' : '普通用户' }}
                </div>
              </div>

              <button
                v-if="project.project_id !== auth.currentProjectId"
                type="button"
                class="ec-btn ec-btn-secondary ec-btn-sm shrink-0"
                @click="handleSwitchProject(project.project_id)"
              >
                切换到此项目
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

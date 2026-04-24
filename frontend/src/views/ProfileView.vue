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

type StepIndex = 1 | 2 | 3

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

const roleTagClass = computed(() => {
  if (auth.isSuperAdmin) {
    return 'bg-danger-soft text-danger'
  }
  if (auth.currentRole === 'admin') {
    return 'bg-warning-soft text-warning'
  }
  return 'bg-accent-soft text-accent-ink'
})

function getProjectRoleClass(role: string): string {
  if (role === 'admin') {
    return 'bg-warning-soft text-warning'
  }
  return 'bg-accent-soft text-accent-ink'
}

function getProjectRoleLabel(role: string): string {
  return role === 'admin' ? '项目管理员' : '普通用户'
}

function getSectionStatusLabel(step: StepIndex): string {
  if (step === 1) {
    return auth.user ? '正常' : '待登录'
  }
  if (step === 2) {
    return '待操作'
  }
  return auth.userProjects.length ? '已就绪' : '待加入'
}

function getSectionStatusTone(step: StepIndex): 'pending' | 'done' {
  if (step === 1) {
    return auth.user ? 'done' : 'pending'
  }
  if (step === 2) {
    return 'pending'
  }
  return auth.userProjects.length ? 'done' : 'pending'
}

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

    <div class="flex-1 overflow-y-auto px-8 py-8">
      <!-- 全宽通栏：01 / 02 / 03 三块撑满整页 -->
      <div class="flex w-full flex-col gap-6">
        <!-- 01 账号信息 -->
        <section class="rounded-card border border-gray-200 bg-card shadow-card-1">
          <div class="border-t-2 border-transparent px-5 py-4">
            <div class="flex items-start justify-between gap-4 border-b border-gray-200 pb-3">
              <SectionHeader
                variant="workbench"
                step="01"
                title="账号信息"
                description="账户基础属性与当前登录态"
                :status-label="getSectionStatusLabel(1)"
                :status-tone="getSectionStatusTone(1)"
              />
            </div>

            <div class="mt-4 overflow-hidden rounded-md border border-gray-200">
              <table class="w-full table-fixed border-collapse text-[13px]">
                <thead class="bg-gray-50">
                  <tr>
                    <th class="w-1/4 border border-gray-100 px-4 py-2.5 text-left text-[12px] font-medium uppercase tracking-wider text-ink-500">
                      用户名
                    </th>
                    <th class="w-1/4 border border-gray-100 px-4 py-2.5 text-left text-[12px] font-medium uppercase tracking-wider text-ink-500">
                      角色
                    </th>
                    <th class="w-1/4 border border-gray-100 px-4 py-2.5 text-left text-[12px] font-medium uppercase tracking-wider text-ink-500">
                      当前项目
                    </th>
                    <th class="w-1/4 border border-gray-100 px-4 py-2.5 text-left text-[12px] font-medium uppercase tracking-wider text-ink-500">
                      可访问项目
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr class="bg-white transition hover:bg-gray-50">
                    <td class="border border-gray-100 px-4 py-3 align-middle">
                      <span class="text-[14px] font-semibold text-ink-900">
                        {{ auth.user?.username ?? '—' }}
                      </span>
                    </td>
                    <td class="border border-gray-100 px-4 py-3 align-middle">
                      <span
                        class="inline-flex items-center rounded-full px-2.5 py-0.5 text-[12px] font-medium"
                        :class="roleTagClass"
                      >
                        {{ roleLabel }}
                      </span>
                    </td>
                    <td class="border border-gray-100 px-4 py-3 align-middle">
                      <span class="text-[14px] font-semibold text-ink-900">
                        {{ auth.currentProjectName || '未选择' }}
                      </span>
                    </td>
                    <td class="border border-gray-100 px-4 py-3 align-middle">
                      <span class="text-[14px] text-ink-900">
                        <span class="font-mono font-semibold">{{ auth.userProjects.length }}</span>
                        <span class="ml-1 text-[13px] font-normal text-ink-500">个</span>
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <!-- 02 修改密码 -->
        <section class="rounded-card border border-gray-200 bg-card shadow-card-1">
          <div class="border-t-2 border-transparent px-5 py-4">
            <div class="flex items-start justify-between gap-4 border-b border-gray-200 pb-3">
              <SectionHeader
                variant="workbench"
                step="02"
                title="修改密码"
                description="新密码至少 4 个字符；保存后立即生效，下一次登录请使用新密码"
                :status-label="getSectionStatusLabel(2)"
                :status-tone="getSectionStatusTone(2)"
              />
            </div>

            <!-- 表单整体左对齐 + max-w-md 约束 -->
            <form
              class="profile-password-form mt-5 flex w-full max-w-md flex-col gap-4"
              @submit.prevent="handleChangePassword"
            >
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

              <div class="mt-2 flex justify-start">
                <button
                  type="submit"
                  class="ec-btn ec-btn-primary"
                  :disabled="isChanging"
                >
                  {{ isChanging ? '保存中…' : '保存新密码' }}
                </button>
              </div>
            </form>
          </div>
        </section>

        <!-- 03 我的项目 -->
        <section class="rounded-card border border-gray-200 bg-card shadow-card-1">
          <div class="border-t-2 border-transparent px-5 py-4">
            <div class="flex items-start justify-between gap-4 border-b border-gray-200 pb-3">
              <SectionHeader
                variant="workbench"
                step="03"
                title="我的项目"
                :description="auth.userProjects.length
                  ? `共 ${auth.userProjects.length} 个项目；点击右侧可切换当前项目`
                  : '当前账号未加入任何项目'"
                :status-label="getSectionStatusLabel(3)"
                :status-tone="getSectionStatusTone(3)"
              />
            </div>

            <div
              v-if="!auth.userProjects.length"
              class="mt-4 rounded-md border border-dashed border-gray-200 bg-white px-4 py-10 text-center text-[13px] text-ink-500"
            >
              暂未加入任何项目
            </div>

            <div v-else class="mt-4 overflow-hidden rounded-md border border-gray-200">
              <table class="w-full table-fixed border-collapse text-[13px]">
                <thead class="bg-gray-50">
                  <tr>
                    <th class="w-1/4 border border-gray-100 px-4 py-2.5 text-left text-[12px] font-medium uppercase tracking-wider text-ink-500">
                      项目名称
                    </th>
                    <th class="w-1/4 border border-gray-100 px-4 py-2.5 text-left text-[12px] font-medium uppercase tracking-wider text-ink-500">
                      角色
                    </th>
                    <th class="w-1/4 border border-gray-100 px-4 py-2.5 text-left text-[12px] font-medium uppercase tracking-wider text-ink-500">
                      状态
                    </th>
                    <th class="w-1/4 border border-gray-100 px-4 py-2.5 text-left align-middle text-[12px] font-medium uppercase tracking-wider text-ink-500">
                      操作
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <!-- 保留原有业务逻辑：项目列表仍基于 auth.userProjects 遍历并继续调用原切换逻辑 -->
                  <tr
                    v-for="project in auth.userProjects"
                    :key="project.project_id"
                    class="bg-white transition hover:bg-gray-50"
                  >
                    <td class="border border-gray-100 px-4 py-3 align-middle">
                      <div class="flex items-center gap-2">
                        <span
                          class="truncate text-[14px] font-semibold"
                          :class="
                            project.project_id === auth.currentProjectId
                              ? 'text-accent-ink'
                              : 'text-ink-900'
                          "
                        >
                          {{ project.project_name }}
                        </span>
                        <span
                          v-if="project.project_id === auth.currentProjectId"
                          class="rounded-md bg-blue-100 px-1.5 py-0.5 text-[11px] font-semibold text-accent-ink"
                        >
                          当前
                        </span>
                      </div>
                    </td>
                    <td class="border border-gray-100 px-4 py-3 align-middle">
                      <span
                        class="inline-flex items-center rounded-full px-2.5 py-0.5 text-[12px] font-medium"
                        :class="getProjectRoleClass(project.role)"
                      >
                        {{ getProjectRoleLabel(project.role) }}
                      </span>
                    </td>
                    <td class="border border-gray-100 px-4 py-3 align-middle">
                      <span
                        v-if="project.project_id === auth.currentProjectId"
                        class="inline-flex items-center gap-1 rounded-full bg-success-soft px-2 py-0.5 text-[12px] font-medium text-success"
                      >
                        <span class="h-1.5 w-1.5 rounded-full bg-success"></span>
                        当前使用
                      </span>
                      <span v-else class="text-[12px] text-ink-500">未启用</span>
                    </td>
                    <td class="border border-gray-100 px-4 py-3 text-left align-middle">
                      <button
                        v-if="project.project_id !== auth.currentProjectId"
                        type="button"
                        class="ec-action-link"
                        @click="handleSwitchProject(project.project_id)"
                      >
                        切换到此项目
                      </button>
                      <span
                        v-else
                        class="text-[12px] text-ink-500"
                      >
                        使用中
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.profile-password-form :deep(.el-input__wrapper) {
  min-height: 42px;
  border: 1px solid #d1d5db !important;
  border-radius: 6px !important;
  background: #ffffff !important;
  box-shadow: none !important;
  transition:
    border-color 160ms cubic-bezier(0.2, 0, 0, 1),
    box-shadow 160ms cubic-bezier(0.2, 0, 0, 1) !important;
}

.profile-password-form :deep(.el-input__wrapper:hover) {
  border-color: #9ca3af !important;
}

.profile-password-form :deep(.el-input__wrapper.is-focus),
.profile-password-form :deep(.el-input.is-focus .el-input__wrapper) {
  border-color: #3b82f6 !important;
  box-shadow: 0 0 0 1px #3b82f6 inset !important;
}

.profile-password-form :deep(.el-input__inner) {
  color: #111827;
  font-size: 14px;
}

.profile-password-form :deep(.el-input__inner::placeholder) {
  color: #9ca3af;
}

.profile-password-form :deep(.el-input__suffix-inner) {
  color: #94a3b8;
}
</style>

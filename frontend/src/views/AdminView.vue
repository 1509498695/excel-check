<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

import {
  apiCreateProject,
  apiDeleteProject,
  apiListProjectMembers,
  apiListProjects,
  apiMoveMemberProject,
  apiRemoveMember,
  apiResetUserPassword,
  apiSetMemberRole,
  apiUpdateProject,
} from '../api/admin'
import { useAuthStore } from '../store/auth'
import type { ProjectDetail, ProjectMember } from '../types/auth'
import PageHeader from '../components/shell/PageHeader.vue'
import SectionHeader from '../components/shell/SectionHeader.vue'

const DEFAULT_PROJECT_NAME = '默认项目'

// 保持原有逻辑不变：项目管理、成员治理与弹窗交互仅做视觉重构，不改权限与接口调用。
const auth = useAuthStore()
const projects = ref<ProjectDetail[]>([])
const selectedProject = ref<ProjectDetail | null>(null)
const members = ref<ProjectMember[]>([])
const isLoadingProjects = ref(false)
const isLoadingMembers = ref(false)
const isProjectDialogVisible = ref(false)
const isSavingProject = ref(false)
const isMoveProjectDialogVisible = ref(false)
const isMovingMemberProject = ref(false)
const projectDialogMode = ref<'create' | 'edit'>('create')
const projectForm = reactive({
  name: '',
  description: '',
})
const moveProjectForm = reactive({
  userId: null as number | null,
  username: '',
  targetProjectId: null as number | null,
})

onMounted(async () => {
  // 保留原有业务逻辑：页面进入后仍先加载项目列表，再按原规则加载成员。
  await loadProjects()
})

const projectDialogTitle = computed(() =>
  projectDialogMode.value === 'create' ? '创建项目' : '编辑项目',
)

const canCreateProject = computed(() => auth.isSuperAdmin)
const canSubmitProject = computed(() => Boolean(projectForm.name.trim()))
const moveTargetProjects = computed(() =>
  projects.value.filter((project) => project.id !== selectedProject.value?.id),
)
const canSubmitMoveProject = computed(() => moveProjectForm.targetProjectId !== null)

async function loadProjects(): Promise<void> {
  isLoadingProjects.value = true
  try {
    // 保留原有业务逻辑：项目列表继续通过原有 admin API 获取。
    const response = await apiListProjects()
    projects.value = response.data

    const nextSelectedProject =
      projects.value.find((item) => item.id === selectedProject.value?.id) ?? projects.value[0] ?? null

    if (!nextSelectedProject) {
      selectedProject.value = null
      members.value = []
      return
    }

    selectedProject.value = nextSelectedProject
    await loadMembers(nextSelectedProject)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '加载项目列表失败')
    projects.value = []
    selectedProject.value = null
    members.value = []
  } finally {
    isLoadingProjects.value = false
  }
}

async function loadMembers(project: ProjectDetail): Promise<void> {
  selectedProject.value = project
  isLoadingMembers.value = true
  try {
    // 保留原有业务逻辑：成员列表继续消费原有项目成员接口。
    const response = await apiListProjectMembers(project.id)
    members.value = response.data
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '加载成员列表失败')
    members.value = []
  } finally {
    isLoadingMembers.value = false
  }
}

async function selectProject(project: ProjectDetail): Promise<void> {
  await loadMembers(project)
}

function openCreateProjectDialog(): void {
  projectDialogMode.value = 'create'
  projectForm.name = ''
  projectForm.description = ''
  isProjectDialogVisible.value = true
}

function openEditProjectDialog(project: ProjectDetail): void {
  projectDialogMode.value = 'edit'
  projectForm.name = project.name
  projectForm.description = project.description ?? ''
  selectedProject.value = project
  isProjectDialogVisible.value = true
}

function closeProjectDialog(): void {
  isProjectDialogVisible.value = false
}

function openMoveProjectDialog(member: ProjectMember): void {
  moveProjectForm.userId = member.user_id
  moveProjectForm.username = member.username
  moveProjectForm.targetProjectId = moveTargetProjects.value[0]?.id ?? null
  isMoveProjectDialogVisible.value = true
}

function closeMoveProjectDialog(): void {
  isMoveProjectDialogVisible.value = false
  moveProjectForm.userId = null
  moveProjectForm.username = ''
  moveProjectForm.targetProjectId = null
}

async function handleSubmitProject(): Promise<void> {
  if (!canSubmitProject.value) {
    ElMessage.warning('项目名称不能为空')
    return
  }

  isSavingProject.value = true
  const payload = {
    name: projectForm.name.trim(),
    description: projectForm.description.trim(),
  }

  try {
    if (projectDialogMode.value === 'create') {
      const response = await apiCreateProject(payload.name, payload.description)
      ElMessage.success('项目创建成功')
      await loadProjects()
      const createdProject = projects.value.find((item) => item.id === response.data.id)
      if (createdProject) {
        await selectProject(createdProject)
      }
    } else {
      if (!selectedProject.value) {
        throw new Error('未找到要编辑的项目')
      }
      await apiUpdateProject(selectedProject.value.id, payload)
      ElMessage.success('项目更新成功')
      await loadProjects()
    }
    closeProjectDialog()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存项目失败')
  } finally {
    isSavingProject.value = false
  }
}

async function handleDeleteProject(project: ProjectDetail): Promise<void> {
  if (project.name === DEFAULT_PROJECT_NAME) {
    ElMessage.warning('默认项目不可删除')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确认永久删除项目「${project.name}」？该项目下的成员关系、固定规则配置和工作台配置都会一并清理，且无法恢复。`,
      '删除项目',
      {
        confirmButtonText: '永久删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      },
    )
    await apiDeleteProject(project.id)
    ElMessage.success('项目已删除，正在刷新页面')
    window.setTimeout(() => {
      window.location.reload()
    }, 300)
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    ElMessage.error(error instanceof Error ? error.message : '删除项目失败')
  }
}

async function handleSetRole(member: ProjectMember, role: string): Promise<void> {
  if (!selectedProject.value) return
  try {
    await apiSetMemberRole(selectedProject.value.id, member.user_id, role)
    ElMessage.success(`已将 ${member.username} 设为${role === 'admin' ? '管理员' : '普通用户'}`)
    await loadMembers(selectedProject.value)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '操作失败')
  }
}

async function handleSubmitMoveProject(): Promise<void> {
  if (!selectedProject.value || moveProjectForm.userId === null || moveProjectForm.targetProjectId === null) {
    return
  }

  isMovingMemberProject.value = true
  try {
    await apiMoveMemberProject(
      selectedProject.value.id,
      moveProjectForm.userId,
      moveProjectForm.targetProjectId,
    )
    ElMessage.success('归属项目已更新')
    closeMoveProjectDialog()
    await loadProjects()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '调整归属项目失败')
  } finally {
    isMovingMemberProject.value = false
  }
}

async function handleRemoveMember(member: ProjectMember): Promise<void> {
  if (!selectedProject.value) return
  try {
    const isDefaultProjectSelected = isDefaultProject(selectedProject.value)
    const confirmMessage = isDefaultProjectSelected
      ? `确认删除用户「${member.username}」？删除后将永久移除该账号及其项目关系，且不可恢复。`
      : `确认删除成员「${member.username}」？删除后将把该成员移入默认项目，并从当前项目中移除。`

    await ElMessageBox.confirm(
      confirmMessage,
      '删除成员',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
    await apiRemoveMember(selectedProject.value.id, member.user_id)
    ElMessage.success(
      isDefaultProjectSelected ? '用户账号已删除' : '成员已移入默认项目',
    )
    await loadProjects()
  } catch {
    // 取消
  }
}

async function handleResetPassword(member: ProjectMember): Promise<void> {
  try {
    const result = await ElMessageBox.prompt(
      `为用户「${member.username}」设置新密码（至少 4 个字符）`,
      '重置密码',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        inputType: 'password',
        inputValidator: (value) =>
          Boolean(value && value.length >= 4) || '密码至少 4 个字符',
      },
    )
    await apiResetUserPassword(member.user_id, result.value)
    ElMessage.success('密码已重置，请通知用户使用新密码登录')
  } catch {
    // 取消
  }
}

function canMoveMemberProject(member: ProjectMember): boolean {
  if (member.is_super_admin || member.role !== 'user') {
    return false
  }
  return moveTargetProjects.value.length > 0
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

function isDefaultProject(project: ProjectDetail): boolean {
  return project.name === DEFAULT_PROJECT_NAME
}
</script>

<template>
  <div class="flex h-full flex-col bg-canvas font-sans text-ink-700">
    <PageHeader breadcrumb="主菜单 / 管理后台" title="管理后台">
      <template #actions>
        <button
          v-if="canCreateProject"
          type="button"
          class="ec-btn ec-btn-primary"
          @click="openCreateProjectDialog"
        >
          <Plus class="h-3.5 w-3.5" />
          创建项目
        </button>
      </template>
    </PageHeader>

    <div class="flex-1 overflow-y-auto px-8 py-8">
      <section class="grid grid-cols-[280px_minmax(0,1fr)] gap-6">
        <!-- 左侧项目列表 -->
        <aside
          v-loading="isLoadingProjects"
          class="rounded-card border border-line bg-card shadow-card-1"
        >
          <div class="border-b border-line px-5 py-4">
            <div class="text-[14px] font-semibold text-ink-900">
              {{ auth.isSuperAdmin ? '项目列表' : '可管理项目' }}
            </div>
            <div class="mt-1 text-[12px] text-ink-500">{{ projects.length }} 个项目</div>
          </div>

          <div v-if="!projects.length" class="px-5 py-8 text-center text-[13px] text-ink-500">
            暂无可管理项目
          </div>

          <nav class="flex flex-col gap-1 p-3">
            <!-- // 保留原有业务逻辑：项目列表仍基于 projects 遍历，点击继续走原有选中与加载成员逻辑 -->
            <div
              v-for="project in projects"
              :key="project.id"
              class="group relative rounded-md text-left text-[13px] transition cursor-pointer"
              :class="
                selectedProject?.id === project.id
                  ? 'bg-accent-soft text-accent-ink before:absolute before:inset-y-2 before:left-0 before:w-0.5 before:bg-accent before:rounded-r'
                  : 'text-ink-700 hover:bg-canvas'
              "
              @click="selectProject(project)"
            >
              <div class="flex items-start justify-between gap-2 px-3 pt-2.5">
                <div class="min-w-0 flex-1">
                  <div
                    class="truncate font-medium"
                    :class="selectedProject?.id === project.id ? 'text-accent-ink' : 'text-ink-900'"
                  >
                    {{ project.name }}
                  </div>
                  <div
                    class="mt-0.5 text-[12px]"
                    :class="selectedProject?.id === project.id ? 'text-accent-ink/80' : 'text-ink-500'"
                  >
                    成员 {{ project.member_count ?? 0 }} · {{ formatDate(project.created_at) }}
                  </div>
                </div>
              </div>
              <div class="flex items-center gap-3 px-3 pb-2.5 pt-1.5 text-[12px]">
                <button
                  type="button"
                  class="ec-btn-link"
                  @click.stop="openEditProjectDialog(project)"
                >
                  编辑
                </button>
                <button
                  v-if="auth.isSuperAdmin && !isDefaultProject(project)"
                  type="button"
                  class="ec-btn-link-danger"
                  @click.stop="handleDeleteProject(project)"
                >
                  删除
                </button>
              </div>
            </div>
          </nav>
        </aside>

        <!-- 右侧成员区 -->
        <div
          v-loading="isLoadingMembers"
          class="rounded-card border border-line bg-card shadow-card-1"
        >
          <div
            v-if="!selectedProject"
            class="flex flex-col items-center justify-center gap-2 py-20 text-center text-[13px] text-ink-500"
          >
            当前没有可管理项目
          </div>

          <template v-else>
            <div class="border-b border-line px-6 py-5">
              <SectionHeader
                :title="selectedProject.name"
                :description="selectedProject.description || '无项目描述'"
              />
            </div>

            <div class="px-6 py-5">
              <SectionHeader title="成员" :description="`共 ${members.length} 位成员`" />

              <div class="mt-4 overflow-hidden rounded-field border border-line">
                <table class="w-full text-[13px]">
                  <thead class="bg-canvas text-left text-[12px] font-medium uppercase tracking-wider text-ink-500">
                    <tr>
                      <th class="px-4 py-3 w-[180px]">用户名</th>
                      <th class="px-4 py-3 w-[140px]">角色</th>
                      <th class="px-4 py-3 w-[160px]">归属项目</th>
                      <th class="px-4 py-3 w-[180px]">加入时间</th>
                      <th class="px-4 py-3 text-right">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-if="!members.length">
                      <td colspan="5" class="px-4 py-12 text-center text-[13px] text-ink-500">
                        暂无成员
                      </td>
                    </tr>
                    <tr
                      v-for="row in members"
                      :key="row.user_id"
                      class="border-t border-line transition hover:bg-canvas"
                    >
                      <td class="px-4 py-3 font-medium text-ink-900 truncate">{{ row.username }}</td>
                      <td class="px-4 py-3">
                        <span
                          class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[12px] font-medium"
                          :class="
                            row.is_super_admin
                              ? 'bg-danger-soft text-danger'
                              : row.role === 'admin'
                                ? 'bg-warning-soft text-warning'
                                : 'bg-subtle text-ink-500'
                          "
                        >
                          {{ row.is_super_admin ? '超级管理员' : row.role === 'admin' ? '项目管理员' : '普通用户' }}
                        </span>
                      </td>
                      <td class="px-4 py-3 truncate text-ink-700">{{ row.primary_project_name ?? '-' }}</td>
                      <td class="px-4 py-3 font-mono text-[12px] text-ink-500">{{ formatDate(row.joined_at) }}</td>
                      <td class="px-4 py-3 text-right">
                        <div class="table-actions">
                          <button
                            v-if="auth.isSuperAdmin && row.user_id !== auth.user?.id"
                            type="button"
                            class="ec-action-link"
                            @click="handleResetPassword(row)"
                          >
                            重置密码
                          </button>
                          <template v-if="!row.is_super_admin">
                            <button
                              v-if="row.role !== 'admin'"
                              type="button"
                              class="ec-action-link"
                              @click="handleSetRole(row, 'admin')"
                            >
                              设为管理员
                            </button>
                            <button
                              v-else
                              type="button"
                              class="ec-action-link"
                              @click="handleSetRole(row, 'user')"
                            >
                              设为普通用户
                            </button>
                            <button
                              v-if="canMoveMemberProject(row)"
                              type="button"
                              class="ec-action-link"
                              @click="openMoveProjectDialog(row)"
                            >
                              调整归属
                            </button>
                            <button
                              v-if="row.user_id !== auth.user?.id"
                              type="button"
                              class="ec-action-link-danger"
                              @click="handleRemoveMember(row)"
                            >
                              删除
                            </button>
                          </template>
                          <span
                            v-if="row.is_super_admin && !(auth.isSuperAdmin && row.user_id !== auth.user?.id)"
                            class="text-ink-500"
                          >
                            —
                          </span>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </template>
        </div>
      </section>
    </div>

    <!-- 项目编辑弹窗 -->
    <el-dialog
      v-model="isProjectDialogVisible"
      :title="projectDialogTitle"
      width="520px"
      destroy-on-close
    >
      <div class="flex flex-col gap-4">
        <div>
          <label class="mb-1.5 block text-[12px] font-medium text-ink-500">项目名称</label>
          <el-input
            v-model="projectForm.name"
            placeholder="请输入项目名称"
            maxlength="128"
            show-word-limit
          />
        </div>
        <div>
          <label class="mb-1.5 block text-[12px] font-medium text-ink-500">项目描述</label>
          <el-input
            v-model="projectForm.description"
            type="textarea"
            :rows="4"
            maxlength="500"
            show-word-limit
            placeholder="可选"
          />
        </div>
      </div>
      <template #footer>
        <div class="flex justify-end gap-2">
          <button
            type="button"
            class="ec-btn ec-btn-secondary"
            @click="closeProjectDialog"
          >
            取消
          </button>
          <button
            type="button"
            class="ec-btn ec-btn-primary"
            :disabled="!canSubmitProject || isSavingProject"
            @click="handleSubmitProject"
          >
            {{ isSavingProject ? '保存中…' : projectDialogMode === 'create' ? '创建项目' : '保存修改' }}
          </button>
        </div>
      </template>
    </el-dialog>

    <!-- 调整归属项目弹窗 -->
    <el-dialog
      v-model="isMoveProjectDialogVisible"
      title="调整归属项目"
      width="480px"
      destroy-on-close
    >
      <div class="flex flex-col gap-4">
        <div>
          <label class="mb-1.5 block text-[12px] font-medium text-ink-500">成员</label>
          <el-input :model-value="moveProjectForm.username" disabled />
        </div>
        <div>
          <label class="mb-1.5 block text-[12px] font-medium text-ink-500">目标归属项目</label>
          <el-select
            v-model="moveProjectForm.targetProjectId"
            placeholder="请选择目标项目"
            class="w-full"
          >
            <el-option
              v-for="project in moveTargetProjects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </div>
      </div>
      <template #footer>
        <div class="flex justify-end gap-2">
          <button
            type="button"
            class="ec-btn ec-btn-secondary"
            @click="closeMoveProjectDialog"
          >
            取消
          </button>
          <button
            type="button"
            class="ec-btn ec-btn-primary"
            :disabled="!canSubmitMoveProject || isMovingMemberProject"
            @click="handleSubmitMoveProject"
          >
            {{ isMovingMemberProject ? '保存中…' : '保存' }}
          </button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

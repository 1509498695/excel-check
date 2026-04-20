<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'

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
import StatPill from '../components/shell/StatPill.vue'

const DEFAULT_PROJECT_NAME = '默认项目'

type StepIndex = 1 | 2 | 3
type StatTone = 'pending' | 'active' | 'done' | 'warn' | 'error'

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
const projectKeyword = ref('')
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

const filteredProjects = computed(() => {
  const keyword = projectKeyword.value.trim().toLowerCase()
  if (!keyword) return projects.value
  return projects.value.filter((project) => project.name.toLowerCase().includes(keyword))
})

const superAdminCount = computed(() => members.value.filter((m) => m.is_super_admin).length)

const overviewItems = computed<
  Array<{
    label: string
    value: number | string
    pendingHint: string
    readyHint: string
    pendingTone: StatTone
    readyTone: StatTone
    isReady: boolean
  }>
>(() => [
  {
    label: '项目总数',
    value: projects.value.length,
    pendingHint: '未加载',
    readyHint: '已就绪',
    pendingTone: 'pending',
    readyTone: 'done',
    isReady: projects.value.length > 0,
  },
  {
    label: '当前项目成员',
    value: members.value.length,
    pendingHint: '待选择项目',
    readyHint: '已加载',
    pendingTone: 'pending',
    readyTone: 'done',
    isReady: members.value.length > 0,
  },
  {
    label: '超级管理员',
    value: superAdminCount.value,
    pendingHint: '当前项目无',
    readyHint: '已配置',
    pendingTone: 'pending',
    readyTone: 'done',
    isReady: superAdminCount.value > 0,
  },
  {
    label: '我的归属项目',
    value: auth.currentProjectName || '未设置',
    pendingHint: '未设置',
    readyHint: '系统保留',
    pendingTone: 'pending',
    readyTone: 'done',
    isReady: Boolean(auth.currentProjectName),
  },
])

function getSectionStatusLabel(step: StepIndex): string {
  if (step === 1) {
    return projects.value.length ? '已完成' : '待配置'
  }
  if (step === 2) {
    return selectedProject.value ? '已完成' : '待配置'
  }
  return members.value.length ? '已完成' : '待配置'
}

function getSectionStatusTone(step: StepIndex): 'pending' | 'done' {
  return getSectionStatusLabel(step) === '已完成' ? 'done' : 'pending'
}

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
  if (member.is_super_admin) {
    return auth.isSuperAdmin && member.user_id === auth.user?.id && moveTargetProjects.value.length > 0
  }
  if (member.role !== 'user') {
    return false
  }
  return moveTargetProjects.value.length > 0
}

function canRemoveMember(member: ProjectMember): boolean {
  if (!selectedProject.value) {
    return false
  }
  if (member.user_id === auth.user?.id) {
    return false
  }
  if (isDefaultProject(selectedProject.value) && !auth.isSuperAdmin) {
    return false
  }
  return true
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

function isDefaultProject(project: ProjectDetail): boolean {
  return project.name === DEFAULT_PROJECT_NAME
}

function getMemberRoleClass(member: ProjectMember): string {
  if (member.is_super_admin) {
    return 'bg-danger-soft text-danger'
  }
  if (member.role === 'admin') {
    return 'bg-warning-soft text-warning'
  }
  return 'bg-accent-soft text-accent-ink'
}

function getMemberRoleLabel(member: ProjectMember): string {
  if (member.is_super_admin) {
    return '超级管理员'
  }
  return member.role === 'admin' ? '项目管理员' : '普通用户'
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

    <div class="flex-1 overflow-y-auto px-8 py-8 flex flex-col gap-6">
      <!-- KPI -->
      <section aria-label="概览" class="grid grid-cols-4 gap-4">
        <!-- 保留原有业务逻辑：概览卡仍基于 overviewItems 计算结果遍历渲染 -->
        <StatPill
          v-for="item in overviewItems"
          :key="item.label"
          :label="item.label"
          :value="item.value"
          :status-label="item.isReady ? item.readyHint : item.pendingHint"
          :status-tone="item.isReady ? item.readyTone : item.pendingTone"
        />
      </section>

      <!-- 单列全宽通栏：01 项目列表 / 02 项目详情 / 03 项目成员 依次堆叠 -->
      <!-- 01 项目列表 -->
      <article
        v-loading="isLoadingProjects"
        class="rounded-card border border-gray-200 bg-card shadow-card-1"
      >
        <div class="border-t-2 border-transparent px-5 py-4">
          <div class="flex items-start justify-between gap-4 border-b border-gray-200 pb-3">
            <SectionHeader
              variant="workbench"
              step="01"
              title="项目列表"
              :description="auth.isSuperAdmin ? '全部项目，可创建、编辑或删除' : '仅展示你可管理的项目'"
              :status-label="getSectionStatusLabel(1)"
              :status-tone="getSectionStatusTone(1)"
            />
            <div class="workbench-section-toolbar__actions shrink-0">
              <el-input
                v-model="projectKeyword"
                placeholder="搜索项目"
                :prefix-icon="Search"
                clearable
                size="default"
                class="w-[260px]"
              />
              <button
                v-if="canCreateProject"
                type="button"
                class="ec-btn ec-btn-primary ec-btn-sm"
                @click="openCreateProjectDialog"
              >
                <Plus class="h-3.5 w-3.5" />
                新建项目
              </button>
            </div>
          </div>

          <div class="pt-4">
            <div
              v-if="!projects.length"
              class="rounded-lg border border-dashed border-gray-200 bg-canvas px-4 py-10 text-center text-[13px] text-ink-500"
            >
              暂无可管理项目
            </div>

            <div
              v-else-if="!filteredProjects.length"
              class="rounded-lg border border-dashed border-gray-200 bg-canvas px-4 py-10 text-center text-[13px] text-ink-500"
            >
              没有匹配「{{ projectKeyword }}」的项目
            </div>

            <nav v-else class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
              <!-- 保留原有业务逻辑：项目列表仍基于 filteredProjects 遍历，点击继续走原有选中与加载成员逻辑 -->
              <article
                v-for="project in filteredProjects"
                :key="project.id"
                class="group relative flex min-h-[112px] cursor-pointer flex-col justify-between rounded-lg border bg-white p-4 transition"
                :class="
                  selectedProject?.id === project.id
                    ? 'border-blue-500 bg-blue-50 border-l-[3px] border-l-blue-500 ring-1 ring-blue-100'
                    : 'border-gray-200 border-l-[3px] border-l-transparent hover:border-gray-300'
                "
                @click="selectProject(project)"
              >
                <div>
                  <div class="flex items-start justify-between gap-2">
                    <div
                      class="truncate text-[14px] font-semibold"
                      :class="selectedProject?.id === project.id ? 'text-accent-ink' : 'text-ink-900'"
                    >
                      {{ project.name }}
                    </div>
                    <div class="flex shrink-0 items-center gap-1">
                      <span
                        v-if="selectedProject?.id === project.id"
                        class="rounded-md bg-blue-100 px-1.5 py-0.5 text-[11px] font-semibold text-accent-ink"
                      >
                        当前
                      </span>
                      <span
                        v-if="isDefaultProject(project)"
                        class="rounded-md bg-gray-100 px-1.5 py-0.5 text-[11px] font-semibold text-ink-700"
                      >
                        默认
                      </span>
                    </div>
                  </div>
                  <div class="mt-1 text-[12px] text-ink-500">
                    成员 {{ project.member_count ?? 0 }} · {{ formatDate(project.created_at) }}
                  </div>
                </div>
                <div class="mt-3 flex items-center justify-end gap-3">
                  <button
                    type="button"
                    class="ec-action-link"
                    @click.stop="openEditProjectDialog(project)"
                  >
                    编辑
                  </button>
                  <button
                    v-if="auth.isSuperAdmin && !isDefaultProject(project)"
                    type="button"
                    class="ec-action-link-danger"
                    @click.stop="handleDeleteProject(project)"
                  >
                    删除
                  </button>
                </div>
              </article>
            </nav>
          </div>
        </div>
      </article>

      <!-- 02 项目详情 -->
      <article class="rounded-card border border-gray-200 bg-card shadow-card-1">
        <div class="border-t-2 border-transparent px-5 py-4">
          <div class="flex items-start justify-between gap-4 border-b border-gray-200 pb-3">
            <SectionHeader
              variant="workbench"
              step="02"
              title="项目详情"
              :description="selectedProject ? (selectedProject.description || '无项目描述') : '请在左侧选择项目'"
              :status-label="getSectionStatusLabel(2)"
              :status-tone="getSectionStatusTone(2)"
            />
            <div class="workbench-section-toolbar__actions shrink-0">
              <button
                v-if="selectedProject && auth.isSuperAdmin && !isDefaultProject(selectedProject)"
                type="button"
                class="ec-btn ec-btn-secondary ec-btn-sm"
                @click="handleDeleteProject(selectedProject)"
              >
                删除项目
              </button>
              <button
                v-if="selectedProject"
                type="button"
                class="ec-btn ec-btn-primary ec-btn-sm"
                @click="openEditProjectDialog(selectedProject)"
              >
                编辑项目
              </button>
            </div>
          </div>

          <div class="pt-4">
            <div
              v-if="!selectedProject"
              class="flex flex-col items-center justify-center gap-2 py-10 text-center text-[13px] text-ink-500"
            >
              <div class="flex h-10 w-10 items-center justify-center rounded-full bg-gray-50">
                <svg class="h-4 w-4 text-ink-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M4 4h16v16H4z M4 9h16" />
                </svg>
              </div>
              <div>当前没有可管理项目</div>
            </div>

            <div v-else class="grid grid-cols-1 gap-x-6 gap-y-5 md:grid-cols-2 xl:grid-cols-4">
              <div>
                <div class="mb-1.5 text-[12px] font-medium text-ink-500">项目名称</div>
                <div class="rounded-md border border-gray-200 bg-white px-4 py-2 text-[14px] font-semibold text-ink-900">
                  {{ selectedProject.name }}
                </div>
              </div>
              <div>
                <div class="mb-1.5 text-[12px] font-medium text-ink-500">归属类型</div>
                <div class="rounded-md border border-gray-200 bg-white px-4 py-2 text-[14px] text-ink-900">
                  {{ isDefaultProject(selectedProject) ? '系统保留' : '自定义项目' }}
                </div>
              </div>
              <div>
                <div class="mb-1.5 text-[12px] font-medium text-ink-500">成员数</div>
                <div class="rounded-md border border-gray-200 bg-white px-4 py-2 font-mono text-[14px] text-ink-900">
                  {{ selectedProject.member_count ?? members.length }}
                </div>
              </div>
              <div>
                <div class="mb-1.5 text-[12px] font-medium text-ink-500">创建时间</div>
                <div class="rounded-md border border-gray-200 bg-white px-4 py-2 font-mono text-[13px] text-ink-700">
                  {{ formatDate(selectedProject.created_at) }}
                </div>
              </div>
              <div class="md:col-span-2 xl:col-span-4">
                <div class="mb-1.5 text-[12px] font-medium text-ink-500">项目描述</div>
                <div class="min-h-[64px] whitespace-pre-wrap rounded-md border border-gray-200 bg-white px-4 py-2.5 text-[13px] leading-relaxed text-ink-700">
                  {{ selectedProject.description || '无项目描述' }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </article>

      <!-- 03 项目成员 -->
      <article
        v-loading="isLoadingMembers"
        class="rounded-card border border-gray-200 bg-card shadow-card-1"
      >
        <div class="border-t-2 border-transparent px-5 py-4">
          <div class="flex items-start justify-between gap-4 border-b border-gray-200 pb-3">
            <SectionHeader
              variant="workbench"
              step="03"
              title="项目成员"
              :description="selectedProject ? `共 ${members.length} 位成员，可调整角色或归属项目` : '请先选择项目'"
              :status-label="getSectionStatusLabel(3)"
              :status-tone="getSectionStatusTone(3)"
            />
          </div>

          <div class="pt-4">
            <!-- 未选择项目 -->
            <div
              v-if="!selectedProject"
              class="rounded-md border border-dashed border-gray-200 bg-white px-4 py-10 text-center text-[13px] text-ink-500"
            >
              请在上方项目列表中选择一个项目，即可查看成员。
            </div>

            <!-- 已选项目但成员为空 -->
            <div
              v-else-if="!members.length"
              class="rounded-md border border-dashed border-gray-200 bg-white px-4 py-10 text-center text-[13px] text-ink-500"
            >
              该项目尚未邀请任何成员加入。
            </div>

            <!-- 成员表（极浅完整网格线） -->
            <div v-else class="overflow-hidden rounded-md border border-gray-200">
              <table class="admin-member-table w-full border-collapse text-[13px]">
                <thead class="bg-gray-50">
                  <tr>
                    <th class="w-[220px] border border-gray-100 px-4 py-2.5 text-left text-[12px] font-medium uppercase tracking-wider text-ink-500">
                      用户名
                    </th>
                    <th class="w-[160px] border border-gray-100 px-4 py-2.5 text-left text-[12px] font-medium uppercase tracking-wider text-ink-500">
                      角色
                    </th>
                    <th class="w-[200px] border border-gray-100 px-4 py-2.5 text-left text-[12px] font-medium uppercase tracking-wider text-ink-500">
                      归属项目
                    </th>
                    <th class="w-[220px] border border-gray-100 px-4 py-2.5 text-left text-[12px] font-medium uppercase tracking-wider text-ink-500">
                      加入时间
                    </th>
                    <th class="border border-gray-100 px-4 py-2.5 text-right text-[12px] font-medium uppercase tracking-wider text-ink-500">
                      操作
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <!-- 保留原有业务逻辑：成员表行级操作仍走原有链路 -->
                  <tr
                    v-for="row in members"
                    :key="row.user_id"
                    class="bg-white transition hover:bg-gray-50"
                  >
                    <td class="border border-gray-100 px-4 py-3 align-middle truncate font-medium text-ink-900">
                      {{ row.username }}
                    </td>
                    <td class="border border-gray-100 px-4 py-3 align-middle">
                      <span
                        class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[12px] font-medium"
                        :class="getMemberRoleClass(row)"
                      >
                        {{ getMemberRoleLabel(row) }}
                      </span>
                    </td>
                    <td class="border border-gray-100 px-4 py-3 align-middle truncate text-ink-700">
                      {{ row.primary_project_name ?? '-' }}
                    </td>
                    <td class="border border-gray-100 px-4 py-3 align-middle font-mono text-[12px] text-ink-500">
                      {{ formatDate(row.joined_at) }}
                    </td>
                    <td class="border border-gray-100 px-4 py-3 align-middle text-right">
                      <div class="table-actions">
                        <button
                          v-if="auth.isSuperAdmin && row.user_id !== auth.user?.id"
                          type="button"
                          class="ec-action-link"
                          @click="handleResetPassword(row)"
                        >
                          重置密码
                        </button>
                        <button
                          v-if="row.is_super_admin && canMoveMemberProject(row)"
                          type="button"
                          class="ec-action-link"
                          @click="openMoveProjectDialog(row)"
                        >
                          调整归属
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
                            v-if="canRemoveMember(row)"
                            type="button"
                            class="ec-action-link-danger"
                            @click="handleRemoveMember(row)"
                          >
                            删除
                          </button>
                        </template>
                        <span
                          v-if="
                            row.is_super_admin &&
                            !(auth.isSuperAdmin && row.user_id !== auth.user?.id) &&
                            !canMoveMemberProject(row)
                          "
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
        </div>
      </article>
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

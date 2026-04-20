<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Edit, Plus } from '@element-plus/icons-vue'

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
  <div class="admin-page">
    <header class="admin-header">
      <div>
        <h1>管理后台</h1>
        <p>{{ auth.isSuperAdmin ? '左侧选项目，右侧管理成员与权限。' : '在右侧工作区管理当前项目成员。' }}</p>
      </div>
      <el-button
        v-if="canCreateProject"
        type="primary"
        :icon="Plus"
        @click="openCreateProjectDialog"
      >
        创建项目
      </el-button>
    </header>

    <div class="admin-layout">
      <section class="admin-projects" v-loading="isLoadingProjects">
        <h2>{{ auth.isSuperAdmin ? '项目列表' : '可管理项目' }}</h2>
        <div v-if="!projects.length" class="admin-empty">暂无可管理项目</div>
        <!-- // 保留原有业务逻辑：项目列表仍基于 projects 遍历，点击继续走原有选中与加载成员逻辑 -->
        <div
          v-for="project in projects"
          :key="project.id"
          class="admin-project-card"
          :class="{ 'is-active': selectedProject?.id === project.id }"
          @click="selectProject(project)"
        >
          <strong>{{ project.name }}</strong>
          <div class="admin-project-meta">
            <span>成员 {{ project.member_count ?? 0 }}</span>
            <span>{{ formatDate(project.created_at) }}</span>
          </div>
          <p v-if="project.description">{{ project.description }}</p>
          <div class="admin-project-actions">
            <el-button
              link
              type="primary"
              :icon="Edit"
              @click.stop="openEditProjectDialog(project)"
            >
              编辑项目
            </el-button>
            <el-button
              v-if="auth.isSuperAdmin && !isDefaultProject(project)"
              link
              type="danger"
              :icon="Delete"
              @click.stop="handleDeleteProject(project)"
            >
              删除项目
            </el-button>
          </div>
        </div>
      </section>

      <section class="admin-members" v-loading="isLoadingMembers">
        <div v-if="!selectedProject" class="admin-empty">
          当前没有可管理项目
        </div>
        <template v-else>
          <h2>{{ selectedProject.name }} / 成员</h2>
          <el-table :data="members" class="workbench-table">
            <el-table-column prop="username" label="用户名" min-width="120" />
            <el-table-column label="角色" min-width="120">
              <template #default="{ row }">
                <el-tag
                  :type="row.is_super_admin ? 'danger' : row.role === 'admin' ? 'warning' : 'info'"
                  effect="light"
                  round
                >
                  {{ row.is_super_admin ? '超级管理员' : row.role === 'admin' ? '项目管理员' : '普通用户' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="归属项目" min-width="140">
              <template #default="{ row }">
                {{ row.primary_project_name ?? '-' }}
              </template>
            </el-table-column>
            <el-table-column label="加入时间" min-width="180">
              <template #default="{ row }">
                {{ formatDate(row.joined_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="380" fixed="right">
              <template #default="{ row }">
                <div class="table-actions">
                  <el-button
                    v-if="auth.isSuperAdmin && row.user_id !== auth.user?.id"
                    link
                    type="warning"
                    @click="handleResetPassword(row)"
                  >
                    重置密码
                  </el-button>
                  <template v-if="!row.is_super_admin">
                    <el-button
                      v-if="row.role !== 'admin'"
                      link
                      type="primary"
                      @click="handleSetRole(row, 'admin')"
                    >
                      设为管理员
                    </el-button>
                    <el-button
                      v-else
                      link
                      type="primary"
                      @click="handleSetRole(row, 'user')"
                    >
                      设为普通用户
                    </el-button>
                    <el-button
                      v-if="canMoveMemberProject(row)"
                      link
                      type="primary"
                      @click="openMoveProjectDialog(row)"
                    >
                      调整归属项目
                    </el-button>
                    <el-button
                      v-if="row.user_id !== auth.user?.id"
                      link
                      type="danger"
                      @click="handleRemoveMember(row)"
                    >
                      删除
                    </el-button>
                  </template>
                  <span
                    v-if="row.is_super_admin && !(auth.isSuperAdmin && row.user_id !== auth.user?.id)"
                    class="admin-no-action"
                  >
                    -
                  </span>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </template>
      </section>
    </div>

    <el-dialog
      v-model="isProjectDialogVisible"
      :title="projectDialogTitle"
      width="520px"
      destroy-on-close
      class="project-dialog"
    >
      <el-form label-position="top" class="dialog-form">
        <el-form-item label="项目名称" required>
          <el-input
            v-model="projectForm.name"
            placeholder="请输入项目名称"
            maxlength="128"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="项目描述">
          <el-input
            v-model="projectForm.description"
            type="textarea"
            :rows="4"
            maxlength="500"
            show-word-limit
            placeholder="请输入项目描述（可选）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="closeProjectDialog">取消</el-button>
          <el-button
            type="primary"
            :loading="isSavingProject"
            :disabled="!canSubmitProject"
            @click="handleSubmitProject"
          >
            {{ projectDialogMode === 'create' ? '创建项目' : '保存修改' }}
          </el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="isMoveProjectDialogVisible"
      title="调整归属项目"
      width="480px"
      destroy-on-close
    >
      <el-form label-position="top" class="dialog-form">
        <el-form-item label="成员">
          <el-input :model-value="moveProjectForm.username" disabled />
        </el-form-item>
        <el-form-item label="目标归属项目" required>
          <el-select
            v-model="moveProjectForm.targetProjectId"
            placeholder="请选择目标项目"
            class="full-width"
          >
            <el-option
              v-for="project in moveTargetProjects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="closeMoveProjectDialog">取消</el-button>
          <el-button
            type="primary"
            :loading="isMovingMemberProject"
            :disabled="!canSubmitMoveProject"
            @click="handleSubmitMoveProject"
          >
            保存
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

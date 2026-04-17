<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

import {
  apiCreateProject,
  apiListProjectMembers,
  apiListProjects,
  apiRemoveMember,
  apiResetUserPassword,
  apiSetMemberRole,
} from '../api/admin'
import { useAuthStore } from '../store/auth'
import type { ProjectDetail, ProjectMember } from '../types/auth'

const auth = useAuthStore()
const projects = ref<ProjectDetail[]>([])
const selectedProject = ref<ProjectDetail | null>(null)
const members = ref<ProjectMember[]>([])
const isLoadingProjects = ref(false)
const isLoadingMembers = ref(false)

onMounted(async () => {
  await loadProjects()
})

async function loadProjects(): Promise<void> {
  isLoadingProjects.value = true
  try {
    const response = await apiListProjects()
    projects.value = response.data
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '加载项目列表失败')
  } finally {
    isLoadingProjects.value = false
  }
}

async function selectProject(project: ProjectDetail): Promise<void> {
  selectedProject.value = project
  isLoadingMembers.value = true
  try {
    const response = await apiListProjectMembers(project.id)
    members.value = response.data
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '加载成员列表失败')
    members.value = []
  } finally {
    isLoadingMembers.value = false
  }
}

async function handleCreateProject(): Promise<void> {
  try {
    const result = await ElMessageBox.prompt('输入项目名称', '创建项目', {
      confirmButtonText: '创建',
      cancelButtonText: '取消',
      inputValidator: (value) => Boolean(value?.trim()) || '项目名称不能为空',
    })
    await apiCreateProject(result.value.trim(), '')
    ElMessage.success('项目创建成功')
    await loadProjects()
  } catch {
    // 取消
  }
}

async function handleSetRole(member: ProjectMember, role: string): Promise<void> {
  if (!selectedProject.value) return
  try {
    await apiSetMemberRole(selectedProject.value.id, member.user_id, role)
    ElMessage.success(`已将 ${member.username} 设为${role === 'admin' ? '管理员' : '普通用户'}`)
    await selectProject(selectedProject.value)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '操作失败')
  }
}

async function handleRemoveMember(member: ProjectMember): Promise<void> {
  if (!selectedProject.value) return
  try {
    await ElMessageBox.confirm(
      `确认将 ${member.username} 从项目中移除？`,
      '移除成员',
      { confirmButtonText: '移除', cancelButtonText: '取消', type: 'warning' },
    )
    await apiRemoveMember(selectedProject.value.id, member.user_id)
    ElMessage.success('成员已移除')
    await selectProject(selectedProject.value)
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

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}
</script>

<template>
  <div class="admin-page">
    <header class="admin-header">
      <div>
        <h1>管理后台</h1>
        <p>项目管理与成员权限控制</p>
      </div>
      <el-button type="primary" :icon="Plus" @click="handleCreateProject">
        创建项目
      </el-button>
    </header>

    <div class="admin-layout">
      <section class="admin-projects" v-loading="isLoadingProjects">
        <h2>项目列表</h2>
        <div v-if="!projects.length" class="admin-empty">暂无项目</div>
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
        </div>
      </section>

      <section class="admin-members" v-loading="isLoadingMembers">
        <div v-if="!selectedProject" class="admin-empty">
          选择左侧项目查看成员
        </div>
        <template v-else>
          <h2>{{ selectedProject.name }} - 成员列表</h2>
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
            <el-table-column label="加入时间" min-width="180">
              <template #default="{ row }">
                {{ formatDate(row.joined_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="280" fixed="right">
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
                      v-if="row.user_id !== auth.user?.id"
                      link
                      type="danger"
                      @click="handleRemoveMember(row)"
                    >
                      移除
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
  </div>
</template>

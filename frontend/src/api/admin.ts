import type { ProjectDetail, ProjectMember } from '../types/auth'
import { apiFetch } from '../utils/apiFetch'

interface ListResponse<T> {
  code: number
  msg: string
  data: T[]
}

interface SingleResponse<T> {
  code: number
  msg: string
  data: T
}

export async function apiListProjects(): Promise<ListResponse<ProjectDetail>> {
  return apiFetch<ListResponse<ProjectDetail>>('/api/v1/admin/projects')
}

export async function apiCreateProject(
  name: string,
  description: string,
): Promise<SingleResponse<ProjectDetail>> {
  return apiFetch<SingleResponse<ProjectDetail>>('/api/v1/admin/projects', {
    method: 'POST',
    body: JSON.stringify({ name, description }),
  })
}

export async function apiUpdateProject(
  projectId: number,
  payload: { name?: string; description?: string },
): Promise<SingleResponse<ProjectDetail>> {
  return apiFetch<SingleResponse<ProjectDetail>>(`/api/v1/admin/projects/${projectId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function apiDeleteProject(projectId: number): Promise<void> {
  await apiFetch(`/api/v1/admin/projects/${projectId}`, {
    method: 'DELETE',
  })
}

export async function apiListProjectMembers(
  projectId: number,
): Promise<ListResponse<ProjectMember>> {
  return apiFetch<ListResponse<ProjectMember>>(
    `/api/v1/admin/projects/${projectId}/members`,
  )
}

export async function apiSetMemberRole(
  projectId: number,
  userId: number,
  role: string,
): Promise<{ code: number; msg: string }> {
  return apiFetch(`/api/v1/admin/projects/${projectId}/members/${userId}/role`, {
    method: 'PUT',
    body: JSON.stringify({ role }),
  })
}

export async function apiRemoveMember(
  projectId: number,
  userId: number,
): Promise<{ code: number; msg: string }> {
  return apiFetch(`/api/v1/admin/projects/${projectId}/members/${userId}`, {
    method: 'DELETE',
  })
}

export async function apiResetUserPassword(
  userId: number,
  newPassword: string,
): Promise<{ code: number; msg: string }> {
  return apiFetch(`/api/v1/admin/users/${userId}/reset-password`, {
    method: 'POST',
    body: JSON.stringify({ new_password: newPassword }),
  })
}

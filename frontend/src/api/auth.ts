import type { AuthResponse, MeResponse, ProjectPublicResponse } from '../types/auth'
import { apiFetch } from '../utils/apiFetch'

export async function apiRegister(
  username: string,
  password: string,
  projectId: number,
): Promise<AuthResponse> {
  return apiFetch<AuthResponse>('/api/v1/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, password, project_id: projectId }),
  })
}

export async function apiLogin(
  username: string,
  password: string,
): Promise<AuthResponse> {
  return apiFetch<AuthResponse>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export async function apiGetMe(): Promise<MeResponse> {
  return apiFetch<MeResponse>('/api/v1/auth/me')
}

export async function apiSwitchProject(
  projectId: number,
): Promise<AuthResponse> {
  return apiFetch<AuthResponse>(`/api/v1/auth/switch-project/${projectId}`, {
    method: 'POST',
  })
}

export async function apiChangePassword(
  oldPassword: string,
  newPassword: string,
): Promise<{ code: number; msg: string }> {
  return apiFetch('/api/v1/auth/change-password', {
    method: 'POST',
    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
  })
}

export async function apiListProjectsPublic(): Promise<ProjectPublicResponse> {
  return apiFetch<ProjectPublicResponse>('/api/v1/admin/projects-public')
}

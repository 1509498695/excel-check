import { defineStore } from 'pinia'

import { apiGetMe, apiLogin, apiRegister, apiSwitchProject } from '../api/auth'
import type { UserInfo, UserProjectInfo } from '../types/auth'
import { clearToken, getToken, setToken } from '../utils/apiFetch'

interface AuthState {
  user: UserInfo | null
  isReady: boolean
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    user: null,
    isReady: false,
  }),

  getters: {
    isLoggedIn(state): boolean {
      return state.user !== null
    },

    isSuperAdmin(state): boolean {
      return state.user?.is_super_admin ?? false
    },

    currentProjectId(state): number | null {
      return state.user?.current_project_id ?? null
    },

    currentRole(state): string | null {
      return state.user?.current_role ?? null
    },

    isProjectAdmin(): boolean {
      return this.isSuperAdmin || this.currentRole === 'admin'
    },

    userProjects(state): UserProjectInfo[] {
      return state.user?.projects ?? []
    },

    currentProjectName(): string {
      const pid = this.currentProjectId
      if (pid === null) return ''
      return this.userProjects.find((p) => p.project_id === pid)?.project_name ?? ''
    },
  },

  actions: {
    async register(username: string, password: string, projectId: number): Promise<void> {
      const response = await apiRegister(username, password, projectId)
      setToken(response.data.token)
      this.user = response.data.user
    },

    async login(username: string, password: string): Promise<void> {
      const response = await apiLogin(username, password)
      setToken(response.data.token)
      this.user = response.data.user
    },

    logout(): void {
      clearToken()
      this.user = null
    },

    async fetchMe(): Promise<void> {
      const token = getToken()
      if (!token) {
        this.user = null
        this.isReady = true
        return
      }

      try {
        const response = await apiGetMe()
        this.user = response.data
      } catch {
        clearToken()
        this.user = null
      } finally {
        this.isReady = true
      }
    },

    async switchProject(projectId: number): Promise<void> {
      const response = await apiSwitchProject(projectId)
      setToken(response.data.token)
      this.user = response.data.user
    },
  },
})

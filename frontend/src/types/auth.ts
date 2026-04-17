export interface UserProjectInfo {
  project_id: number
  project_name: string
  role: string
}

export interface UserInfo {
  id: number
  username: string
  is_super_admin: boolean
  current_project_id: number | null
  current_role: string | null
  projects: UserProjectInfo[]
}

export interface AuthResponse {
  code: number
  msg: string
  data: {
    token: string
    user: UserInfo
  }
}

export interface MeResponse {
  code: number
  msg: string
  data: UserInfo
}

export interface ProjectPublic {
  id: number
  name: string
}

export interface ProjectPublicResponse {
  code: number
  msg: string
  data: ProjectPublic[]
}

export interface ProjectDetail {
  id: number
  name: string
  description: string
  created_at: string | null
  member_count?: number
}

export interface ProjectMember {
  user_id: number
  username: string
  role: string
  is_super_admin: boolean
  primary_project_id: number | null
  primary_project_name: string | null
  joined_at: string | null
}

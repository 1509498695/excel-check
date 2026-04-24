/**
 * SVN 数据源相关接口包装。
 *
 * 注意：所有调用都自动携带 Bearer Token；后端鉴权失败用 403 表达，
 * 不会触发 apiFetch 的「自动跳登录」逻辑。
 *
 * `listSvnDirectory` 出错时抛 `SvnApiError`，携带 status 与 category，
 * 让前端 picker 弹窗能区分「需要凭据 / 目录不存在 / 网络异常」三类。
 */

import { apiFetch, getToken, clearToken } from '../utils/apiFetch'
import type { DataSource } from '../types/workbench'

export type SvnErrorCategory =
  | 'auth_failed'
  | 'not_found'
  | 'network'
  | 'timeout'
  | 'allowlist'
  | 'invalid_url'
  | 'unknown'

export class SvnApiError extends Error {
  status: number
  category: SvnErrorCategory

  constructor(message: string, status: number, category: SvnErrorCategory) {
    super(message)
    this.name = 'SvnApiError'
    this.status = status
    this.category = category
  }
}

function categoryFromStatus(status: number, hintCategory?: string): SvnErrorCategory {
  if (hintCategory && ['auth_failed', 'not_found', 'network', 'timeout'].includes(hintCategory)) {
    return hintCategory as SvnErrorCategory
  }
  if (status === 403) return 'auth_failed'
  if (status === 404) return 'not_found'
  if (status === 502) return 'network'
  if (status === 504) return 'timeout'
  return 'unknown'
}

export interface SvnEntry {
  kind: 'file' | 'dir'
  name: string
  size: number | null
  revision: number | null
  last_author: string
  last_modified_at: string
}

export interface SvnListResponse {
  code: number
  msg: string
  data: {
    dir_url: string
    host: string
    entries: SvnEntry[]
    credential_username: string
  }
}

export interface SvnCredentialItem {
  host: string
  username: string
  updated_at: string
  test_dir_url?: string | null
}

export interface SvnCredentialListResponse {
  code: number
  msg: string
  data: { items: SvnCredentialItem[] }
}

export interface SvnCredentialUpsertResponse {
  code: number
  msg: string
  data: {
    host: string
    username: string
    updated_at: string | null
    test_dir_url?: string | null
  }
}

export interface SvnRefreshResponse {
  code: number
  msg: string
  data: {
    source_id: string
    cached_path: string
    host: string
    revision: number | null
    last_updated_at: string | null
  }
}

export async function listSvnDirectory(dirUrl: string): Promise<SvnListResponse> {
  // 不走 apiFetch，因为我们需要从 HTTP 状态推断错误分类，并避免把 SVN 业务级
  // auth_failed（403）当成"前端登录态失效"处理。
  const token = getToken()
  const headers = new Headers({ 'Content-Type': 'application/json' })
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch('/api/v1/sources/svn-list', {
    method: 'POST',
    headers,
    body: JSON.stringify({ dir_url: dirUrl }),
  })

  if (response.status === 401) {
    // 真正的登录态失效：清 token 并跳登录，与 apiFetch 行为对齐。
    clearToken()
    window.location.href = '/login'
    throw new SvnApiError('登录态已过期，请重新登录。', 401, 'unknown')
  }

  if (!response.ok) {
    let detailMessage = `请求失败：${response.status}`
    let detailCategory: string | undefined
    try {
      const payload = (await response.json()) as { detail?: unknown }
      if (typeof payload.detail === 'string' && payload.detail.trim()) {
        detailMessage = payload.detail
      } else if (payload.detail && typeof payload.detail === 'object') {
        const detailObj = payload.detail as { msg?: unknown; category?: unknown }
        if (typeof detailObj.msg === 'string' && detailObj.msg.trim()) {
          detailMessage = detailObj.msg
        }
        if (typeof detailObj.category === 'string') {
          detailCategory = detailObj.category
        }
      }
    } catch {
      detailMessage = `${response.status} ${response.statusText}`
    }

    const category =
      response.status === 400 && /不在允许列表/.test(detailMessage)
        ? 'allowlist'
        : response.status === 400 && /URL/.test(detailMessage)
          ? 'invalid_url'
          : categoryFromStatus(response.status, detailCategory)
    throw new SvnApiError(detailMessage, response.status, category)
  }

  return (await response.json()) as SvnListResponse
}

export async function listSvnCredentialHosts(): Promise<SvnCredentialListResponse> {
  return apiFetch<SvnCredentialListResponse>('/api/v1/sources/svn-credentials')
}

export async function saveSvnCredentials(
  host: string,
  username: string,
  password: string,
  testDirUrl?: string,
): Promise<SvnCredentialUpsertResponse> {
  return apiFetch<SvnCredentialUpsertResponse>('/api/v1/sources/svn-credentials', {
    method: 'POST',
    body: JSON.stringify({ host, username, password, test_dir_url: testDirUrl }),
  })
}

export async function deleteSvnCredentials(host: string): Promise<void> {
  await apiFetch(`/api/v1/sources/svn-credentials/${encodeURIComponent(host)}`, {
    method: 'DELETE',
  })
}

export async function refreshRemoteSvnSource(
  source: DataSource,
): Promise<SvnRefreshResponse> {
  return apiFetch<SvnRefreshResponse>('/api/v1/sources/svn-refresh', {
    method: 'POST',
    body: JSON.stringify({ source }),
  })
}

/** 浏览器端工具：判断 dir_url 是否合法 http(s) 形式（容忍末尾无 `/`）。 */
export function isHttpDirUrl(input: string): boolean {
  const trimmed = input.trim()
  if (!trimmed) {
    return false
  }
  return /^https?:\/\/[^\s]+/i.test(trimmed)
}

/** 把无尾斜杠的目录 URL 补斜杠，与后端规整保持一致。 */
export function ensureTrailingSlash(input: string): string {
  const trimmed = input.trim()
  if (!trimmed) {
    return trimmed
  }
  return trimmed.endsWith('/') ? trimmed : `${trimmed}/`
}

/** 从 URL 中解析出 hostname，错误时返回空串。 */
export function parseSvnHost(input: string): string {
  try {
    return new URL(input.trim()).hostname.toLowerCase()
  } catch {
    return ''
  }
}

/** 当前 host 的默认测试目录。 */
export function getDefaultSvnCredentialTestDirUrl(host: string): string {
  const normalizedHost = host.trim().toLowerCase()
  if (normalizedHost === 'samosvn') {
    return 'https://samosvn/data/project/samo/GameDatas/'
  }
  return ''
}

/**
 * 封装 fetch，自动附加 Bearer Token 和 Content-Type。
 * 所有业务 API 统一通过此函数发起请求。
 */

const TOKEN_KEY = 'ec_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

function isAuthLoginOrRegisterUrl(url: string): boolean {
  return url.includes('/auth/login') || url.includes('/auth/register')
}

export async function apiFetch<T = unknown>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken()
  const headers = new Headers(options.headers)

  if (token && !isAuthLoginOrRegisterUrl(url)) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(url, { ...options, headers })

  if (!response.ok) {
    let message = '请求失败，请稍后重试。'
    try {
      const payload = (await response.json()) as { detail?: string }
      if (typeof payload.detail === 'string') {
        message = payload.detail
      }
    } catch {
      message = `${response.status} ${response.statusText}`
    }

    if (response.status === 401) {
      clearToken()
      if (!isAuthLoginOrRegisterUrl(url)) {
        window.location.href = '/login'
      }
      throw new Error(message)
    }

    throw new Error(message)
  }

  if (response.status === 204) {
    return undefined as T
  }

  const rawText = await response.text()
  if (!rawText.trim()) {
    return undefined as T
  }

  return JSON.parse(rawText) as T
}

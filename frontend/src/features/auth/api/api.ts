import { apiGet, apiPost } from '@/shared/lib/api'
import type { LoginResponse, MeResponse } from '@/features/auth/types'

export function fetchMe(): Promise<MeResponse> {
  return apiGet<MeResponse>('/api/auth/me')
}

export function login(username: string, password: string): Promise<LoginResponse> {
  return apiPost<LoginResponse>('/api/auth/login', { username, password })
}

export function logout(): Promise<void> {
  return apiPost<void>('/api/auth/logout')
}

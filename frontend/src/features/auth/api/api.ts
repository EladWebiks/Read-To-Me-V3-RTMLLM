import { apiGet, apiPost } from '@/shared/lib/api'
import type { MeResponse } from '@/features/auth/types'

export const GOOGLE_LOGIN_URL = '/api/auth/google/login'

export function fetchMe(): Promise<MeResponse> {
  return apiGet<MeResponse>('/api/auth/me')
}

export function logout(): Promise<void> {
  return apiPost<void>('/api/auth/logout')
}

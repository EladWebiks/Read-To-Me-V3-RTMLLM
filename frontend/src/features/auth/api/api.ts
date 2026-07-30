import { apiGet, apiPost, apiUrl } from '@/shared/lib/api'
import type { MeResponse } from '@/features/auth/types'

/**
 * Popup entry point for the Google code flow.
 *
 * Routed through `apiUrl` like every other call, so a configured
 * `VITE_API_URL` doesn't 404 against the frontend origin. Note the flow still
 * REQUIRES the API to be same-origin with the app: the callback page posts its
 * result with `postMessage(..., window.location.origin)`, i.e. targeting the
 * popup's *own* origin, so a cross-origin `VITE_API_URL` means the opener
 * never receives the message and sign-in hangs until the closed-poll fires.
 */
export const GOOGLE_LOGIN_URL = apiUrl('/api/auth/google/login')

export function fetchMe(): Promise<MeResponse> {
  return apiGet<MeResponse>('/api/auth/me')
}

export function logout(): Promise<void> {
  return apiPost<void>('/api/auth/logout')
}

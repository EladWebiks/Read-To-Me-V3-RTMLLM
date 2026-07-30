import { apiGet, apiPost, apiUrl } from '@/shared/lib/api'
import type { MeResponse } from '@/features/auth/types'

/**
 * Popup entry point for the Google code flow.
 *
 * Routed through `apiUrl` like every other call, so a configured
 * `VITE_API_URL` doesn't 404 against the frontend origin. Note the flow still
 * REQUIRES the API to be same-origin with the app: the callback page reports
 * its result over a BroadcastChannel (and opener postMessage), both scoped to
 * the popup's *own* origin, so a cross-origin `VITE_API_URL` means the result
 * never arrives and sign-in only recovers via the /me session poll — if the
 * cookie is readable cross-origin at all.
 */
export const GOOGLE_LOGIN_URL = apiUrl('/api/auth/google/login')

export function fetchMe(): Promise<MeResponse> {
  return apiGet<MeResponse>('/api/auth/me')
}

export function logout(): Promise<void> {
  return apiPost<void>('/api/auth/logout')
}

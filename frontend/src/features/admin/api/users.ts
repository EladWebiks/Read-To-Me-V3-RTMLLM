import type { Page } from '@/features/admin/types'
import { apiDelete, apiGet, apiPatch, apiPost } from '@/shared/lib/api'

/** Mirrors UserAdminRead (users/schemas.py) exactly. */
export type AdminUser = {
  id: string
  username: string
  email: string | null
  is_admin: boolean
  membership: string
  google_linked: boolean
  created_at: string
  deleted_at: string | null
}

export type AdminUserPatch = { is_admin?: boolean; membership?: string }

export function fetchAdminUsers(limit: number, offset: number): Promise<Page<AdminUser>> {
  return apiGet(`/api/admin/users?limit=${limit}&offset=${offset}`)
}

export function patchAdminUser(id: string, body: AdminUserPatch): Promise<AdminUser> {
  return apiPatch(`/api/admin/users/${id}`, body)
}

export function softDeleteAdminUser(id: string): Promise<AdminUser> {
  return apiDelete(`/api/admin/users/${id}`)
}

export function restoreAdminUser(id: string): Promise<AdminUser> {
  return apiPost(`/api/admin/users/${id}/restore`)
}

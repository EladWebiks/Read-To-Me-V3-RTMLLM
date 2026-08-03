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

export type AdminUserFilters = {
  q?: string
  membership?: string
  status?: 'all' | 'active' | 'deleted'
  admin?: 'any' | 'admin' | 'user'
  sort?: 'created_desc' | 'created_asc' | 'username_asc' | 'username_desc'
}

export function fetchAdminUsers(
  limit: number,
  offset: number,
  filters: AdminUserFilters = {},
): Promise<Page<AdminUser>> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  })
  if (filters.q?.trim()) params.set('q', filters.q.trim())
  if (filters.membership) params.set('membership', filters.membership)
  if (filters.status && filters.status !== 'all') params.set('status', filters.status)
  if (filters.admin && filters.admin !== 'any') params.set('admin', filters.admin)
  if (filters.sort && filters.sort !== 'created_desc') params.set('sort', filters.sort)
  return apiGet(`/api/admin/users?${params}`)
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

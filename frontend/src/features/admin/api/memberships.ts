import { apiGet, apiPatch, apiPost } from '@/shared/lib/api'

/** Mirrors MembershipAdminRead (users/schemas.py). */
export type AdminMembership = {
  slug: string
  label: string
  description: string | null
  price_label: string | null
  rank: number
  is_active: boolean
  is_default: boolean
  user_count: number
  updated_at: string
}

export type MembershipCreateBody = {
  slug: string
  label: string
  rank: number
  description?: string | null
  price_label?: string | null
}

export type MembershipPatchBody = Partial<{
  label: string
  description: string | null
  price_label: string | null
  rank: number
  is_default: true
  is_active: true
}>

export function fetchMemberships(): Promise<{ memberships: AdminMembership[] }> {
  return apiGet('/api/admin/memberships')
}

export function createMembership(body: MembershipCreateBody): Promise<AdminMembership> {
  return apiPost('/api/admin/memberships', body)
}

export function patchMembership(
  slug: string,
  patch: MembershipPatchBody,
): Promise<AdminMembership> {
  return apiPatch(`/api/admin/memberships/${encodeURIComponent(slug)}`, patch)
}

export function deactivateMembership(
  slug: string,
  migrateTo: string,
): Promise<AdminMembership> {
  return apiPost(`/api/admin/memberships/${encodeURIComponent(slug)}/deactivate`, {
    migrate_to: migrateTo,
  })
}

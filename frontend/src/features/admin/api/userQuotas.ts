import type { QuotaKindInfo } from '@/features/admin/api/membershipQuotas'
import { apiDelete, apiGet, apiPut } from '@/shared/lib/api'

/** Mirrors quotas/schemas.py::UserQuotaOverrideRead. */
export type UserQuotaOverride = {
  quota_kind: string
  limit_value: number
  updated_at: string
}

/** Registry + the user's tier limits (sparse) + their override rows. */
export type UserQuotas = {
  membership: string
  kinds: QuotaKindInfo[]
  tier_limits: Record<string, number>
  overrides: UserQuotaOverride[]
}

export function fetchUserQuotas(userId: string): Promise<UserQuotas> {
  return apiGet(`/api/admin/users/${encodeURIComponent(userId)}/quotas`)
}

export function putUserQuota(
  userId: string,
  kind: string,
  limitValue: number,
): Promise<UserQuotaOverride> {
  return apiPut(
    `/api/admin/users/${encodeURIComponent(userId)}/quotas/${encodeURIComponent(kind)}`,
    { limit_value: limitValue },
  )
}

export function deleteUserQuota(userId: string, kind: string): Promise<void> {
  return apiDelete(
    `/api/admin/users/${encodeURIComponent(userId)}/quotas/${encodeURIComponent(kind)}`,
  )
}

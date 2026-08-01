import { apiDelete, apiGet, apiPut } from '@/shared/lib/api'

/** Mirrors quotas/schemas.py. */
export type QuotaKindInfo = {
  kind: string
  label: string
  unit: string
  window: 'month' | 'standing'
}

export type MembershipQuotaRow = {
  membership: string
  quota_kind: string
  limit_value: number
  updated_at: string
}

export type MembershipQuotasResponse = {
  kinds: QuotaKindInfo[]
  quotas: MembershipQuotaRow[]
}

export function fetchMembershipQuotas(): Promise<MembershipQuotasResponse> {
  return apiGet('/api/admin/membership-quotas')
}

export function putMembershipQuota(
  membership: string,
  kind: string,
  limitValue: number,
): Promise<MembershipQuotaRow> {
  return apiPut(
    `/api/admin/membership-quotas/${encodeURIComponent(membership)}/${encodeURIComponent(kind)}`,
    { limit_value: limitValue },
  )
}

export function deleteMembershipQuota(membership: string, kind: string): Promise<void> {
  return apiDelete(
    `/api/admin/membership-quotas/${encodeURIComponent(membership)}/${encodeURIComponent(kind)}`,
  )
}

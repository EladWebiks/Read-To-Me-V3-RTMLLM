import { apiGet, apiPatch } from '@/shared/lib/api'
import type { PolicyFieldKey } from '@/features/admin/logic/policyFields'

/** Mirrors MembershipPolicyRead (orchestration/schemas.py). */
export type MembershipPolicy = {
  membership: string
  updated_at: string
} & Record<PolicyFieldKey, number | null>

export type MembershipPoliciesResponse = {
  policies: MembershipPolicy[]
  inherited: Record<string, number>
}

export type PolicyPatch = Partial<Record<PolicyFieldKey, number | null>>

export function fetchMembershipPolicies(): Promise<MembershipPoliciesResponse> {
  return apiGet('/api/admin/membership-policies')
}

export function patchMembershipPolicy(
  membership: string,
  patch: PolicyPatch,
): Promise<MembershipPolicy> {
  return apiPatch(
    `/api/admin/membership-policies/${encodeURIComponent(membership)}`,
    patch,
  )
}

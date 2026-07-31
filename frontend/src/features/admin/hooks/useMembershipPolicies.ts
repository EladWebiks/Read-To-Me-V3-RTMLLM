import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  fetchMembershipPolicies,
  patchMembershipPolicy,
  type PolicyPatch,
} from '@/features/admin/api/membershipPolicies'

export const membershipPoliciesKey = ['admin', 'membership-policies'] as const

export function useMembershipPolicies() {
  return useQuery({
    queryKey: membershipPoliciesKey,
    queryFn: fetchMembershipPolicies,
  })
}

export function usePatchMembershipPolicy() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ membership, patch }: { membership: string; patch: PolicyPatch }) =>
      patchMembershipPolicy(membership, patch),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: membershipPoliciesKey }),
  })
}

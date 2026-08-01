import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createMembership,
  deactivateMembership,
  fetchMemberships,
  patchMembership,
  type MembershipCreateBody,
  type MembershipPatchBody,
} from '@/features/admin/api/memberships'
import { membershipPoliciesKey } from '@/features/admin/hooks/useMembershipPolicies'
import { usersKey as adminUsersKey } from '@/features/admin/hooks/useAdminUsers'

export const membershipsKey = ['admin', 'memberships'] as const

export function useMemberships() {
  return useQuery({
    queryKey: membershipsKey,
    queryFn: fetchMemberships,
  })
}

function useInvalidateMemberships() {
  const queryClient = useQueryClient()
  return () => {
    queryClient.invalidateQueries({ queryKey: membershipsKey })
    queryClient.invalidateQueries({ queryKey: membershipPoliciesKey })
    queryClient.invalidateQueries({ queryKey: adminUsersKey })
  }
}

export function useCreateMembership() {
  const invalidate = useInvalidateMemberships()
  return useMutation({
    mutationFn: (body: MembershipCreateBody) => createMembership(body),
    onSuccess: invalidate,
  })
}

export function usePatchMembership() {
  const invalidate = useInvalidateMemberships()
  return useMutation({
    mutationFn: ({ slug, patch }: { slug: string; patch: MembershipPatchBody }) =>
      patchMembership(slug, patch),
    onSuccess: invalidate,
  })
}

export function useDeactivateMembership() {
  const invalidate = useInvalidateMemberships()
  return useMutation({
    mutationFn: ({ slug, migrateTo }: { slug: string; migrateTo: string }) =>
      deactivateMembership(slug, migrateTo),
    onSuccess: invalidate,
  })
}

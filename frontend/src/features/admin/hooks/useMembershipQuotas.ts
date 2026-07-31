import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  deleteMembershipQuota,
  fetchMembershipQuotas,
  putMembershipQuota,
} from '@/features/admin/api/membershipQuotas'

export const membershipQuotasKey = ['admin', 'membership-quotas'] as const

export function useMembershipQuotas() {
  return useQuery({ queryKey: membershipQuotasKey, queryFn: fetchMembershipQuotas })
}

export type QuotaChange = { membership: string; kind: string; limit: number | null }

export function useSaveQuota() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ membership, kind, limit }: QuotaChange) =>
      limit === null
        ? deleteMembershipQuota(membership, kind)
        : putMembershipQuota(membership, kind, limit).then(() => undefined),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: membershipQuotasKey }),
  })
}

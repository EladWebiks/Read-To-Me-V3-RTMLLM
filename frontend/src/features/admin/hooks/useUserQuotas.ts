import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  deleteUserQuota,
  fetchUserQuotas,
  putUserQuota,
} from '@/features/admin/api/userQuotas'

export const userQuotasKey = (userId: string) =>
  ['admin', 'users', userId, 'quotas'] as const

export function useUserQuotas(userId: string, enabled: boolean) {
  return useQuery({
    queryKey: userQuotasKey(userId),
    queryFn: () => fetchUserQuotas(userId),
    enabled,
  })
}

/** A null limit clears the override so the tier limit applies again. */
export function useSetUserQuota(userId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ kind, limit }: { kind: string; limit: number | null }) =>
      limit === null
        ? deleteUserQuota(userId, kind)
        : putUserQuota(userId, kind, limit).then(() => undefined),
    onSettled: () => queryClient.invalidateQueries({ queryKey: userQuotasKey(userId) }),
  })
}

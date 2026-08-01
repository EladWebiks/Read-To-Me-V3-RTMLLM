import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { meQueryKey } from '@/features/auth/hooks'
import { fetchPlans, switchPlan } from '../api/plans'
import { meUsageKey } from './useMeUsage'

export const plansKey = ['me', 'plans'] as const

export function usePlans() {
  return useQuery({ queryKey: plansKey, queryFn: fetchPlans })
}

export function useSwitchPlan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (slug: string) => switchPlan(slug),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: plansKey })
      // Switching tiers changes the user's quotas, so the usage meters must refetch too.
      queryClient.invalidateQueries({ queryKey: meUsageKey })
      // The navbar avatar renders membership from the auth `me` query — it
      // must refetch too, or it keeps showing the pre-switch plan.
      queryClient.invalidateQueries({ queryKey: meQueryKey })
    },
  })
}

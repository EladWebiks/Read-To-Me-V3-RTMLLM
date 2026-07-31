import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
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
      queryClient.invalidateQueries({ queryKey: meUsageKey })
    },
  })
}

import { useQuery } from '@tanstack/react-query'
import { fetchMeUsage } from '../api/meUsage'

export const meUsageKey = ['me', 'usage'] as const

export function useMeUsage() {
  return useQuery({ queryKey: meUsageKey, queryFn: fetchMeUsage, staleTime: 30_000 })
}

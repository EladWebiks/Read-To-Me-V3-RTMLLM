import { useQuery } from '@tanstack/react-query'
import {
  fetchExecutions,
  fetchUsageByUser,
  fetchUsageOverview,
} from '@/features/admin/api/usage'
import type { Period } from '@/features/admin/logic/period'

export function useUsageOverview(period: Period) {
  return useQuery({
    queryKey: ['admin', 'usage', 'summary', period],
    queryFn: () => fetchUsageOverview(period),
  })
}

export function useUsageByUser(period: Period, limit: number, offset: number) {
  return useQuery({
    queryKey: ['admin', 'usage', 'by-user', period, limit, offset],
    queryFn: () => fetchUsageByUser(period, limit, offset),
  })
}

export function useExecutions(period: Period, limit: number, offset: number) {
  return useQuery({
    queryKey: ['admin', 'usage', 'executions', period, limit, offset],
    queryFn: () => fetchExecutions(period, limit, offset),
  })
}

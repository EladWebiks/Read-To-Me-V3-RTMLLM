import type { Period } from '@/features/admin/logic/period'
import type { Page } from '@/features/admin/types'
import { apiGet } from '@/shared/lib/api'

export type UsageBreakdown = {
  tokens_in: number
  tokens_out: number
  total_cost: number
  execution_count: number
}

export type ModelUsage = UsageBreakdown & { provider: string; model: string }
export type TaskUsage = UsageBreakdown & { task: string }
export type UserUsage = UsageBreakdown & {
  user_id: string
  username: string | null
  membership: string | null
  month_tokens: number
  month_cost: number
  llm_tokens_limit: number | null
  llm_cost_limit: number | null
}

export type UsageOverview = UsageBreakdown & {
  period_start: string
  period_end: string
  by_model: ModelUsage[]
  by_task: TaskUsage[]
}

export type LlmExecutionRow = {
  id: string
  user_id: string
  conversation_id: string | null
  task: string
  provider: string
  model: string
  tokens_in: number
  tokens_out: number
  cost: number
  latency_ms: number
  status: string
  fallback_used: boolean
  error: string | null
  created_at: string
}

function rangeQuery(period: Period): string {
  return `from=${encodeURIComponent(period.from)}&to=${encodeURIComponent(period.to)}`
}

export function fetchUsageOverview(period: Period): Promise<UsageOverview> {
  return apiGet(`/api/admin/usage/summary?${rangeQuery(period)}`)
}

export function fetchUsageByUser(
  period: Period,
  limit: number,
  offset: number,
): Promise<Page<UserUsage>> {
  return apiGet(
    `/api/admin/usage/by-user?${rangeQuery(period)}&limit=${limit}&offset=${offset}`,
  )
}

export function fetchExecutions(
  period: Period,
  limit: number,
  offset: number,
): Promise<Page<LlmExecutionRow>> {
  return apiGet(
    `/api/admin/usage/executions?${rangeQuery(period)}&limit=${limit}&offset=${offset}`,
  )
}

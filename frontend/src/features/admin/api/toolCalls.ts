import type { Page } from '@/features/admin/types'
import { apiGet } from '@/shared/lib/api'

/** Mirrors AdminToolCallRead (admin/schemas.py). */
export type ToolCall = {
  id: string
  tool_name: string
  status: string
  risk_level: string
  confirmed_by_user: boolean
  duration_ms: number | null
  input: Record<string, unknown>
  output: Record<string, unknown> | null
  error: string | null
  user_id: string | null
  username: string | null
  email: string | null
  created_at: string
}

export type ToolCallFilterValues = {
  tool_name?: string
  status?: string
  risk_level?: string
  from?: string
  to?: string
}

export const RISK_LEVELS = ['read_only', 'low_risk', 'confirmation_required'] as const

export function fetchToolCalls(
  filters: ToolCallFilterValues,
  limit: number,
  offset: number,
): Promise<Page<ToolCall>> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  for (const [key, value] of Object.entries(filters)) {
    if (value) {
      params.set(key, value)
    }
  }
  return apiGet(`/api/admin/tool-calls?${params.toString()}`)
}

import { apiGet } from '@/shared/lib/api'

/** Mirrors usage/schemas.py::MeUsageResponse. */
export type MeUsageKind = {
  kind: string
  label: string
  unit: string
  window: 'month' | 'standing'
  used: number
  limit: number | null
}

export type MeUsage = {
  membership: string
  exempt: boolean
  as_of: string
  resets_at: string
  kinds: MeUsageKind[]
}

export function fetchMeUsage(): Promise<MeUsage> {
  return apiGet('/api/me/usage')
}

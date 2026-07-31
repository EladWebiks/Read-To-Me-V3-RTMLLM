import { apiGet, apiPost } from '@/shared/lib/api'

/** Mirrors PlansResponse (users/schemas.py). */
export type Plan = {
  slug: string
  label: string
  description: string | null
  price_label: string | null
  current: boolean
}

export type PlansResponse = {
  plans: Plan[]
  can_switch: boolean
}

export function fetchPlans(): Promise<PlansResponse> {
  return apiGet('/api/me/plans')
}

export function switchPlan(slug: string): Promise<unknown> {
  return apiPost('/api/me/membership', { membership: slug })
}

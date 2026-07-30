import { apiDelete, apiGet, apiPut } from '@/shared/lib/api'

/** Mirrors EffectiveSettingRead (runtime_config/schemas.py) exactly. */
export type EffectiveSetting = {
  key: string
  effective_value: unknown
  env_value: unknown
  overridden: boolean
  updated_by?: string | null
  updated_at?: string | null
}

export type SettingsListResponse = { settings: EffectiveSetting[] }

export type OverrideRead = {
  key: string
  value: unknown
  updated_by: string
  updated_at: string
}

export function fetchAdminSettings(): Promise<SettingsListResponse> {
  return apiGet('/api/admin/settings')
}

export function putAdminSetting(key: string, value: unknown): Promise<OverrideRead> {
  return apiPut(`/api/admin/settings/${encodeURIComponent(key)}`, { value })
}

export function deleteAdminSetting(key: string): Promise<void> {
  return apiDelete(`/api/admin/settings/${encodeURIComponent(key)}`)
}

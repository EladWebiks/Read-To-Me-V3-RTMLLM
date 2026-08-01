import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  deleteAdminSetting,
  fetchAdminSettings,
  putAdminSetting,
} from '@/features/admin/api/settings'

export const adminSettingsKey = ['admin', 'settings'] as const

export function useAdminSettings() {
  return useQuery({ queryKey: adminSettingsKey, queryFn: fetchAdminSettings })
}

export function useSetSetting() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ key, value }: { key: string; value: unknown }) =>
      putAdminSetting(key, value),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminSettingsKey }),
  })
}

export function useClearSetting() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteAdminSetting,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminSettingsKey }),
  })
}

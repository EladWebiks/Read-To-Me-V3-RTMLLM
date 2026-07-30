import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  fetchAdminUsers,
  patchAdminUser,
  restoreAdminUser,
  softDeleteAdminUser,
  type AdminUserPatch,
} from '@/features/admin/api/users'

const usersKey = ['admin', 'users'] as const

export function useAdminUsers(limit: number, offset: number) {
  return useQuery({
    queryKey: [...usersKey, limit, offset],
    queryFn: () => fetchAdminUsers(limit, offset),
  })
}

function useInvalidateUsers() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: usersKey })
}

export function usePatchUser() {
  const invalidate = useInvalidateUsers()
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: AdminUserPatch }) =>
      patchAdminUser(id, body),
    onSuccess: invalidate,
  })
}

export function useDeleteUser() {
  const invalidate = useInvalidateUsers()
  return useMutation({ mutationFn: softDeleteAdminUser, onSuccess: invalidate })
}

export function useRestoreUser() {
  const invalidate = useInvalidateUsers()
  return useMutation({ mutationFn: restoreAdminUser, onSuccess: invalidate })
}

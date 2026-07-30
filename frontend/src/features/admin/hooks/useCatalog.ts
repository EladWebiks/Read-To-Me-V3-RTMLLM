import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createModel,
  fetchCatalog,
  patchModel,
  patchProvider,
  type ModelCreateBody,
  type ModelPatchBody,
} from '@/features/admin/api/catalog'

export const catalogKey = ['admin', 'llm-catalog'] as const

export function useCatalog() {
  return useQuery({ queryKey: catalogKey, queryFn: fetchCatalog })
}

function useInvalidateCatalog() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: catalogKey })
}

export function usePatchProvider() {
  const invalidate = useInvalidateCatalog()
  return useMutation({
    mutationFn: ({ name, enabled }: { name: string; enabled: boolean }) =>
      patchProvider(name, enabled),
    onSuccess: invalidate,
  })
}

export function usePatchModel() {
  const invalidate = useInvalidateCatalog()
  return useMutation({
    mutationFn: ({
      provider,
      modelName,
      body,
    }: {
      provider: string
      modelName: string
      body: ModelPatchBody
    }) => patchModel(provider, modelName, body),
    onSuccess: invalidate,
  })
}

export function useCreateModel() {
  const invalidate = useInvalidateCatalog()
  return useMutation({
    mutationFn: (body: ModelCreateBody) => createModel(body),
    onSuccess: invalidate,
  })
}

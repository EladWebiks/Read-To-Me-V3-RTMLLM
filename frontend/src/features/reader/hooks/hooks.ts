import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getProgress, saveProgress } from '@/features/reader/api'
import type { ProgressUpsertInput } from '@/features/reader/types'

export function progressQueryKey(bookId: string) {
  return ['reader', 'progress', bookId] as const
}

export function useProgress(bookId: string) {
  return useQuery({
    queryKey: progressQueryKey(bookId),
    queryFn: () => getProgress(bookId),
    enabled: Boolean(bookId),
  })
}

export function useSaveProgress(bookId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: ProgressUpsertInput) => saveProgress(bookId, input),
    onSuccess: (data) => {
      queryClient.setQueryData(progressQueryKey(bookId), data)
    },
  })
}

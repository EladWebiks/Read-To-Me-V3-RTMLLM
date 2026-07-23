import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createChapter,
  deleteChapter,
  getChapter,
  listChapters,
  updateChapter,
} from '@/features/library/api'
import type { ChapterCreateInput } from '@/features/library/types'
import { booksQueryKey } from './bookHooks'

export function useChapters(bookId: string) {
  return useQuery({
    queryKey: [...booksQueryKey, bookId, 'chapters'],
    queryFn: () => listChapters(bookId),
    enabled: Boolean(bookId),
  })
}

export function useChapter(chapterId: string) {
  return useQuery({
    queryKey: ['chapters', chapterId],
    queryFn: () => getChapter(chapterId),
    enabled: Boolean(chapterId),
  })
}

export function useCreateChapter(bookId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: ChapterCreateInput) => createChapter(bookId, input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...booksQueryKey, bookId] })
    },
  })
}

export function useUpdateChapter(bookId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      chapterId,
      input,
    }: {
      chapterId: string
      input: Partial<ChapterCreateInput>
    }) => updateChapter(chapterId, input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...booksQueryKey, bookId] })
    },
  })
}

export function useDeleteChapter(bookId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (chapterId: string) => deleteChapter(chapterId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...booksQueryKey, bookId] })
    },
  })
}

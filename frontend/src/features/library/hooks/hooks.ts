import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createBook,
  createChapter,
  deleteBook,
  deleteChapter,
  getBook,
  getChapter,
  listBooks,
  listChapters,
  updateChapter,
  uploadCover,
} from '@/features/library/api'
import type { BookCreateInput, ChapterCreateInput } from '@/features/library/types'

export const booksQueryKey = ['library', 'books'] as const

export function useBooks() {
  return useQuery({ queryKey: booksQueryKey, queryFn: listBooks })
}

export function useBook(bookId: string) {
  return useQuery({
    queryKey: [...booksQueryKey, bookId],
    queryFn: () => getBook(bookId),
    enabled: Boolean(bookId),
  })
}

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

export function useCreateBook() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: BookCreateInput) => createBook(input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: booksQueryKey })
    },
  })
}

export function useDeleteBook() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (bookId: string) => deleteBook(bookId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: booksQueryKey })
    },
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

export function useUploadCover(bookId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => uploadCover(bookId, file),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: booksQueryKey })
    },
  })
}

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createBook,
  deleteBook,
  getBook,
  listBooks,
  updateBook,
} from '@/features/library/api'
import type { BookCreateInput } from '@/features/library/types'

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

export function useCreateBook() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: BookCreateInput) => createBook(input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: booksQueryKey })
    },
  })
}

export function useUpdateBook() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      bookId,
      input,
    }: {
      bookId: string
      input: Partial<BookCreateInput>
    }) => updateBook(bookId, input),
    onSuccess: (_book, { bookId }) => {
      void queryClient.invalidateQueries({ queryKey: booksQueryKey })
      void queryClient.invalidateQueries({ queryKey: [...booksQueryKey, bookId] })
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

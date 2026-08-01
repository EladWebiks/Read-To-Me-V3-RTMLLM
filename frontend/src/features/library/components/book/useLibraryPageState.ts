import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router'
import { useBooks } from '@/features/library/hooks'
import { filterAndSortBooks } from '@/features/library/logic/filterSortBooks'
import type { Book, LibrarySort } from '@/features/library/types'
import { useLibraryBookActions } from './useLibraryBookActions'

export function useLibraryPageState(pageSize: number) {
  const { data, isLoading, isError, refetch } = useBooks()
  const [searchParams] = useSearchParams()
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState<LibrarySort>('read')
  const [page, setPage] = useState(1)
  const [formBook, setFormBook] = useState<Book | null | undefined>(undefined)
  const actions = useLibraryBookActions(setFormBook)

  const books = filterAndSortBooks(data ?? [], search, sort)
  const size = Math.max(1, pageSize)
  const pageCount = Math.max(1, Math.ceil(books.length / size))
  const safePage = Math.min(page, pageCount)
  const pageBooks = useMemo(
    () => books.slice((safePage - 1) * size, safePage * size),
    [books, safePage, size],
  )
  const bookParam = searchParams.get('book')
  const selected = bookParam
    ? (books.find((book) => book.id === bookParam) ?? null)
    : null

  return {
    isLoading,
    isError,
    refetch,
    search,
    sort,
    page: safePage,
    pageCount,
    pageSize: size,
    books,
    pageBooks,
    formBook,
    formOpen: formBook !== undefined,
    selected,
    setSearch: (value: string) => {
      setSearch(value)
      setPage(1)
    },
    setSort: (value: LibrarySort) => {
      setSort(value)
      setPage(1)
    },
    setPage,
    ...actions,
  }
}

import { useNavigate, useSearchParams } from 'react-router'
import { useDeleteBook } from '@/features/library/hooks'
import type { Book } from '@/features/library/types'

type FormSetter = (book: Book | null | undefined) => void

export function useLibraryBookActions(setFormBook: FormSetter) {
  const deleteBook = useDeleteBook()
  const navigate = useNavigate()
  const [, setSearchParams] = useSearchParams()

  function setBookParam(bookId: string | null) {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        if (bookId) next.set('book', bookId)
        else next.delete('book')
        return next
      },
      { replace: true },
    )
  }

  return {
    isDeleting: deleteBook.isPending,
    openNew: () => setFormBook(null),
    openEdit: (book: Book) => setFormBook(book),
    closeForm: () => setFormBook(undefined),
    onOpen: (book: Book) => setBookParam(book.id),
    onCloseChapters: () => setBookParam(null),
    onRead: (book: Book) => {
      void navigate(`/read/${book.id}`)
    },
    onDelete: (id: string) => {
      deleteBook.mutate(id)
    },
  }
}

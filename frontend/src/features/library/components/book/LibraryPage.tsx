import { useState } from 'react'
import { useNavigate } from 'react-router'
import { BookCard } from './BookCard'
import { BookFormDialog } from './BookFormDialog'
import { ChaptersModal } from './ChaptersModal'
import { SearchSortBar } from './SearchSortBar'
import { useBooks, useDeleteBook } from '@/features/library/hooks'
import { filterAndSortBooks } from '@/features/library/logic/filterSortBooks'
import type { Book, LibrarySort } from '@/features/library/types'

export function LibraryPage() {
  const { data, isLoading, isError } = useBooks()
  const deleteBook = useDeleteBook()
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState<LibrarySort>('read')
  const [newOpen, setNewOpen] = useState(false)
  const [selected, setSelected] = useState<Book | null>(null)
  const books = filterAndSortBooks(data ?? [], search, sort)

  return (
    <section className="space-y-6 animate-fade-in-up">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Library</h1>
        <p className="text-muted-foreground">Your books and chapters.</p>
      </div>
      <SearchSortBar
        search={search}
        onSearch={setSearch}
        sort={sort}
        onSort={setSort}
        onNewBook={() => setNewOpen(true)}
      />
      <LibraryBody
        isLoading={isLoading}
        isError={isError}
        books={books}
        onOpen={setSelected}
        onRead={(book) => void navigate(`/read/${book.id}`)}
        onDelete={(id) => deleteBook.mutate(id)}
        isDeleting={deleteBook.isPending}
      />
      <BookFormDialog open={newOpen} onClose={() => setNewOpen(false)} />
      <ChaptersModal book={selected} onClose={() => setSelected(null)} />
    </section>
  )
}

function LibraryBody(props: {
  isLoading: boolean
  isError: boolean
  books: Book[]
  onOpen: (book: Book) => void
  onRead: (book: Book) => void
  onDelete: (bookId: string) => void
  isDeleting: boolean
}) {
  if (props.isLoading) return <p className="text-sm text-muted-foreground">Loading…</p>
  if (props.isError)
    return <p className="text-sm text-destructive">Could not load library.</p>
  if (props.books.length === 0) {
    return <p className="text-sm text-muted-foreground">No books yet.</p>
  }
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {props.books.map((book) => (
        <BookCard
          key={book.id}
          book={book}
          onOpen={props.onOpen}
          onRead={props.onRead}
          onDelete={props.onDelete}
          isDeleting={props.isDeleting}
        />
      ))}
    </div>
  )
}

import { useRef } from 'react'
import { BookFormDialog } from './BookFormDialog'
import { ChaptersModal } from './ChaptersModal'
import { DeleteBookModal } from './DeleteBookModal'
import { LibraryGrid } from './LibraryGrid'
import { LibraryPagination } from './LibraryPagination'
import { SearchSortBar } from './SearchSortBar'
import { useFitLibraryPageSize } from './useFitLibraryPageSize'
import { useLibraryPageState } from './useLibraryPageState'
import { useViewportLock } from '@/shared/hooks/useViewportLock'

export function LibraryPage() {
  const sectionRef = useRef<HTMLElement>(null)
  const gridSlotRef = useRef<HTMLDivElement>(null)
  useViewportLock(sectionRef)
  const pageSize = useFitLibraryPageSize(gridSlotRef)
  const state = useLibraryPageState(pageSize)

  return (
    <section
      ref={sectionRef}
      className="flex flex-col gap-4 overflow-hidden animate-fade-in-up"
    >
      <LibraryHeader loading={state.isLoading} count={state.books.length} />
      <SearchSortBar
        search={state.search}
        onSearch={state.setSearch}
        sort={state.sort}
        onSort={state.setSort}
        onNewBook={state.openNew}
      />
      <div ref={gridSlotRef} className="min-h-0 flex-1 overflow-hidden">
        <LibraryGrid
          isLoading={state.isLoading}
          isError={state.isError}
          empty={state.books.length === 0}
          books={state.pageBooks}
          onOpen={state.onOpen}
          onEdit={state.openEdit}
          onRead={state.onRead}
          onDelete={state.onDelete}
          isDeleting={state.isDeleting}
        />
      </div>
      <div className="shrink-0">
        <LibraryPagination
          page={state.page}
          pageCount={state.pageCount}
          total={state.books.length}
          pageSize={state.pageSize}
          onPage={state.setPage}
        />
      </div>
      <BookFormDialog
        open={state.formOpen}
        book={state.formBook}
        onClose={state.closeForm}
      />
      <DeleteBookModal
        book={state.pendingDelete}
        open={Boolean(state.pendingDelete)}
        busy={state.isDeleting}
        onClose={state.closeDelete}
        onConfirm={state.confirmDelete}
      />
      <ChaptersModal book={state.selected} onClose={state.onCloseChapters} />
    </section>
  )
}

function LibraryHeader({ loading, count }: { loading: boolean; count: number }) {
  return (
    <div className="shrink-0">
      <h1 className="text-3xl font-semibold tracking-tight">Library</h1>
      <p className="text-muted-foreground">
        {loading ? 'Loading your books…' : `${count} book${count === 1 ? '' : 's'}`}
      </p>
    </div>
  )
}

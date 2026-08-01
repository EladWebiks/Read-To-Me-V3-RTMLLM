import { motion } from 'motion/react'
import { QueryState, SkeletonCards } from '@/shared/ui'
import { BookCard } from './BookCard'
import type { Book } from '@/features/library/types'

type Props = {
  isLoading: boolean
  isError: boolean
  pageSize: number
  onRetry: () => void
  empty: boolean
  books: Book[]
  onOpen: (book: Book) => void
  onEdit: (book: Book) => void
  onRead: (book: Book) => void
  onDelete: (book: Book) => void
  isDeleting: boolean
}

const list = {
  hidden: {},
  show: { transition: { staggerChildren: 0.035 } },
}

const item = {
  hidden: { opacity: 0, y: 10 },
  show: {
    opacity: 1,
    y: 0,
    transition: { type: 'spring' as const, stiffness: 380, damping: 28 },
  },
}

export function LibraryGrid(props: Props) {
  return (
    <QueryState
      isPending={props.isLoading}
      isError={props.isError}
      loading={<SkeletonCards count={props.pageSize} />}
      errorLabel="Couldn't load library."
      label="Loading books…"
      onRetry={props.onRetry}
    >
      {props.empty ? (
        <p className="rounded-lg border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
          No books yet. Add one or scrape a novel to get started.
        </p>
      ) : (
        <motion.div
          className="grid auto-rows-40 grid-cols-1 gap-x-4 gap-y-4 pt-1 sm:grid-cols-2 xl:grid-cols-3"
          variants={list}
          initial="hidden"
          animate="show"
        >
          {props.books.map((book) => (
            <motion.div key={book.id} variants={item} className="h-full overflow-visible">
              <BookCard
                book={book}
                onOpen={props.onOpen}
                onEdit={props.onEdit}
                onRead={props.onRead}
                onDelete={props.onDelete}
                isDeleting={props.isDeleting}
              />
            </motion.div>
          ))}
        </motion.div>
      )}
    </QueryState>
  )
}

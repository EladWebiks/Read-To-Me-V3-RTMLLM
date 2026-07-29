import { motion } from 'motion/react'
import type { Book } from '@/features/library/types'
import { BookCover } from './BookCover'
import { BookCardActions } from './BookCardActions'

type Props = {
  book: Book
  onOpen: (book: Book) => void
  onEdit: (book: Book) => void
  onRead: (book: Book) => void
  onDelete: (book: Book) => void
  isDeleting: boolean
}

const hoverSpring = { type: 'spring' as const, stiffness: 380, damping: 26 }

export function BookCard({ book, onOpen, onEdit, onRead, onDelete, isDeleting }: Props) {
  const progress =
    book.last_read_chapter_number == null
      ? 'Not started'
      : `At ch. ${book.last_read_chapter_number}`

  return (
    <motion.article
      role="button"
      tabIndex={0}
      aria-label={`Open ${book.title}`}
      title={book.title}
      className="group relative flex h-40 cursor-pointer overflow-hidden rounded-xl border border-border bg-card outline-none will-change-transform focus-visible:ring-2 focus-visible:ring-ring"
      initial={false}
      whileHover={{
        y: -3,
        boxShadow: '0 12px 28px -12px rgb(0 0 0 / 0.28)',
        transition: hoverSpring,
      }}
      whileTap={{ scale: 0.988, transition: { duration: 0.1 } }}
      onClick={() => onOpen(book)}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onOpen(book)
        }
      }}
    >
      <div className="relative w-[4.75rem] shrink-0 self-stretch overflow-hidden bg-muted sm:w-[5.25rem]">
        <BookCover url={book.cover_url ?? null} title={book.title} />
      </div>
      <div className="flex min-w-0 flex-1 flex-col px-3 py-2.5 sm:px-3.5 sm:py-3">
        <h2 className="line-clamp-2 text-sm font-semibold leading-snug tracking-tight sm:text-[0.95rem]">
          {book.title}
        </h2>
        <p className="mt-0.5 truncate text-xs text-muted-foreground">
          {book.author || 'Unknown author'}
        </p>
        <p className="mt-auto truncate text-xs text-muted-foreground">
          {book.chapter_count} ch. · {progress}
        </p>
        <div className="mt-1 flex justify-end">
          <BookCardActions
            book={book}
            onEdit={onEdit}
            onRead={onRead}
            onDelete={onDelete}
            isDeleting={isDeleting}
          />
        </div>
      </div>
    </motion.article>
  )
}

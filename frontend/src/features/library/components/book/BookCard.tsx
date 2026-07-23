import { Card, CardContent, Button } from '@/shared/ui'
import type { Book } from '@/features/library/types'

type Props = {
  book: Book
  onOpen: (book: Book) => void
  onRead: (book: Book) => void
  onDelete: (bookId: string) => void
  isDeleting: boolean
}

export function BookCard({ book, onOpen, onRead, onDelete, isDeleting }: Props) {
  return (
    <Card className="flex overflow-hidden">
      <button type="button" className="contents text-left" onClick={() => onOpen(book)}>
        <CoverThumb url={book.cover_url ?? null} title={book.title} />
      </button>
      <CardContent className="flex flex-1 flex-col justify-between gap-2 p-4">
        <button type="button" className="text-left" onClick={() => onOpen(book)}>
          <p className="line-clamp-2 text-lg font-medium hover:underline">{book.title}</p>
          <p className="text-sm text-muted-foreground">
            {book.author || 'Unknown author'}
          </p>
        </button>
        <div className="flex items-end justify-between gap-2">
          <div className="text-sm text-muted-foreground">
            <p>
              {book.chapter_count} chapter{book.chapter_count === 1 ? '' : 's'}
            </p>
            <p>Current Ch: {book.last_read_chapter_number ?? '—'}</p>
          </div>
          <div className="flex gap-1">
            {book.chapter_count > 0 ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => onRead(book)}
              >
                Read
              </Button>
            ) : null}
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="text-destructive"
              disabled={isDeleting}
              onClick={() => onDelete(book.id)}
            >
              Delete
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function CoverThumb({ url, title }: { url: string | null; title: string }) {
  if (url) {
    return <img src={url} alt="" className="h-36 w-28 shrink-0 object-cover" />
  }
  return (
    <div className="flex h-36 w-28 shrink-0 items-center justify-center bg-muted px-2 text-center text-xs text-muted-foreground">
      {title.slice(0, 24) || 'No cover'}
    </div>
  )
}

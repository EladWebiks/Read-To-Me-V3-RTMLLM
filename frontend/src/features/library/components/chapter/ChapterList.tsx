import { Link } from 'react-router'
import { Button, Card } from '@/shared/ui'

type ChapterListProps = {
  isLoading: boolean
  isError: boolean
  bookId: string
  chapters: {
    id: string
    chapter_number: number
    title: string
    word_count: number
  }[]
  onDelete: (chapterId: string) => void
  isDeleting: boolean
}

export function ChapterList(props: ChapterListProps) {
  const { isLoading, isError, bookId, chapters, onDelete, isDeleting } = props
  if (isLoading) return <p className="text-sm text-muted-foreground">Loading…</p>
  if (isError) return <p className="text-sm text-destructive">Could not load chapters.</p>
  if (chapters.length === 0) {
    return <p className="text-sm text-muted-foreground">No chapters yet.</p>
  }
  return (
    <Card>
      <ul className="divide-y divide-border">
        {chapters.map((ch) => (
          <ChapterRow
            key={ch.id}
            bookId={bookId}
            chapter={ch}
            onDelete={onDelete}
            isDeleting={isDeleting}
          />
        ))}
      </ul>
    </Card>
  )
}

type RowProps = {
  bookId: string
  chapter: { id: string; chapter_number: number; title: string; word_count: number }
  onDelete: (id: string) => void
  isDeleting: boolean
}

function ChapterRow({ bookId, chapter, onDelete, isDeleting }: RowProps) {
  return (
    <li className="flex items-center justify-between gap-3 px-4 py-3">
      <div className="min-w-0">
        <span className="font-medium tabular-nums">#{chapter.chapter_number}</span>{' '}
        <span>{chapter.title || 'Untitled'}</span>{' '}
        <span className="text-sm text-muted-foreground">
          ({chapter.word_count} words)
        </span>
      </div>
      <div className="flex shrink-0 gap-1">
        <Button variant="ghost" size="sm" asChild>
          <Link to={`/read/${bookId}/${chapter.id}`}>Read</Link>
        </Button>
        <Button variant="ghost" size="sm" asChild>
          <Link to={`/library/books/${bookId}/chapters/${chapter.id}/edit`}>Edit</Link>
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="text-destructive"
          onClick={() => onDelete(chapter.id)}
          disabled={isDeleting}
        >
          Delete
        </Button>
      </div>
    </li>
  )
}

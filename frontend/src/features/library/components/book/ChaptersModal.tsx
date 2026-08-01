import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import {
  Button,
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  Input,
} from '@/shared/ui'
import { ChapterRows } from './ChapterRows'
import { useChapters, useDeleteChapter } from '@/features/library/hooks'
import type { Book, ChapterSummary } from '@/features/library/types'

type Props = { book: Book | null; onClose: () => void }

export function ChaptersModal({ book, onClose }: Props) {
  return (
    <Dialog open={Boolean(book)} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="flex max-h-[85vh] max-w-2xl flex-col">
        {book ? <ChaptersModalBody key={book.id} book={book} onClose={onClose} /> : null}
      </DialogContent>
    </Dialog>
  )
}

function ChaptersModalBody({ book, onClose }: { book: Book; onClose: () => void }) {
  const navigate = useNavigate()
  const [filter, setFilter] = useState('')
  const chaptersQuery = useChapters(book.id)
  const deleteChapter = useDeleteChapter(book.id)
  const filtered = useMemo(
    () => filterChapters(chaptersQuery.data ?? [], filter),
    [chaptersQuery.data, filter],
  )
  return (
    <>
      <DialogHeader>
        <DialogTitle className="truncate">{book.title} — Chapters</DialogTitle>
      </DialogHeader>
      <Input
        placeholder="Filter by title or number…"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      />
      <ChapterRows
        loading={chaptersQuery.isLoading}
        errored={chaptersQuery.isError}
        onRetry={() => void chaptersQuery.refetch()}
        chapters={filtered}
        lastRead={book.last_read_chapter_number ?? null}
        onPlay={(id) => {
          onClose()
          void navigate(`/read/${book.id}/${id}`)
        }}
        onEdit={(id) => {
          onClose()
          void navigate(`/library/books/${book.id}/chapters/${id}/edit`)
        }}
        onDelete={(id) => {
          if (window.confirm('Delete this chapter?')) void deleteChapter.mutateAsync(id)
        }}
      />
      <div className="mt-4 flex justify-end border-t border-border pt-4">
        <Button
          type="button"
          onClick={() => {
            onClose()
            void navigate(`/library/books/${book.id}/chapters/new`)
          }}
        >
          Add Chapter
        </Button>
      </div>
    </>
  )
}

function filterChapters(chapters: ChapterSummary[], filter: string) {
  const q = filter.trim().toLowerCase()
  if (!q) return chapters
  return chapters.filter(
    (ch) => ch.title.toLowerCase().includes(q) || String(ch.chapter_number).includes(q),
  )
}

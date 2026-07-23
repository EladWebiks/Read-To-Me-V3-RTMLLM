import { useState } from 'react'
import { useParams } from 'react-router'
import { AudioModal } from '@/features/downloads'
import { useProgress } from '@/features/reader/hooks'
import { AddChapterForm } from '@/features/library/components/chapter/AddChapterForm'
import { BookDetailHeader } from './BookDetailHeader'
import { ChapterList } from '@/features/library/components/chapter/ChapterList'
import { useBook, useChapters, useDeleteChapter } from '@/features/library/hooks'

export function BookDetailPage() {
  const { bookId = '' } = useParams()
  const bookQuery = useBook(bookId)
  const chaptersQuery = useChapters(bookId)
  const progressQuery = useProgress(bookId)
  const deleteChapter = useDeleteChapter(bookId)
  const [audioOpen, setAudioOpen] = useState(false)

  if (bookQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Loading book…</p>
  }
  if (bookQuery.isError || !bookQuery.data) {
    return <p className="text-sm text-destructive">Book not found.</p>
  }

  const book = bookQuery.data
  const chapters = chaptersQuery.data ?? []
  const currentChapter =
    chapters.find((ch) => ch.id === progressQuery.data?.chapter_id)?.chapter_number ??
    chapters[0]?.chapter_number ??
    0

  return (
    <section className="space-y-6">
      <BookDetailHeader
        book={book}
        bookId={bookId}
        hasChapters={chapters.length > 0}
        hasProgress={Boolean(progressQuery.data)}
        onAudio={() => setAudioOpen(true)}
      />
      <AddChapterForm bookId={bookId} />
      <ChapterList
        isLoading={chaptersQuery.isLoading}
        isError={chaptersQuery.isError}
        chapters={chapters}
        bookId={bookId}
        onDelete={(id) => deleteChapter.mutate(id)}
        isDeleting={deleteChapter.isPending}
      />
      <AudioModal
        open={audioOpen}
        onClose={() => setAudioOpen(false)}
        bookId={bookId}
        bookTitle={book.title}
        chapters={chapters}
        currentChapterNumber={currentChapter}
      />
    </section>
  )
}

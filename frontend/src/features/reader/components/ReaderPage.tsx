import { useLocation, useParams } from 'react-router'
import { useBook, useChapter, useChapters } from '@/features/library/hooks'
import type { ChapterSummary } from '@/features/library/types'
import { useProgress } from '@/features/reader/hooks'
import { ReaderSession } from './ReaderSession'
import type { ReaderCursor } from '@/features/reader/types'

type LocationState = { autoPlay?: boolean }

export function ReaderPage() {
  const { bookId = '', chapterId = '' } = useParams()
  const location = useLocation()
  const autoPlay = Boolean((location.state as LocationState | null)?.autoPlay)
  const bookQuery = useBook(bookId)
  const chapterQuery = useChapter(chapterId)
  const chaptersQuery = useChapters(bookId)
  const progressQuery = useProgress(bookId)

  if (bookQuery.isLoading || chapterQuery.isLoading || chaptersQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Loading chapter…</p>
  }
  if (
    bookQuery.isError ||
    !bookQuery.data ||
    chapterQuery.isError ||
    !chapterQuery.data
  ) {
    return <p className="text-sm text-destructive">Chapter not found.</p>
  }

  const book = bookQuery.data
  const chapter = chapterQuery.data
  const chapters = chaptersQuery.data ?? []
  const { prevId, nextId } = neighbors(chapters, chapterId)

  return (
    <section className="flex min-h-0 flex-1 flex-col">
      <ReaderSession
        key={chapterId}
        bookId={bookId}
        bookTitle={book.title}
        chapterId={chapterId}
        chapterTitle={chapter.title}
        chapterNumber={chapter.chapter_number}
        content={chapter.content}
        chapters={chapters}
        initialCursor={cursorFromProgress(progressQuery.data, chapterId)}
        prevChapterId={prevId}
        nextChapterId={nextId}
        autoPlay={autoPlay}
      />
    </section>
  )
}

function cursorFromProgress(
  progress:
    | { chapter_id: string; paragraph_index: number; word_index: number }
    | null
    | undefined,
  chapterId: string,
): ReaderCursor {
  if (progress?.chapter_id !== chapterId) {
    return { paragraphIndex: 0, wordIndex: 0 }
  }
  return {
    paragraphIndex: progress.paragraph_index,
    wordIndex: progress.word_index,
  }
}

function neighbors(chapters: ChapterSummary[], chapterId: string) {
  const index = chapters.findIndex((item) => item.id === chapterId)
  return {
    prevId: index > 0 ? (chapters[index - 1]?.id ?? null) : null,
    nextId:
      index >= 0 && index < chapters.length - 1
        ? (chapters[index + 1]?.id ?? null)
        : null,
  }
}

import { Link, Navigate, useParams } from 'react-router'
import { useChapters } from '@/features/library/hooks'
import { libraryBookHref } from '@/features/library/logic/libraryPaths'
import { useProgress } from '@/features/reader/hooks'

export function ResumeReadingPage() {
  const { bookId = '' } = useParams()
  const progressQuery = useProgress(bookId)
  const chaptersQuery = useChapters(bookId)

  if (progressQuery.isLoading || chaptersQuery.isLoading) {
    return <p className="text-sm text-stone-500">Opening book…</p>
  }
  if (chaptersQuery.isError) {
    return <p className="text-sm text-red-700">Could not load chapters.</p>
  }

  const chapters = chaptersQuery.data ?? []
  const targetId = progressQuery.data?.chapter_id ?? chapters[0]?.id
  if (!targetId) {
    return (
      <p className="text-sm text-stone-500">
        No chapters to read.{' '}
        <Link to={libraryBookHref(bookId)} className="underline">
          Add one
        </Link>
        .
      </p>
    )
  }
  return <Navigate to={`/read/${bookId}/${targetId}`} replace />
}

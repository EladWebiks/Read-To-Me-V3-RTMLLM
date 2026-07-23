import { Link, Navigate } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { getContinueReading } from '@/features/reader/api'
import { useBooks } from '@/features/library/hooks'

export function ReaderHubPage() {
  const continueQuery = useQuery({
    queryKey: ['reader', 'continue'],
    queryFn: getContinueReading,
  })
  const booksQuery = useBooks()

  if (continueQuery.isLoading || booksQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Opening reader…</p>
  }

  const progress = continueQuery.data
  if (progress?.book_id && progress.chapter_id) {
    return <Navigate to={`/read/${progress.book_id}/${progress.chapter_id}`} replace />
  }

  const firstReadable = (booksQuery.data ?? []).find((book) => book.chapter_count > 0)
  if (firstReadable) {
    return <Navigate to={`/read/${firstReadable.id}`} replace />
  }

  return (
    <p className="text-sm text-muted-foreground">
      No books to read yet.{' '}
      <Link
        to="/library"
        className="font-medium text-foreground underline-offset-2 hover:underline"
      >
        Open library
      </Link>
      .
    </p>
  )
}

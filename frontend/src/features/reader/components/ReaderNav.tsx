import { Link } from 'react-router'
import { ChevronLeft } from 'lucide-react'
import { libraryBookHref } from '@/features/library/logic/libraryPaths'

type ReaderNavProps = {
  bookId: string
  bookTitle: string
  chapterTitle: string
  chapterNumber: number
}

export function ReaderNav(props: ReaderNavProps) {
  return (
    <header className="space-y-2 border-b border-border/80 pb-3">
      <Link
        to={libraryBookHref(props.bookId)}
        className="inline-flex items-center gap-1 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
      >
        <ChevronLeft className="h-4 w-4" />
        {props.bookTitle}
      </Link>
      <div className="min-w-0">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Chapter {props.chapterNumber}
        </p>
        <h1 className="truncate text-2xl font-semibold tracking-tight">
          {props.chapterTitle || 'Untitled'}
        </h1>
      </div>
    </header>
  )
}

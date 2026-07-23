import { Link } from 'react-router'
import { ChevronLeft, Upload } from 'lucide-react'
import { Button } from '@/shared/ui'
import type { Book } from '@/features/library/types'
import { useUploadCover } from '@/features/library/hooks'

type Props = {
  book: Book
  bookId: string
  hasChapters: boolean
  hasProgress: boolean
  onAudio: () => void
}

export function BookDetailHeader(props: Props) {
  const { book, bookId, hasChapters, hasProgress, onAudio } = props
  const upload = useUploadCover(bookId)
  return (
    <div className="space-y-4">
      <Link
        to="/library"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="h-4 w-4" />
        Back to library
      </Link>
      <div className="flex gap-5">
        <BookCover
          url={book.cover_url ?? null}
          uploading={upload.isPending}
          onFile={(f) => upload.mutate(f)}
        />
        <div className="min-w-0">
          <h1 className="text-3xl font-semibold tracking-tight">{book.title}</h1>
          <p className="text-muted-foreground">{book.author || 'Unknown author'}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {hasChapters && (
              <Button variant="outline" size="sm" asChild>
                <Link to={`/read/${bookId}`}>
                  {hasProgress ? 'Continue reading' : 'Start reading'}
                </Link>
              </Button>
            )}
            {hasChapters && (
              <Button variant="outline" size="sm" onClick={onAudio}>
                Download audio
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

type CoverProps = { url: string | null; uploading: boolean; onFile: (f: File) => void }

function BookCover({ url, uploading, onFile }: CoverProps) {
  return (
    <div className="group relative h-36 w-24 shrink-0 overflow-hidden rounded-md bg-muted">
      {url ? (
        <img src={url} alt="" className="h-full w-full object-cover" />
      ) : (
        <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
          No cover
        </div>
      )}
      <label className="absolute inset-0 flex cursor-pointer items-end justify-center bg-black/0 pb-2 opacity-0 transition-opacity group-hover:bg-black/30 group-hover:opacity-100">
        <Upload className="h-4 w-4 text-white" />
        <input
          type="file"
          accept="image/*"
          className="sr-only"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) onFile(file)
          }}
        />
      </label>
      {uploading && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/40 text-xs text-white">
          Uploading…
        </div>
      )}
    </div>
  )
}

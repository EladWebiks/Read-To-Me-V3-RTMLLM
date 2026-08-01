import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/shared/ui'
import { useCleanDownloads, useDownloadJobs } from '@/features/downloads/hooks'
import { ReadyFilesList } from './ReadyFilesList'
import { ReadyFilesToolbar } from './ReadyFilesToolbar'
import type { DownloadJob } from '@/features/downloads/types'

type Props = {
  open: boolean
  bookId: string
  bookTitle: string
  canListen: boolean
  onClose: () => void
  onListen: (job: DownloadJob) => void
}

export function ReadyFilesModal(props: Props) {
  const { open, bookId, bookTitle, canListen, onClose, onListen } = props
  const jobsQuery = useDownloadJobs(bookId, open)
  const clean = useCleanDownloads(bookId)
  const jobs = jobsQuery.data ?? []
  if (!open) return null
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Ready files</DialogTitle>
          <p className="text-sm text-muted-foreground">
            Book: <span className="font-medium text-foreground">{bookTitle}</span>
          </p>
          <p className="text-xs text-muted-foreground">
            Generated audio is kept for a few days, then removed.
          </p>
        </DialogHeader>
        <ReadyFilesToolbar
          cleaning={clean.isPending}
          canClean={jobs.length > 0}
          onRefresh={() => void jobsQuery.refetch()}
          onClean={() => {
            if (window.confirm('Delete all ready files for this book?')) {
              void clean.mutateAsync()
            }
          }}
          onClose={onClose}
        />
        <ReadyFilesList
          bookId={bookId}
          jobs={jobs}
          loading={jobsQuery.isLoading}
          errored={jobsQuery.isError}
          canListen={canListen}
          onListen={onListen}
          onRetry={() => void jobsQuery.refetch()}
        />
      </DialogContent>
    </Dialog>
  )
}

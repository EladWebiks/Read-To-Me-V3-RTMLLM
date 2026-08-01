import type { DownloadJob } from '@/features/downloads/types'
import { QueryState, SkeletonRows } from '@/shared/ui'
import { ReadyJobRow } from './ReadyJobRow'

type Props = {
  bookId: string
  jobs: DownloadJob[]
  loading: boolean
  errored: boolean
  canListen: boolean
  onListen: (job: DownloadJob) => void
  onRetry: () => void
}

export function ReadyFilesList({
  bookId,
  jobs,
  loading,
  errored,
  canListen,
  onListen,
  onRetry,
}: Props) {
  return (
    <div className="mt-4 space-y-2">
      <QueryState
        isPending={loading}
        isError={errored}
        isEmpty={jobs.length === 0}
        loading={<SkeletonRows count={3} height="h-10" />}
        errorLabel="Couldn't load jobs."
        emptyLabel={
          <p className="text-sm text-muted-foreground">No jobs yet for this book.</p>
        }
        label="Loading jobs…"
        onRetry={onRetry}
      >
        <ul className="space-y-2">
          {jobs.map((job) => (
            <ReadyJobRow
              key={job.id}
              bookId={bookId}
              job={job}
              canListen={canListen}
              onListen={() => onListen(job)}
            />
          ))}
        </ul>
      </QueryState>
    </div>
  )
}

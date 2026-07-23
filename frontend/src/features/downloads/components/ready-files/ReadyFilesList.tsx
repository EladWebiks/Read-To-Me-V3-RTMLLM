import type { DownloadJob } from '@/features/downloads/types'
import { ReadyJobRow } from './ReadyJobRow'

type Props = {
  bookId: string
  jobs: DownloadJob[]
  loading: boolean
  errored: boolean
  canListen: boolean
  onListen: (job: DownloadJob) => void
}

export function ReadyFilesList({
  bookId,
  jobs,
  loading,
  errored,
  canListen,
  onListen,
}: Props) {
  return (
    <div className="mt-4 space-y-2">
      {loading ? <p className="text-sm text-muted-foreground">Loading jobs…</p> : null}
      {errored ? <p className="text-sm text-destructive">Could not load jobs.</p> : null}
      {!loading && jobs.length === 0 ? (
        <p className="text-sm text-muted-foreground">No jobs yet for this book.</p>
      ) : null}
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
    </div>
  )
}

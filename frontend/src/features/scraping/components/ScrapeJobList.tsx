import { Link } from 'react-router'
import { Button } from '@/shared/ui'
import { libraryBookHref } from '@/features/library/logic/libraryPaths'
import { useCancelScrapeJob, useScrapeJobs } from '../hooks'
import type { ScrapeJob } from '../types'

export function ScrapeJobList() {
  const jobs = useScrapeJobs()
  const cancel = useCancelScrapeJob()
  const items = jobs.data ?? []
  return (
    <div className="space-y-3">
      <h2 className="text-sm font-medium text-muted-foreground">Recent jobs</h2>
      {jobs.isLoading ? <p className="text-sm text-muted-foreground">Loading…</p> : null}
      {items.length === 0 && !jobs.isLoading ? (
        <p className="text-sm text-muted-foreground">No scrape jobs yet.</p>
      ) : null}
      <ul className="space-y-2">
        {items.map((job) => (
          <JobRow
            key={job.id}
            job={job}
            onCancel={() => void cancel.mutateAsync(job.id)}
          />
        ))}
      </ul>
    </div>
  )
}

function JobRow({ job, onCancel }: { job: ScrapeJob; onCancel: () => void }) {
  const busy = job.status === 'pending' || job.status === 'running'
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border bg-card px-3 py-2 text-sm">
      <div className="min-w-0">
        <p className="font-medium">
          {job.status} · {job.chapters_done} chapters
        </p>
        <p className="truncate text-xs text-muted-foreground">
          {job.message || job.start_url}
        </p>
        {job.error ? <p className="text-xs text-destructive">{job.error}</p> : null}
      </div>
      <div className="flex gap-2">
        {job.book_id ? (
          <Button asChild variant="outline" size="sm">
            <Link to={libraryBookHref(job.book_id)}>Open book</Link>
          </Button>
        ) : null}
        {busy ? (
          <Button variant="destructive" size="sm" onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
      </div>
    </li>
  )
}

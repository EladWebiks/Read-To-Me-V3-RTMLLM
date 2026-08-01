import { useState } from 'react'
import { DownloadJobsTable } from './DownloadJobsTable'
import { ScrapingJobsTable } from './ScrapingJobsTable'

const TAB = 'rounded-md px-2.5 py-1 text-sm'

export function JobsPage() {
  const [kind, setKind] = useState<'scraping' | 'downloads'>('scraping')
  const [status, setStatus] = useState('')
  return (
    <section>
      <h1 className="mb-1 text-lg font-semibold">Jobs monitor</h1>
      <p className="mb-3 text-sm text-muted-foreground">
        Read-only view across all users. Cancel/retry live in the owning features.
      </p>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          className={`${TAB} ${kind === 'scraping' ? 'bg-muted font-medium' : 'text-muted-foreground'}`}
          onClick={() => setKind('scraping')}
        >
          Scraping
        </button>
        <button
          type="button"
          className={`${TAB} ${kind === 'downloads' ? 'bg-muted font-medium' : 'text-muted-foreground'}`}
          onClick={() => setKind('downloads')}
        >
          Downloads
        </button>
        <input
          className="ml-auto rounded border border-border bg-background px-2 py-1 text-sm"
          placeholder="Filter by status"
          aria-label="Filter by status"
          value={status}
          onChange={(event) => setStatus(event.target.value)}
        />
      </div>
      {kind === 'scraping' ? (
        <ScrapingJobsTable status={status} />
      ) : (
        <DownloadJobsTable status={status} />
      )}
    </section>
  )
}

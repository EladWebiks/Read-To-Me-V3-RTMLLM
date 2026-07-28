import { useState } from 'react'
import { Link } from 'react-router'
import { Button } from '@/shared/ui'
import {
  scrapeJobIsBusy,
  scrapeJobIsTerminal,
  scrapeJobSubtitle,
} from '../logic/scrapeJobCopy'
import type { ScrapeJob } from '../types'
import { ScrapeJobErrorModal } from './ScrapeJobErrorModal'

type Props = {
  job: ScrapeJob
  onCancel: () => void
  onRemove: () => void
  onOpenHref: string | null
}

export function ScrapeJobRow({ job, onCancel, onRemove, onOpenHref }: Props) {
  const [errorOpen, setErrorOpen] = useState(false)
  const busy = scrapeJobIsBusy(job.status)
  const terminal = scrapeJobIsTerminal(job.status)
  const hasError = Boolean(job.error) || job.status === 'failed'
  const detail = job.error || job.message || 'An error occurred'
  const title = job.book_title?.trim() || 'Untitled'
  const subtitle = scrapeJobSubtitle(job)
  const meta = `${job.status} · ${job.chapters_done} chapters · ${subtitle}`

  return (
    <li className="flex h-[3.75rem] items-center gap-3 overflow-hidden rounded-md border border-border bg-card px-3 text-sm">
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium">{title}</p>
        <p
          className={
            hasError
              ? 'truncate text-xs text-destructive'
              : 'truncate text-xs text-muted-foreground'
          }
        >
          {meta}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {hasError ? (
          <Button variant="outline" size="sm" onClick={() => setErrorOpen(true)}>
            Details
          </Button>
        ) : null}
        {onOpenHref ? (
          <Button asChild variant="outline" size="sm">
            <Link to={onOpenHref}>Open book</Link>
          </Button>
        ) : null}
        {busy ? (
          <Button variant="destructive" size="sm" onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
        {terminal ? (
          <Button variant="ghost" size="sm" onClick={onRemove}>
            Remove
          </Button>
        ) : null}
      </div>
      {hasError ? (
        <ScrapeJobErrorModal
          open={errorOpen}
          onClose={() => setErrorOpen(false)}
          detail={detail}
        />
      ) : null}
    </li>
  )
}

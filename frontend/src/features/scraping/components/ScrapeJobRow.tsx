import { Link } from 'react-router'
import { Button } from '@/shared/ui'
import type { ScrapeJob } from '../types'

type Props = {
  job: ScrapeJob
  onCancel: () => void
  onOpenHref: string | null
}

export function ScrapeJobRow({ job, onCancel, onOpenHref }: Props) {
  const busy = job.status === 'pending' || job.status === 'running'
  return (
    <li className="flex h-[3.75rem] flex-wrap items-center justify-between gap-2 overflow-hidden rounded-md border border-border bg-card px-3 py-2 text-sm">
      <div className="min-w-0">
        <p className="truncate font-medium">
          {job.status} · {job.chapters_done} chapters
        </p>
        <p
          className={
            job.error
              ? 'truncate text-xs text-destructive'
              : 'truncate text-xs text-muted-foreground'
          }
        >
          {job.error || job.message || job.start_url}
        </p>
      </div>
      <div className="flex gap-2">
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
      </div>
    </li>
  )
}

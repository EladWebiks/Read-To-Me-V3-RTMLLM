import { formatJobExpiry } from '@/features/downloads/logic/formatJobExpiry'
import { ReadyJobActions } from './ReadyJobActions'
import type { DownloadJob } from '@/features/downloads/types'

type Props = {
  bookId: string
  job: DownloadJob
  canListen: boolean
  onListen: () => void
}

export function ReadyJobRow({ bookId, job, canListen, onListen }: Props) {
  const range =
    job.chapter_from === job.chapter_to
      ? `Ch ${job.chapter_from}`
      : `Ch ${job.chapter_from}–${job.chapter_to}`
  const expiry = formatJobExpiry(job.expires_at)
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border px-3 py-2 text-sm">
      <div className="min-w-0">
        <p className="font-medium text-foreground">
          {range} · {job.provider} · {job.voice}
        </p>
        <p className="text-xs text-muted-foreground">
          {job.status} · {job.ready_count}/{job.total_count}
          {expiry ? ` · ${expiry}` : ''}
          {job.error ? ` · ${job.error}` : ''}
        </p>
      </div>
      <ReadyJobActions
        bookId={bookId}
        job={job}
        canListen={canListen}
        onListen={onListen}
      />
    </li>
  )
}

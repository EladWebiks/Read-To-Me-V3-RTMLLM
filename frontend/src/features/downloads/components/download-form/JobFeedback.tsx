import type { DownloadJob } from '@/features/downloads/types'

export function JobFeedback({
  job,
  error,
  mode,
}: {
  job: DownloadJob | undefined
  error: string | null
  mode: 'download' | 'listen' | null
}) {
  if (error) {
    return <p className="mt-3 text-sm text-destructive">{error}</p>
  }
  if (!job || !mode) {
    return null
  }
  if (job.status === 'complete' && mode === 'download') {
    return (
      <p className="mt-3 text-sm text-emerald-700 dark:text-emerald-400">
        Audio ready — download should start automatically.
      </p>
    )
  }
  if (job.status === 'failed') {
    return <p className="mt-3 text-sm text-destructive">{job.error ?? 'Job failed'}</p>
  }
  return (
    <p className="mt-3 text-sm text-muted-foreground">
      {job.status} ({job.ready_count}/{job.total_count})
    </p>
  )
}

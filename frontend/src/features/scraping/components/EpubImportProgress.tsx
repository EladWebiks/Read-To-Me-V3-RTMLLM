import { X } from 'lucide-react'
import { Button } from '@/shared/ui'
import type { ImportJob } from '../types/importTypes'

type Props = {
  job: ImportJob
  elapsedMs: number
  cancelling: boolean
  onCancel: () => void
}

export function EpubImportProgress({ job, elapsedMs, cancelling, onCancel }: Props) {
  const parsing = job.total_chapters == null
  const progress = progressPercent(job, parsing)
  const counter = parsing
    ? `${job.files_parsed} / ${job.files_total} files`
    : `${job.chapters_imported} / ${job.total_chapters} chapters`

  return (
    <div className="space-y-3 rounded-md border border-border bg-muted/30 p-4">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-sm font-medium">
          {parsing ? 'Parsing EPUB files' : 'Importing chapters'}
        </span>
        <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
          {formatElapsed(elapsedMs)}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-all"
          style={{ width: `${progress ?? 8}%` }}
        />
      </div>
      <div className="flex items-start justify-between gap-3 text-sm">
        <p className="min-w-0 flex-1 truncate text-muted-foreground" title={job.message}>
          {job.current_file || job.message}
        </p>
        <span className="shrink-0 tabular-nums text-foreground">{counter}</span>
      </div>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="-ml-2 gap-1.5 text-amber-600"
        onClick={onCancel}
        disabled={cancelling}
      >
        <X className="size-3.5" />
        {cancelling ? 'Cancelling…' : 'Cancel'}
      </Button>
    </div>
  )
}

function progressPercent(job: ImportJob, parsing: boolean): number | null {
  if (parsing) {
    return job.files_total > 0
      ? Math.round((job.files_parsed / job.files_total) * 100)
      : null
  }
  if (!job.total_chapters || job.total_chapters <= 0) return null
  return Math.min(100, Math.round((job.chapters_imported / job.total_chapters) * 100))
}

function formatElapsed(ms: number): string {
  const sec = Math.floor(ms / 1000)
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

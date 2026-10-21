type ProgressProps = {
  status: string
  done: number
  total: number | null
  message?: string
}

export function ScrapeProgress({ status, done, total, message }: ProgressProps) {
  const known = total != null && total > 0
  const percent = known ? Math.min(100, Math.round((done / total) * 100)) : null
  const label = progressLabel(status, done, total, message)
  return (
    <div className="mt-2 space-y-1">
      <p className="text-xs text-muted-foreground">{label}</p>
      {status === 'cancelled' || status === 'failed' ? null : (
        <div className="h-1.5 overflow-hidden rounded-full bg-muted">
          <div
            className={
              percent == null
                ? 'h-full w-1/3 animate-pulse bg-primary/70'
                : 'h-full bg-primary transition-all'
            }
            style={percent == null ? undefined : { width: `${percent}%` }}
          />
        </div>
      )}
    </div>
  )
}

function progressLabel(
  status: string,
  done: number,
  total: number | null,
  message?: string,
): string {
  if (status === 'failed') return message?.trim() || 'Scrape failed'
  if (status === 'cancelled') return message?.trim() || 'Cancelled'
  if (status === 'complete') {
    return total != null
      ? `Finished — ${done}/${total} chapters`
      : `Finished — ${done} chapters`
  }
  if (total != null && total > 0) return `Scraping… ${done}/${total}`
  if (done > 0) return `Scraping… ${done} chapters`
  return status === 'pending' ? 'Queued…' : 'Scraping…'
}

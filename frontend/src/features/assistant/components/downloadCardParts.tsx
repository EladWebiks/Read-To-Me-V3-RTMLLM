import { Button } from '@/shared/ui'

type ProgressProps = {
  status?: string
  ready: number
  total: number
}

export function DownloadProgress({ status, ready, total }: ProgressProps) {
  const safeTotal = Math.max(total, 1)
  const percent = Math.min(100, Math.round((ready / safeTotal) * 100))
  const label =
    status === 'failed'
      ? 'Generation failed'
      : status === 'cancelled'
        ? 'Cancelled'
        : status === 'complete'
          ? 'Ready — download started'
          : `Generating audio… ${ready}/${total}`
  return (
    <div className="mt-2 space-y-1">
      <p className="text-xs text-muted-foreground">{label}</p>
      {status !== 'cancelled' ? (
        <div className="h-1.5 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full bg-primary transition-all"
            style={{ width: `${percent}%` }}
          />
        </div>
      ) : null}
    </div>
  )
}

type ActionsProps = {
  complete: boolean
  inFlight: boolean
  downloading: boolean
  cancelling: boolean
  onDownload: () => void
  onCancel: () => void
}

export function DownloadCardActions(props: ActionsProps) {
  if (!props.complete && !props.inFlight) return null
  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {props.complete ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={props.downloading}
          onClick={props.onDownload}
        >
          {props.downloading ? 'Downloading…' : 'Download MP3'}
        </Button>
      ) : null}
      {props.inFlight ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={props.cancelling}
          onClick={props.onCancel}
        >
          {props.cancelling ? 'Cancelling…' : 'Cancel'}
        </Button>
      ) : null}
    </div>
  )
}

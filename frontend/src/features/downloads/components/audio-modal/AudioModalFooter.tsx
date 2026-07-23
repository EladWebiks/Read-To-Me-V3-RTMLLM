import { Button } from '@/shared/ui'

type Props = {
  busy: boolean
  creating: boolean
  mode: 'download' | 'listen' | null
  hasChapters: boolean
  showListen: boolean
  jobStatus: string | undefined
  onClose: () => void
  onListen: () => void
  onDownload: () => void
  onOpenReadyFiles: () => void
}

export function AudioModalFooter(props: Props) {
  const generating =
    props.mode === 'download' &&
    props.jobStatus !== 'complete' &&
    (props.creating || Boolean(props.jobStatus))
  return (
    <div className="mt-5 flex flex-wrap items-center justify-between gap-2">
      <Button variant="outline" size="sm" onClick={props.onOpenReadyFiles}>
        Ready files…
      </Button>
      <div className="flex flex-wrap justify-end gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={props.creating}
          onClick={props.onClose}
        >
          Close
        </Button>
        {props.showListen && (
          <Button
            variant="outline"
            size="sm"
            disabled={props.busy || !props.hasChapters}
            onClick={props.onListen}
          >
            {props.mode === 'listen' && props.creating ? 'Starting…' : 'Listen offline'}
          </Button>
        )}
        <Button
          size="sm"
          disabled={props.busy || !props.hasChapters}
          onClick={props.onDownload}
        >
          {generating ? 'Generating…' : 'Download MP3'}
        </Button>
      </div>
    </div>
  )
}

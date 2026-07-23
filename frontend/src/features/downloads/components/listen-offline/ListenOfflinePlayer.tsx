import type { ChapterSummary } from '@/features/library/types'
import type { AudioFormState } from '@/features/downloads/logic/audioModalUtils'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/shared/ui'
import { ListenOfflineControls } from './ListenOfflineControls'
import { useAutoPlayWhenReady } from '@/features/downloads/hooks/useAutoPlayWhenReady'
import { useListenOffline } from '@/features/downloads/hooks/useListenOffline'
import type { DownloadJob } from '@/features/downloads/types'

type ListenState = { job: DownloadJob; form: AudioFormState }

type Props = {
  open: boolean
  config: ListenState | null
  bookTitle: string
  chapters: ChapterSummary[]
  onClose: () => void
}

export function ListenOfflinePlayer(props: Props) {
  if (!props.open || !props.config) return null
  return <ListenOfflineOpen key={props.config.job.id} {...props} config={props.config} />
}

function ListenOfflineOpen({
  config,
  bookTitle,
  chapters,
  onClose,
}: Props & { config: ListenState }) {
  const listen = useListenOffline(
    true,
    { job: config.job, chapterFrom: config.form.from, chapterTo: config.form.to },
    chapters,
  )
  useAutoPlayWhenReady(listen.chapterReady, listen.index, listen.status, listen.resume)
  const failed = listen.job?.status === 'failed'
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Listen offline</DialogTitle>
          <p className="text-sm text-muted-foreground">{bookTitle}</p>
        </DialogHeader>
        <ListenOfflineControls
          jobId={config.job.id}
          jobStatus={listen.job?.status}
          readyCount={listen.readyCount}
          totalCount={listen.job?.total_count ?? config.job.total_count}
          current={listen.current}
          chapterReady={listen.chapterReady}
          status={listen.status}
          error={listen.error ?? (failed ? (listen.job?.error ?? 'Job failed') : null)}
          canPrev={listen.index > 0}
          canNext={listen.index < listen.range.length - 1}
          currentTime={listen.currentTime}
          duration={listen.duration}
          onClose={() => {
            listen.stop()
            onClose()
          }}
          onPrev={listen.prev}
          onNext={listen.next}
          onPause={listen.pause}
          onResume={listen.resume}
          onSeekBack={listen.seekBack}
          onSeekForward={listen.seekForward}
          onSeekTo={listen.seekTo}
        />
      </DialogContent>
    </Dialog>
  )
}

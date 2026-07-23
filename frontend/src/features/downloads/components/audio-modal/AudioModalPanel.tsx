import type { ChapterSummary } from '@/features/library/types'
import type { ServerVoice } from '@/features/reader/api/audioApi'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/shared/ui'
import { AudioModalFields } from './AudioModalFields'
import { AudioModalFooter } from './AudioModalFooter'
import type { AudioFormState } from '@/features/downloads/logic/audioModalUtils'
import { JobFeedback } from '@/features/downloads/components/download-form/JobFeedback'
import type { useAudioJob } from '@/features/downloads/hooks/useAudioJob'

type JobApi = ReturnType<typeof useAudioJob>

type Props = {
  bookTitle: string
  chapters: ChapterSummary[]
  form: AudioFormState
  voices: ServerVoice[]
  job: JobApi
  showListen: boolean
  onClose: () => void
  onChange: (patch: Partial<AudioFormState>) => void
  onOpenReadyFiles: () => void
}

export function AudioModalPanel(props: Props) {
  return (
    <Dialog open onOpenChange={(open) => !open && props.onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Download audio</DialogTitle>
          <p className="text-sm text-muted-foreground">
            Book: <span className="font-medium text-foreground">{props.bookTitle}</span>
          </p>
          <p className="text-sm text-muted-foreground">
            {props.job.count} chapter{props.job.count === 1 ? '' : 's'} selected
          </p>
        </DialogHeader>
        <AudioModalFields
          chapters={props.chapters}
          form={props.form}
          voices={props.voices}
          busy={props.job.busy}
          onChange={props.onChange}
        />
        <JobFeedback job={props.job.job} error={props.job.error} mode={props.job.mode} />
        <AudioModalFooter
          busy={props.job.busy}
          creating={props.job.creating}
          mode={props.job.mode}
          hasChapters={props.chapters.length > 0}
          showListen={props.showListen}
          jobStatus={props.job.job?.status}
          onClose={props.onClose}
          onListen={() => props.job.startListen()}
          onDownload={() => props.job.startDownload()}
          onOpenReadyFiles={props.onOpenReadyFiles}
        />
      </DialogContent>
    </Dialog>
  )
}

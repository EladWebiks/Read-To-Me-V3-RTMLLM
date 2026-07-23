import { useState } from 'react'
import type { ChapterSummary } from '@/features/library/types'
import type { ServerVoice } from '@/features/reader/api/audioApi'
import { AudioModalPanel } from './AudioModalPanel'
import type { AudioFormState } from '@/features/downloads/logic/audioModalUtils'
import { ReadyFilesModal } from '@/features/downloads/components/ready-files/ReadyFilesModal'
import type { DownloadJob } from '@/features/downloads/types'
import type { useAudioJob } from '@/features/downloads/hooks/useAudioJob'

type JobApi = ReturnType<typeof useAudioJob>

type Props = {
  bookId: string
  bookTitle: string
  chapters: ChapterSummary[]
  form: AudioFormState
  voices: ServerVoice[]
  job: JobApi
  showListen: boolean
  onClose: () => void
  onChange: (patch: Partial<AudioFormState>) => void
  onResumeListen: (job: DownloadJob) => void
}

export function AudioModalBody(props: Props) {
  const [readyOpen, setReadyOpen] = useState(false)
  return (
    <>
      <AudioModalPanel
        bookTitle={props.bookTitle}
        chapters={props.chapters}
        form={props.form}
        voices={props.voices}
        job={props.job}
        showListen={props.showListen}
        onClose={props.onClose}
        onChange={props.onChange}
        onOpenReadyFiles={() => setReadyOpen(true)}
      />
      <ReadyFilesModal
        open={readyOpen}
        bookId={props.bookId}
        bookTitle={props.bookTitle}
        canListen={props.showListen}
        onClose={() => setReadyOpen(false)}
        onListen={(resumeJob) => {
          setReadyOpen(false)
          props.onResumeListen(resumeJob)
        }}
      />
    </>
  )
}

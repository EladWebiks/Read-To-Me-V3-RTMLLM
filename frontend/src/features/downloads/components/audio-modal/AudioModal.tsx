import { useState } from 'react'
import type { ChapterSummary } from '@/features/library/types'
import { useServerVoices } from '@/features/reader/hooks/useServerVoices'
import { useTtsSettings } from '@/features/reader/hooks/ttsSettingsStore'
import {
  applyAudioFormPatch,
  initialAudioForm,
} from '@/features/downloads/logic/audioFormState'
import { AudioModalBody } from './AudioModalBody'
import type { AudioFormState } from '@/features/downloads/logic/audioModalUtils'
import { useAudioJob } from '@/features/downloads/hooks/useAudioJob'
import type { DownloadJob, DownloadProvider } from '@/features/downloads/types'

type Props = {
  open: boolean
  onClose: () => void
  bookId: string
  bookTitle: string
  chapters: ChapterSummary[]
  currentChapterNumber: number
  onListenStarted?: (job: DownloadJob, form: AudioFormState) => void
}

export function AudioModal(props: Props) {
  if (!props.open) return null
  return <AudioModalOpen key={props.currentChapterNumber} {...props} />
}

function AudioModalOpen(props: Props) {
  const settings = useTtsSettings()
  const [form, setForm] = useState(() =>
    initialAudioForm(
      props.currentChapterNumber,
      settings.provider,
      settings.serverVoice,
      settings.rate,
    ),
  )
  const voices = useServerVoices(form.provider).data ?? []
  const voice =
    form.provider === 'edge' && voices[0] && !voices.some((v) => v.id === form.voice)
      ? voices[0].id
      : form.voice
  const activeForm = voice === form.voice ? form : { ...form, voice }
  const job = useAudioJob({
    bookId: props.bookId,
    form: activeForm,
    onListenStarted: (created) => props.onListenStarted?.(created, activeForm),
  })
  return (
    <AudioModalBody
      bookId={props.bookId}
      bookTitle={props.bookTitle}
      chapters={props.chapters}
      form={activeForm}
      voices={voices}
      job={job}
      showListen={Boolean(props.onListenStarted)}
      onClose={props.onClose}
      onChange={(next) =>
        setForm((prev) => applyAudioFormPatch(prev, next, settings.serverVoice))
      }
      onResumeListen={(resumeJob) => {
        props.onListenStarted?.(resumeJob, formFromJob(resumeJob))
        props.onClose()
      }}
    />
  )
}

function formFromJob(job: DownloadJob): AudioFormState {
  const provider: DownloadProvider = job.provider === 'sapi' ? 'sapi' : 'edge'
  return {
    from: job.chapter_from,
    to: job.chapter_to,
    provider,
    voice: job.voice,
    rate: Number(job.rate) || 1,
  }
}

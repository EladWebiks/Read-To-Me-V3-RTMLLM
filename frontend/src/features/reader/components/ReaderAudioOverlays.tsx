import type { ChapterSummary } from '@/features/library/types'
import {
  AudioModal,
  ListenOfflinePlayer,
  type AudioFormState,
  type DownloadJob,
} from '@/features/downloads'

type ListenState = { job: DownloadJob; form: AudioFormState }

type Props = {
  bookId: string
  bookTitle: string
  chapters: ChapterSummary[]
  chapterNumber: number
  audioOpen: boolean
  setAudioOpen: (open: boolean) => void
  listen: ListenState | null
  setListen: (state: ListenState | null) => void
}

export function ReaderAudioOverlays({
  bookId,
  bookTitle,
  chapters,
  chapterNumber,
  audioOpen,
  setAudioOpen,
  listen,
  setListen,
}: Props) {
  return (
    <>
      <AudioModal
        open={audioOpen}
        onClose={() => setAudioOpen(false)}
        bookId={bookId}
        bookTitle={bookTitle}
        chapters={chapters}
        currentChapterNumber={chapterNumber}
        onListenStarted={(job, form) => {
          setAudioOpen(false)
          setListen({ job, form })
        }}
      />
      <ListenOfflinePlayer
        open={Boolean(listen)}
        config={listen}
        bookTitle={bookTitle}
        chapters={chapters}
        onClose={() => setListen(null)}
      />
    </>
  )
}

export type { ListenState }

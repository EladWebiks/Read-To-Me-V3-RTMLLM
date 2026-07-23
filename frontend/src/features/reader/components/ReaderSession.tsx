import { useState } from 'react'
import { useNavigate } from 'react-router'
import type { ChapterSummary } from '@/features/library/types'
import { ReaderWidthFrame } from './ReaderWidthFrame'
import { ReaderAudioOverlays, type ListenState } from './ReaderAudioOverlays'
import { ReaderBottomBar } from './ReaderBottomBar'
import { ReaderNav } from './ReaderNav'
import { ChapterBody } from './ChapterBody'
import { ReaderPlayer } from '@/features/reader/components/player/ReaderPlayer'
import { useChapterReader } from '@/features/reader/hooks/useChapterReader'
import { useTtsSettings } from '@/features/reader/hooks/ttsSettingsStore'
import { useMediaSession, useWakeLock } from '@/features/reader/hooks/useMediaSession'
import type { ReaderCursor } from '@/features/reader/types'

type Props = {
  bookId: string
  bookTitle: string
  chapterId: string
  chapterTitle: string
  chapterNumber: number
  content: string
  chapters: ChapterSummary[]
  initialCursor: ReaderCursor
  prevChapterId: string | null
  nextChapterId: string | null
  autoPlay: boolean
}

export function ReaderSession(props: Props) {
  const navigate = useNavigate()
  const [audioOpen, setAudioOpen] = useState(false)
  const [listen, setListen] = useState<ListenState | null>(null)
  const go = (chapterId: string, autoPlay = false) => {
    void navigate(`/read/${props.bookId}/${chapterId}`, {
      state: autoPlay ? { autoPlay: true } : undefined,
    })
  }
  const reader = useReader(props, go)
  return (
    <ReaderWidthFrame>
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg bg-card shadow-sm ring-1 ring-border">
        <div className="shrink-0 space-y-3 border-b border-border px-4 pt-3 sm:px-6">
          <ReaderNav
            bookId={props.bookId}
            bookTitle={props.bookTitle}
            chapterTitle={props.chapterTitle}
            chapterNumber={props.chapterNumber}
          />
          <div className="pb-3">
            <ReaderPlayer reader={reader} />
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5">
          <ChapterBody
            paragraphs={reader.paragraphs}
            activeCursor={reader.cursor}
            onWordClick={reader.onWordClick}
          />
        </div>
        <div className="shrink-0 border-t border-border bg-card px-4 py-3 sm:px-6">
          <ReaderBottomBar
            chapters={props.chapters}
            chapterId={props.chapterId}
            prevChapterId={props.prevChapterId}
            nextChapterId={props.nextChapterId}
            onNavigate={go}
            onDownload={() => setAudioOpen(true)}
          />
        </div>
        <ReaderAudioOverlays
          bookId={props.bookId}
          bookTitle={props.bookTitle}
          chapters={props.chapters}
          chapterNumber={props.chapterNumber}
          audioOpen={audioOpen}
          setAudioOpen={setAudioOpen}
          listen={listen}
          setListen={setListen}
        />
      </div>
    </ReaderWidthFrame>
  )
}

function useReader(props: Props, go: (id: string, autoPlay?: boolean) => void) {
  const reader = useChapterReader({
    bookId: props.bookId,
    chapterId: props.chapterId,
    chapterNumber: props.chapterNumber,
    content: props.content,
    initialCursor: props.initialCursor,
    autoPlay: props.autoPlay,
    onChapterEnd: () => {
      if (useTtsSettings.getState().autoNext && props.nextChapterId) {
        go(props.nextChapterId, true)
      }
    },
  })
  useMediaSession({
    title: props.chapterTitle || `Chapter ${props.chapterNumber}`,
    artist: props.bookTitle,
    status: reader.status,
    onPlayPause: reader.playPause,
    onStop: reader.stop,
    onSkipPrev: reader.skipPrev,
    onSkipNext: reader.skipNext,
  })
  useWakeLock(reader.status === 'playing')
  return reader
}

import { useEffect, useMemo, useRef, useState } from 'react'
import { clampCursor, parseParagraphs } from '@/features/reader/logic/parseChapter'
import {
  usePersistProgress,
  usePlayPause,
  useStopPlayback,
  useWordClick,
} from '@/features/reader/logic/readerActions'
import { useSkipParagraph } from '@/features/reader/logic/useSkipParagraph'
import { useSaveProgress } from '@/features/reader/hooks'
import { usePlaybackEngine } from './usePlaybackEngine'
import { useTtsSettings } from './ttsSettingsStore'
import type { ReaderCursor } from '@/features/reader/types'

export type ChapterReaderArgs = {
  bookId: string
  chapterId: string
  chapterNumber: number
  content: string
  initialCursor: ReaderCursor
  autoPlay: boolean
  onChapterEnd: () => void
}

export function useChapterReader(args: ChapterReaderArgs) {
  const paragraphs = useMemo(() => parseParagraphs(args.content), [args.content])
  const start = clampCursor(
    paragraphs,
    args.initialCursor.paragraphIndex,
    args.initialCursor.wordIndex,
  )
  const [cursor, setCursor] = useState(start)
  const saveProgress = useSaveProgress(args.bookId)
  const settings = useTtsSettings()
  const lastSaveRef = useRef(0)
  const endRef = useRef(args.onChapterEnd)

  useEffect(() => {
    endRef.current = args.onChapterEnd
  })

  const persist = usePersistProgress(
    args.chapterId,
    args.chapterNumber,
    saveProgress,
    lastSaveRef,
  )
  const playback = usePlaybackEngine({
    paragraphs,
    settings,
    onCursor: (next) => {
      setCursor(next)
      persist(next)
    },
    onChapterEnd: () => endRef.current(),
  })
  useAutoPlay(args.autoPlay, args.chapterId, paragraphs.length, playback.speech.play)

  return {
    paragraphs,
    cursor,
    onWordClick: useWordClick(setCursor, persist, playback.speech),
    status: playback.speech.status,
    playPause: usePlayPause(cursor, persist, playback.speech),
    stop: useStopPlayback(cursor, setCursor, persist, playback.speech),
    skipPrev: useSkipParagraph(
      -1,
      paragraphs,
      cursor,
      setCursor,
      persist,
      playback.speech,
    ),
    skipNext: useSkipParagraph(
      1,
      paragraphs,
      cursor,
      setCursor,
      persist,
      playback.speech,
    ),
    browserVoices: playback.browserVoices,
    serverVoices: playback.serverVoices,
    error: playback.error,
    settings,
  }
}

function useAutoPlay(
  autoPlay: boolean,
  chapterId: string,
  paragraphCount: number,
  play: (from: ReaderCursor) => void,
) {
  useEffect(() => {
    if (!autoPlay || paragraphCount === 0) {
      return
    }
    play({ paragraphIndex: 0, wordIndex: 0 })
  }, [autoPlay, chapterId, paragraphCount, play])
}

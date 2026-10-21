import { useEffect, useMemo, useRef, useState } from 'react'
import { clampCursor, parseParagraphs } from '@/features/reader/logic/parseChapter'
import { applyRegexCuts } from '@/features/reader/logic/applyRegexCuts'
import {
  usePersistProgress,
  usePlayPause,
  useStopPlayback,
  useWordClick,
  type SpeechApi,
} from '@/features/reader/logic/readerActions'
import { useSkipParagraph } from '@/features/reader/logic/useSkipParagraph'
import { useSaveProgress } from '@/features/reader/hooks'
import { useAppSettings } from '@/features/settings/settingsStore'
import { useAutoPlay } from './useAutoPlay'
import { usePlaybackEngine } from './usePlaybackEngine'
import { useTtsSettings } from './ttsSettingsStore'
import type { ReaderCursor } from '@/features/reader/types'

export type ChapterReaderArgs = {
  bookId: string
  chapterId: string
  chapterNumber: number
  content: string
  initialCursor: ReaderCursor
  autoPlayKey: string | null
  onChapterEnd: () => void
}

function useCleanedChapterContent(content: string): string {
  const regexCutRules = useAppSettings((s) => s.regexCutRules)
  return useMemo(
    () =>
      applyRegexCuts(
        content,
        regexCutRules.filter((r) => r.enabled).map((r) => r.pattern),
      ).cleaned,
    [content, regexCutRules],
  )
}

function useChapterSkips(
  paragraphs: string[][],
  cursor: ReaderCursor,
  setCursor: (next: ReaderCursor) => void,
  persist: (next: ReaderCursor, force?: boolean) => void,
  speech: SpeechApi,
) {
  const skipPrev = useSkipParagraph(-1, paragraphs, cursor, setCursor, persist, speech)
  const skipNext = useSkipParagraph(1, paragraphs, cursor, setCursor, persist, speech)
  return { skipPrev, skipNext }
}

export function useChapterReader(args: ChapterReaderArgs) {
  const cleanedContent = useCleanedChapterContent(args.content)
  const paragraphs = useMemo(() => parseParagraphs(cleanedContent), [cleanedContent])
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
  useAutoPlay(args.autoPlayKey, paragraphs.length, start, playback.speech.play)
  const { skipPrev, skipNext } = useChapterSkips(
    paragraphs,
    cursor,
    setCursor,
    persist,
    playback.speech,
  )

  return {
    paragraphs,
    cursor,
    onWordClick: useWordClick(setCursor, persist, playback.speech),
    status: playback.speech.status,
    playPause: usePlayPause(cursor, persist, playback.speech),
    stop: useStopPlayback(cursor, setCursor, persist, playback.speech),
    skipPrev,
    skipNext,
    browserVoices: playback.browserVoices,
    serverVoices: playback.serverVoices,
    error: playback.error,
    settings,
  }
}

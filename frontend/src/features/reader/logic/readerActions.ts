import { useCallback } from 'react'
import type { ReaderCursor } from '@/features/reader/types'

type SaveMutate = {
  mutate: (input: {
    chapter_id: string
    chapter_number: number
    paragraph_index: number
    word_index: number
  }) => void
}

const SAVE_THROTTLE_MS = 1500

export function usePersistProgress(
  chapterId: string,
  chapterNumber: number,
  saveProgress: SaveMutate,
  lastSaveRef: { current: number },
) {
  return useCallback(
    (next: ReaderCursor, force = false) => {
      const now = Date.now()
      if (!force && now - lastSaveRef.current < SAVE_THROTTLE_MS) {
        return
      }
      lastSaveRef.current = now
      saveProgress.mutate({
        chapter_id: chapterId,
        chapter_number: chapterNumber,
        paragraph_index: next.paragraphIndex,
        word_index: next.wordIndex,
      })
    },
    [chapterId, chapterNumber, lastSaveRef, saveProgress],
  )
}

export type SpeechApi = {
  status: 'idle' | 'playing' | 'paused'
  statusRef: { current: 'idle' | 'playing' | 'paused' }
  play: (from: ReaderCursor) => void
  pause: () => void
  resume: () => void
  /** Stops audio; snaps to start of `at` paragraph (or current). */
  stop: (at?: ReaderCursor) => ReaderCursor
  seek: (from: ReaderCursor) => void
}

export function useWordClick(
  setCursor: (next: ReaderCursor) => void,
  persist: (next: ReaderCursor, force?: boolean) => void,
  speech: SpeechApi,
) {
  return useCallback(
    (next: ReaderCursor) => {
      setCursor(next)
      persist(next, true)
      speech.seek(next)
      if (speech.statusRef.current !== 'idle') {
        speech.play(next)
      }
    },
    [persist, setCursor, speech],
  )
}

export function usePlayPause(
  cursor: ReaderCursor,
  persist: (next: ReaderCursor, force?: boolean) => void,
  speech: SpeechApi,
) {
  return useCallback(() => {
    if (speech.statusRef.current === 'playing') {
      speech.pause()
      persist(cursor, true)
      return
    }
    if (speech.statusRef.current === 'paused') {
      speech.resume()
      return
    }
    speech.play(cursor)
  }, [cursor, persist, speech])
}

export function useStopPlayback(
  cursor: ReaderCursor,
  setCursor: (next: ReaderCursor) => void,
  persist: (next: ReaderCursor, force?: boolean) => void,
  speech: SpeechApi,
) {
  return useCallback(() => {
    const snapped = speech.stop(cursor)
    setCursor(snapped)
    persist(snapped, true)
  }, [cursor, persist, setCursor, speech])
}

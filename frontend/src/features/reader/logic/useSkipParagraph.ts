import { useCallback } from 'react'
import type { ReaderCursor } from '@/features/reader/types'
import type { SpeechApi } from './readerActions'

export function useSkipParagraph(
  direction: -1 | 1,
  paragraphs: string[][],
  cursor: ReaderCursor,
  setCursor: (next: ReaderCursor) => void,
  persist: (next: ReaderCursor, force?: boolean) => void,
  speech: SpeechApi,
) {
  return useCallback(() => {
    const nextIndex = cursor.paragraphIndex + direction
    if (nextIndex < 0 || nextIndex >= paragraphs.length) return
    const next: ReaderCursor = { paragraphIndex: nextIndex, wordIndex: 0 }
    const wasActive = speech.statusRef.current !== 'idle'
    setCursor(next)
    persist(next, true)
    speech.seek(next)
    if (wasActive) {
      // cancel current utterance (via generation bump) then speak the new paragraph
      speech.play(next)
    }
  }, [cursor, direction, paragraphs.length, persist, setCursor, speech])
}

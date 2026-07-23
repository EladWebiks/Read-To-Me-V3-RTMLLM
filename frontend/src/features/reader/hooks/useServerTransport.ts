import { useCallback } from 'react'
import { speakParagraphChunk } from '@/features/reader/logic/serverSpeak'
import { stopAudio } from '@/features/reader/logic/audioDom'
import type { ReaderCursor } from '@/features/reader/types'
import type { SpeechStatus } from './speechStatus'
import type { useServerArgsRef } from './useServerArgsRef'

type AudioRef = React.MutableRefObject<HTMLAudioElement | null>
type UrlRef = React.MutableRefObject<string | null>
type SettleRef = React.MutableRefObject<(() => void) | null>
type CursorRef = React.MutableRefObject<ReaderCursor>
type GenRef = React.MutableRefObject<number>

export function useServerPlay(
  argsRef: ReturnType<typeof useServerArgsRef>,
  audioRef: AudioRef,
  urlRef: UrlRef,
  settleRef: SettleRef,
  cursorRef: CursorRef,
  genRef: GenRef,
  setStatus: (s: SpeechStatus) => void,
  setError: (m: string | null) => void,
) {
  return useCallback(
    (from: ReaderCursor) => {
      const generation = genRef.current + 1
      genRef.current = generation
      stopAudio(audioRef, urlRef, settleRef)
      cursorRef.current = from
      setError(null)
      void speakParagraphChunk(from.paragraphIndex, {
        argsRef,
        audioRef,
        urlRef,
        settleRef,
        setStatus,
        genRef,
        generation,
      })
    },
    [argsRef, audioRef, cursorRef, genRef, setError, setStatus, settleRef, urlRef],
  )
}

export function useServerStop(
  audioRef: AudioRef,
  urlRef: UrlRef,
  settleRef: SettleRef,
  cursorRef: CursorRef,
  genRef: GenRef,
  setStatus: (s: SpeechStatus) => void,
  setError: (m: string | null) => void,
) {
  return useCallback(
    (at?: ReaderCursor) => {
      genRef.current += 1
      stopAudio(audioRef, urlRef, settleRef)
      setError(null)
      const snapped: ReaderCursor = {
        paragraphIndex: (at ?? cursorRef.current).paragraphIndex,
        wordIndex: 0,
      }
      cursorRef.current = snapped
      setStatus('idle')
      return snapped
    },
    [audioRef, cursorRef, genRef, setError, setStatus, settleRef, urlRef],
  )
}

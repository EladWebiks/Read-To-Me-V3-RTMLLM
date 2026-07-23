import { useCallback } from 'react'
import { speakParagraph } from '@/features/reader/logic/speakParagraph'
import type { SpeakArgs } from '@/features/reader/logic/speakParagraph'
import type { ReaderCursor } from '@/features/reader/types'
import type { SpeechStatus } from './speechStatus'

type Refs = {
  argsRef: React.MutableRefObject<SpeakArgs>
  cursorRef: React.MutableRefObject<ReaderCursor>
  genRef: React.MutableRefObject<number>
}

export function useBrowserTransport(
  argsRef: Refs['argsRef'],
  cursorRef: Refs['cursorRef'],
  genRef: Refs['genRef'],
  setStatus: (status: SpeechStatus) => void,
) {
  const play = usePlay(argsRef, cursorRef, genRef, setStatus)
  const pause = useCallback(() => {
    window.speechSynthesis?.pause()
    setStatus('paused')
  }, [setStatus])
  const resume = useCallback(() => {
    const synth = window.speechSynthesis
    if (!synth) return
    if (!synth.speaking && !synth.pending) {
      play(cursorRef.current)
      return
    }
    synth.resume()
    setStatus('playing')
  }, [cursorRef, play, setStatus])
  const stop = useStop(cursorRef, genRef, setStatus)
  const seek = useCallback(
    (from: ReaderCursor) => {
      cursorRef.current = from
    },
    [cursorRef],
  )
  return { play, pause, resume, stop, seek }
}

function usePlay(
  argsRef: Refs['argsRef'],
  cursorRef: Refs['cursorRef'],
  genRef: Refs['genRef'],
  setStatus: (status: SpeechStatus) => void,
) {
  return useCallback(
    (from: ReaderCursor) => {
      const synth = window.speechSynthesis
      if (!synth) return
      const generation = genRef.current + 1
      genRef.current = generation
      synth.cancel()
      cursorRef.current = from
      window.setTimeout(() => {
        if (genRef.current !== generation) return
        speakParagraph(
          from.paragraphIndex,
          from.wordIndex,
          argsRef,
          cursorRef,
          setStatus,
          generation,
          genRef,
        )
      }, 50)
    },
    [argsRef, cursorRef, genRef, setStatus],
  )
}

function useStop(
  cursorRef: Refs['cursorRef'],
  genRef: Refs['genRef'],
  setStatus: (status: SpeechStatus) => void,
) {
  return useCallback(
    (at?: ReaderCursor) => {
      genRef.current += 1
      window.speechSynthesis?.cancel()
      const snapped: ReaderCursor = {
        paragraphIndex: (at ?? cursorRef.current).paragraphIndex,
        wordIndex: 0,
      }
      cursorRef.current = snapped
      setStatus('idle')
      return snapped
    },
    [cursorRef, genRef, setStatus],
  )
}

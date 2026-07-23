import { useCallback, useEffect, useRef, useState } from 'react'
import type { ReaderCursor } from '@/features/reader/types'
import type { SpeechStatus } from './speechStatus'
import type { TtsProviderName } from './ttsSettingsStore'
import { useStatusRef } from './speechRefs'
import { useServerArgsRef } from './useServerArgsRef'
import { useServerPlay, useServerStop } from './useServerTransport'
import { stopAudio } from '@/features/reader/logic/audioDom'

type Args = {
  paragraphs: string[][]
  provider: TtsProviderName
  voice: string | null
  rate: number
  volume: number
  onCursor: (cursor: ReaderCursor) => void
  onChapterEnd: () => void
}

export function useServerSpeech(args: Args) {
  const [status, setStatus] = useState<SpeechStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const statusRef = useStatusRef(status)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const urlRef = useRef<string | null>(null)
  const settleRef = useRef<(() => void) | null>(null)
  const genRef = useRef(0)
  const cursorRef = useRef<ReaderCursor>({ paragraphIndex: 0, wordIndex: 0 })
  const argsRef = useServerArgsRef(args, cursorRef, setError)

  useEffect(() => {
    return () => {
      genRef.current += 1
      stopAudio(audioRef, urlRef, settleRef)
    }
  }, [])

  const play = useServerPlay(
    argsRef,
    audioRef,
    urlRef,
    settleRef,
    cursorRef,
    genRef,
    setStatus,
    setError,
  )
  const pause = useCallback(() => {
    audioRef.current?.pause()
    setStatus('paused')
  }, [])
  const resume = useCallback(() => {
    const audio = audioRef.current
    if (audio && !audio.ended) {
      void audio.play()
      setStatus('playing')
      return
    }
    play(cursorRef.current)
  }, [play])
  const stop = useServerStop(
    audioRef,
    urlRef,
    settleRef,
    cursorRef,
    genRef,
    setStatus,
    setError,
  )
  const seek = useCallback((from: ReaderCursor) => {
    cursorRef.current = from
  }, [])

  return { status, statusRef, error, play, pause, resume, stop, seek }
}

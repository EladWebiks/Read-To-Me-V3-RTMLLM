import { useEffect, useRef } from 'react'

/** v2 parity: start playback when the current chapter becomes ready. */
export function useAutoPlayWhenReady(
  chapterReady: boolean,
  index: number,
  status: 'idle' | 'loading' | 'playing' | 'paused',
  play: () => void,
) {
  const startedFor = useRef<number | null>(null)
  useEffect(() => {
    if (!chapterReady || status !== 'idle') {
      return
    }
    if (startedFor.current === index) {
      return
    }
    startedFor.current = index
    const timer = window.setTimeout(() => {
      play()
    }, 0)
    return () => window.clearTimeout(timer)
  }, [chapterReady, index, status, play])
}

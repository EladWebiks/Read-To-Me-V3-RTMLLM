import { useEffect, useRef } from 'react'
import type { ReaderCursor } from '@/features/reader/types'

/**
 * Starts playback once per autoplay request. `from` and `play` are read through
 * a ref because saved progress rewrites them while audio is running, and a
 * restart there would cut the current utterance short.
 */
export function useAutoPlay(
  autoPlayKey: string | null,
  paragraphCount: number,
  from: ReaderCursor,
  play: (from: ReaderCursor) => void,
) {
  const latest = useRef({ from, play })
  const startedFor = useRef<string | null>(null)

  useEffect(() => {
    latest.current = { from, play }
  })

  useEffect(() => {
    if (!autoPlayKey || paragraphCount === 0) return
    if (startedFor.current === autoPlayKey) return
    startedFor.current = autoPlayKey
    latest.current.play(latest.current.from)
  }, [autoPlayKey, paragraphCount])
}

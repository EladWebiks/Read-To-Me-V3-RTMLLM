import { useEffect, useRef } from 'react'
import type { ReaderCursor } from '@/features/reader/types'
import type { TtsProviderName } from './ttsSettingsStore'

type Args = {
  paragraphs: string[][]
  provider: TtsProviderName
  voice: string | null
  rate: number
  volume: number
  onCursor: (cursor: ReaderCursor) => void
  onChapterEnd: () => void
}

export function useServerArgsRef(
  args: Args,
  cursorRef: { current: ReaderCursor },
  setError: (message: string | null) => void,
) {
  const onCursorRef = useRef(args.onCursor)
  const argsRef = useRef({
    ...args,
    onError: (message: string) => setError(message),
  })

  useEffect(() => {
    onCursorRef.current = args.onCursor
  })

  useEffect(() => {
    argsRef.current = {
      ...args,
      onError: (message: string) => setError(message),
      onCursor: (cursor) => {
        cursorRef.current = cursor
        onCursorRef.current(cursor)
      },
    }
  })

  return argsRef
}

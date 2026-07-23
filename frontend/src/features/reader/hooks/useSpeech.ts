import { useEffect, useRef, useState } from 'react'
import type { SpeakArgs } from '@/features/reader/logic/speakParagraph'
import type { ReaderCursor } from '@/features/reader/types'
import type { SpeechStatus } from './speechStatus'
import { useStatusRef } from './speechRefs'
import { useBrowserTransport } from './useBrowserTransport'

export type { SpeechStatus } from './speechStatus'

export function useSpeech(args: SpeakArgs) {
  const [status, setStatus] = useState<SpeechStatus>('idle')
  const argsRef = useRef(args)
  const cursorRef = useRef<ReaderCursor>({ paragraphIndex: 0, wordIndex: 0 })
  const genRef = useRef(0)
  const statusRef = useStatusRef(status)
  const transport = useBrowserTransport(argsRef, cursorRef, genRef, setStatus)

  useEffect(() => {
    argsRef.current = args
  })

  useEffect(() => {
    return () => {
      genRef.current += 1
      window.speechSynthesis?.cancel()
    }
  }, [])

  return { status, statusRef, ...transport }
}

import { useEffect, useRef } from 'react'
import type { SpeechStatus } from './speechStatus'

export function useStatusRef(status: SpeechStatus) {
  const statusRef = useRef(status)
  useEffect(() => {
    statusRef.current = status
  }, [status])
  return statusRef
}

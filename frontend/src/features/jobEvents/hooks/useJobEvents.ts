import { useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { streamJobEvents } from '../api/streamJobEvents'
import { applyJobEvent } from '../logic/applyJobEvent'
import { useJobEventsStore } from '../jobEventsStore'

const BASE_DELAY_MS = 1000
const MAX_DELAY_MS = 15000

/** Keep a multiplex job-events SSE stream open while the shell is mounted. */
export function useJobEvents() {
  const queryClient = useQueryClient()
  const setConnected = useJobEventsStore((s) => s.setConnected)
  const emit = useJobEventsStore((s) => s.emit)
  const delayRef = useRef(BASE_DELAY_MS)

  useEffect(() => {
    const abort = new AbortController()
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | null = null

    const schedule = () => {
      if (cancelled) return
      const wait = delayRef.current
      delayRef.current = Math.min(MAX_DELAY_MS, wait * 2)
      timer = setTimeout(connect, wait)
    }

    const connect = () => {
      if (cancelled) return
      void streamJobEvents(
        {
          onReady: () => {
            delayRef.current = BASE_DELAY_MS
            setConnected(true)
            void queryClient.invalidateQueries({ queryKey: ['scraping', 'jobs'] })
            void queryClient.invalidateQueries({ queryKey: ['downloads'] })
          },
          onJob: (event) => {
            applyJobEvent(queryClient, event)
            emit(event)
          },
        },
        abort.signal,
      )
        .catch(() => undefined)
        .finally(() => {
          setConnected(false)
          if (!cancelled && !abort.signal.aborted) schedule()
        })
    }

    connect()
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
      abort.abort()
      setConnected(false)
    }
  }, [emit, queryClient, setConnected])
}

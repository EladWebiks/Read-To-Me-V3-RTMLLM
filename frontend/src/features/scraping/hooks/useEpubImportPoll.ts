import { useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useJobEventsStore } from '@/features/jobEvents'
import { getImportJob } from '../api/importApi'
import type { EpubImportResult, ImportJob } from '../types/importTypes'

const POLL_MS = 500

type Setters = {
  setImportJob: (j: ImportJob) => void
  setResult: (r: EpubImportResult | null) => void
  setImportError: (e: string) => void
  onImported: () => void
}

/** Follow EPUB import progress via SSE when connected, else poll. */
export function useEpubImportPoll(importJob: ImportJob | null, setters: Setters) {
  const queryClient = useQueryClient()
  const sseConnected = useJobEventsStore((s) => s.connected)
  const subscribe = useJobEventsStore((s) => s.subscribe)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const { setImportJob, setResult, setImportError, onImported } = setters

  useEffect(() => {
    if (!importJob || importJob.status !== 'running') {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
      return
    }

    const runOnce = () =>
      void pollOnce(importJob, {
        setImportJob,
        setResult,
        setImportError,
        onImported,
        queryClient,
      })

    if (sseConnected) {
      return subscribe((event) => {
        if (event.kind === 'import' && event.job_id === importJob.job_id) runOnce()
      })
    }

    pollRef.current = setInterval(runOnce, POLL_MS)
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
    // Only restart when job identity/status/SSE mode changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [importJob?.job_id, importJob?.status, sseConnected, subscribe])
}

async function pollOnce(
  importJob: ImportJob,
  ctx: Setters & { queryClient: ReturnType<typeof useQueryClient> },
) {
  try {
    const job = await getImportJob(importJob.job_id)
    ctx.setImportJob(job)
    if (job.status === 'completed' && job.result) {
      ctx.setResult(job.result)
      void ctx.queryClient.invalidateQueries({ queryKey: ['library', 'books'] })
      ctx.onImported()
    } else if (job.status === 'failed') {
      ctx.setImportError(job.message || 'Import failed')
    } else if (job.status === 'cancelled') {
      ctx.setImportError(job.message || 'Import cancelled')
    }
  } catch (err) {
    ctx.setImportError(err instanceof Error ? err.message : 'Lost connection')
    ctx.setImportJob({ ...importJob, status: 'failed' })
  }
}

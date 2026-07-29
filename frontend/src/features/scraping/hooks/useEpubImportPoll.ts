import { useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { getImportJob } from '../api/importApi'
import type { EpubImportResult, ImportJob } from '../types/importTypes'

const POLL_MS = 500

type Setters = {
  setImportJob: (j: ImportJob) => void
  setResult: (r: EpubImportResult | null) => void
  setImportError: (e: string) => void
  onImported: () => void
}

/** Poll while an EPUB import job is running. */
export function useEpubImportPoll(importJob: ImportJob | null, setters: Setters) {
  const queryClient = useQueryClient()
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
    pollRef.current = setInterval(() => {
      void pollOnce(importJob, {
        setImportJob,
        setResult,
        setImportError,
        onImported,
        queryClient,
      })
    }, POLL_MS)
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
    // Only restart when job identity/status changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [importJob?.job_id, importJob?.status])
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

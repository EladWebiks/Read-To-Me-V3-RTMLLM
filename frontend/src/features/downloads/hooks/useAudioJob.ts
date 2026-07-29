import { useEffect, useRef, useState } from 'react'
import { getDownloadUrl } from '@/features/downloads/api'
import { downloadFileFromUrl } from '@/features/downloads/logic/downloadFile'
import { useCreateDownload, useDownloadJob } from '@/features/downloads/hooks'
import type { AudioFormState } from '@/features/downloads/logic/audioModalUtils'
import { chapterCount } from '@/features/downloads/logic/audioModalUtils'
import type { DownloadJob } from '@/features/downloads/types'

type Args = {
  bookId: string
  form: AudioFormState
  onListenStarted?: (job: DownloadJob) => void
}

export function useAudioJob({ bookId, form, onListenStarted }: Args) {
  const create = useCreateDownload()
  const [jobId, setJobId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<'download' | 'listen' | null>(null)
  const job = useDownloadJob(jobId).data
  const downloadedRef = useRef<string | null>(null)
  useAutoDownload(mode, jobId, job?.status, setError, downloadedRef)

  const startJob = (nextMode: 'download' | 'listen') => {
    setError(null)
    setMode(nextMode)
    downloadedRef.current = null
    create.mutate(
      {
        book_id: bookId,
        chapter_from: form.from,
        chapter_to: form.to,
        provider: form.provider,
        voice: form.voice,
        rate: form.rate,
      },
      {
        onSuccess: (created) => {
          setJobId(created.id)
          if (nextMode === 'listen') onListenStarted?.(created)
        },
        onError: (err: unknown) => {
          setMode(null)
          setError(err instanceof Error ? err.message : 'Failed to start job')
        },
      },
    )
  }

  return {
    jobId,
    job,
    error,
    mode,
    busy: create.isPending || isDownloading(mode, job?.status),
    creating: create.isPending,
    count: chapterCount(form.from, form.to),
    startDownload: () => startJob('download'),
    startListen: () => startJob('listen'),
  }
}

function isDownloading(mode: string | null, status: string | undefined): boolean {
  return mode === 'download' && status !== 'complete' && status !== 'failed'
}

function useAutoDownload(
  mode: string | null,
  jobId: string | null,
  status: string | undefined,
  setError: (message: string) => void,
  downloadedRef: { current: string | null },
) {
  useEffect(() => {
    if (mode !== 'download' || status !== 'complete' || !jobId) return
    if (downloadedRef.current === jobId) return
    downloadedRef.current = jobId
    void getDownloadUrl(jobId)
      .then((data) => downloadFileFromUrl(data.url, data.filename))
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Download URL failed')
      })
  }, [mode, status, jobId, setError, downloadedRef])
}

import { useCallback, useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { deleteDownload, getDownloadUrl } from '@/features/downloads/api'
import { useDownloadJob } from '@/features/downloads/hooks'
import { downloadFileFromUrl } from '@/features/downloads/logic/downloadFile'

export function useDownloadCardActions(jobId: string) {
  const client = useQueryClient()
  const job = useDownloadJob(jobId).data
  const [error, setError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)
  const [cancelled, setCancelled] = useState(false)
  const autoDownloaded = useRef(false)
  const status = cancelled ? 'cancelled' : job?.status
  const complete = status === 'complete'
  const inFlight = status === 'pending' || status === 'processing' || status === 'running'

  const download = useCallback(async () => {
    setDownloading(true)
    setError(null)
    try {
      const data = await getDownloadUrl(jobId)
      await downloadFileFromUrl(data.url, data.filename)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Download failed')
    } finally {
      setDownloading(false)
    }
  }, [jobId])

  const cancel = useMutation({
    mutationFn: () => deleteDownload(jobId),
    onSuccess: () => {
      setCancelled(true)
      void client.invalidateQueries({ queryKey: ['downloads', jobId] })
      void client.invalidateQueries({ queryKey: ['downloads', 'list'] })
    },
    onError: (reason: unknown) => {
      setError(reason instanceof Error ? reason.message : 'Cancel failed')
    },
  })

  useEffect(() => {
    if (!complete || autoDownloaded.current || cancelled) return
    autoDownloaded.current = true
    void download()
  }, [complete, download, cancelled])

  return {
    job,
    status,
    complete,
    inFlight,
    error,
    downloading,
    cancelling: cancel.isPending,
    download,
    cancelJob: () => void cancel.mutateAsync(),
  }
}

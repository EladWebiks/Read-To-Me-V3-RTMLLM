import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useJobEventsStore } from '@/features/jobEvents'
import {
  cleanDownloads,
  createDownload,
  deleteDownload,
  getDownload,
  getDownloadUrl,
  listDownloads,
} from '@/features/downloads/api'
import type { DownloadCreateInput } from '@/features/downloads/types'

export function useCreateDownload() {
  return useMutation({
    mutationFn: (input: DownloadCreateInput) => createDownload(input),
  })
}

export function useDownloadJobs(bookId: string | null, enabled = true) {
  const sseConnected = useJobEventsStore((s) => s.connected)
  return useQuery({
    queryKey: ['downloads', 'list', bookId],
    queryFn: () => listDownloads(bookId as string),
    enabled: Boolean(bookId) && enabled,
    refetchInterval: (query) => {
      if (sseConnected) return false
      const jobs = query.state.data ?? []
      const busy = jobs.some(
        (j) =>
          j.status === 'pending' || j.status === 'processing' || j.status === 'running',
      )
      return busy ? 4000 : false
    },
  })
}

export function useDeleteDownload(bookId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (jobId: string) => deleteDownload(jobId),
    onSuccess: () =>
      void client.invalidateQueries({ queryKey: ['downloads', 'list', bookId] }),
  })
}

export function useCleanDownloads(bookId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => cleanDownloads(bookId),
    onSuccess: () =>
      void client.invalidateQueries({ queryKey: ['downloads', 'list', bookId] }),
  })
}

export function useDownloadJob(jobId: string | null) {
  const sseConnected = useJobEventsStore((s) => s.connected)
  return useQuery({
    queryKey: ['downloads', jobId],
    queryFn: () => getDownload(jobId as string),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      if (sseConnected) return false
      const status = query.state.data?.status
      return status === 'pending' || status === 'processing' || status === 'running'
        ? 2000
        : false
    },
  })
}

export function useDownloadUrl(jobId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ['downloads', jobId, 'url'],
    queryFn: () => getDownloadUrl(jobId as string),
    enabled: Boolean(jobId) && enabled,
  })
}

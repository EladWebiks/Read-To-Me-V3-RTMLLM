import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
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
  return useQuery({
    queryKey: ['downloads', 'list', bookId],
    queryFn: () => listDownloads(bookId as string),
    enabled: Boolean(bookId) && enabled,
    refetchInterval: 4000,
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
  return useQuery({
    queryKey: ['downloads', jobId],
    queryFn: () => getDownload(jobId as string),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
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

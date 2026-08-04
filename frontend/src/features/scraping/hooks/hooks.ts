import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useJobEventsStore } from '@/features/jobEvents'
import {
  cancelScrapeJob,
  createScrapeJob,
  deleteScrapeJob,
  listScrapeJobs,
  previewScrape,
} from '../api'
import type { ScrapeJobCreateInput } from '../types'

export function useScrapePreview() {
  return useMutation({ mutationFn: (url: string) => previewScrape(url) })
}

export function useCreateScrapeJob() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: ScrapeJobCreateInput) => createScrapeJob(input),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['scraping', 'jobs'] }),
  })
}

export function useScrapeJobs() {
  const sseConnected = useJobEventsStore((s) => s.connected)
  return useQuery({
    queryKey: ['scraping', 'jobs'],
    queryFn: listScrapeJobs,
    refetchOnMount: 'always',
    refetchInterval: (query) => {
      if (sseConnected) return false
      const jobs = query.state.data ?? []
      const busy = jobs.some((j) => j.status === 'pending' || j.status === 'running')
      return busy ? 2000 : false
    },
  })
}

export function useCancelScrapeJob() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (jobId: string) => cancelScrapeJob(jobId),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['scraping', 'jobs'] }),
  })
}

export function useDeleteScrapeJob() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (jobId: string) => deleteScrapeJob(jobId),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['scraping', 'jobs'] }),
  })
}

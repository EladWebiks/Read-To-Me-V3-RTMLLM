import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { cancelScrapeJob, createScrapeJob, listScrapeJobs, previewScrape } from '../api'
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
  return useQuery({
    queryKey: ['scraping', 'jobs'],
    queryFn: listScrapeJobs,
    refetchInterval: (query) => {
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

import { useQuery } from '@tanstack/react-query'
import { useJobEventsStore } from '@/features/jobEvents'
import { getScrapeJob } from '../api'

/** Live scrape job — SSE when connected, poll fallback while pending/running. */
export function useScrapeJob(jobId: string | null) {
  const sseConnected = useJobEventsStore((s) => s.connected)
  return useQuery({
    queryKey: ['scraping', 'jobs', jobId],
    queryFn: () => getScrapeJob(jobId as string),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      if (sseConnected) return false
      const status = query.state.data?.status
      return status === 'pending' || status === 'running' ? 2000 : false
    },
  })
}

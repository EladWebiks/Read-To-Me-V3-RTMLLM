import { useQuery } from '@tanstack/react-query'
import { getScrapeJob } from '../api'

/** Poll one scrape job while pending/running (chat progress card). */
export function useScrapeJob(jobId: string | null) {
  return useQuery({
    queryKey: ['scraping', 'jobs', jobId],
    queryFn: () => getScrapeJob(jobId as string),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'pending' || status === 'running' ? 2000 : false
    },
  })
}

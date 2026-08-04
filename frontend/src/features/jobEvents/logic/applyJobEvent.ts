import type { QueryClient } from '@tanstack/react-query'
import { booksQueryKey } from '@/features/library/hooks/bookHooks'
import type { JobEvent } from '../api/streamJobEvents'

/** Map a job SSE event onto react-query invalidations. */
export function applyJobEvent(queryClient: QueryClient, event: JobEvent): void {
  if (event.kind === 'scrape') {
    void queryClient.invalidateQueries({ queryKey: ['scraping', 'jobs'] })
    void queryClient.invalidateQueries({ queryKey: ['scraping', 'jobs', event.job_id] })
    void queryClient.invalidateQueries({ queryKey: booksQueryKey })
    return
  }
  if (event.kind === 'download') {
    void queryClient.invalidateQueries({ queryKey: ['downloads', event.job_id] })
    if (event.book_id) {
      void queryClient.invalidateQueries({
        queryKey: ['downloads', 'list', event.book_id],
      })
    }
    return
  }
  void queryClient.invalidateQueries({ queryKey: ['imports', 'jobs', event.job_id] })
  if (event.status === 'completed') {
    void queryClient.invalidateQueries({ queryKey: booksQueryKey })
  }
}

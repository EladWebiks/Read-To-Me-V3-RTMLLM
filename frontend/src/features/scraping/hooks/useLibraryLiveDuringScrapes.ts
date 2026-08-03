import { useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { booksQueryKey } from '@/features/library/hooks/bookHooks'
import { useScrapeJobs } from './hooks'
import { scrapeProgressKey } from '../logic/scrapeProgressKey'

/**
 * Keep library chapter counts in sync while scrapes run.
 * Polls scrape jobs app-wide (react-query dedupes with the Scraper page).
 */
export function useLibraryLiveDuringScrapes() {
  const queryClient = useQueryClient()
  const jobs = useScrapeJobs()
  const key = scrapeProgressKey(jobs.data ?? [])
  const prevKey = useRef<string | null>(null)

  useEffect(() => {
    if (prevKey.current === null) {
      prevKey.current = key
      return
    }
    if (key === prevKey.current) return
    prevKey.current = key
    void queryClient.invalidateQueries({ queryKey: booksQueryKey })
  }, [key, queryClient])
}

import { useMemo, useState, type RefObject } from 'react'
import { useFitRowPageSize } from '@/shared/hooks/useFitRowPageSize'
import { useCancelScrapeJob, useDeleteScrapeJob, useScrapeJobs } from '../hooks'
import { MOCK_SCRAPE_JOBS, SCRAPER_APPEND_MOCKS } from '../mocks/mockScrapeJobs'
import type { ScrapeJob } from '../types'

/** Matches JobRow: h-[3.75rem]; list uses space-y-2. */
export const JOB_ROW_REM = 3.75
export const JOB_GAP_REM = 0.5

export function useScrapeJobListState(listSlotRef: RefObject<HTMLElement | null>) {
  const jobs = useScrapeJobs()
  const cancel = useCancelScrapeJob()
  const remove = useDeleteScrapeJob()
  const pageSize = useFitRowPageSize(listSlotRef, {
    rowRem: JOB_ROW_REM,
    gapRem: JOB_GAP_REM,
    fallback: 8,
  })
  const [page, setPage] = useState(1)

  const items = useMemo(() => {
    const real = jobs.data ?? []
    if (!SCRAPER_APPEND_MOCKS) return real
    return [...real, ...MOCK_SCRAPE_JOBS]
  }, [jobs.data])

  const size = Math.max(1, pageSize)
  const pageCount = Math.max(1, Math.ceil(items.length / size))
  const safePage = Math.min(page, pageCount)
  const pageItems = useMemo(
    () => items.slice((safePage - 1) * size, safePage * size),
    [items, safePage, size],
  )

  function onCancel(job: ScrapeJob) {
    if (job.id.startsWith('mock-')) return
    void cancel.mutateAsync(job.id)
  }

  function onRemove(job: ScrapeJob) {
    if (job.id.startsWith('mock-')) return
    void remove.mutateAsync(job.id)
  }

  return {
    isLoading: jobs.isLoading && !SCRAPER_APPEND_MOCKS,
    items,
    pageItems,
    page: safePage,
    pageCount,
    pageSize: size,
    setPage,
    onCancel,
    onRemove,
    showMocksHint: SCRAPER_APPEND_MOCKS,
  }
}

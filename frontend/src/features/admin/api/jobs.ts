import type { Page } from '@/features/admin/types'
import { apiGet } from '@/shared/lib/api'

/** Mirrors ScrapeJobAdminRead (scraping/schemas.py) exactly. */
export type ScrapeJob = {
  id: string
  user_id: string
  book_id: string | null
  book_title: string | null
  start_url: string
  mode: string
  status: string
  chapters_done: number
  chapter_from: number | null
  chapter_to: number | null
  message: string | null
  error: string | null
  created_at: string
  updated_at: string
}

/** Mirrors DownloadJobAdminRead (downloads/schemas.py) exactly. */
export type DownloadJob = {
  id: string
  user_id: string
  book_id: string
  chapter_from: number
  chapter_to: number
  provider: string
  voice: string
  status: string
  ready_count: number
  total_count: number
  error: string | null
  expires_at: string | null
  created_at: string
  updated_at: string
}

function jobsQuery(status: string, limit: number, offset: number): string {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (status) {
    params.set('status', status)
  }
  return params.toString()
}

export function fetchScrapingJobs(
  status: string,
  limit: number,
  offset: number,
): Promise<Page<ScrapeJob>> {
  return apiGet(`/api/admin/jobs/scraping?${jobsQuery(status, limit, offset)}`)
}

export function fetchDownloadJobs(
  status: string,
  limit: number,
  offset: number,
): Promise<Page<DownloadJob>> {
  return apiGet(`/api/admin/jobs/downloads?${jobsQuery(status, limit, offset)}`)
}

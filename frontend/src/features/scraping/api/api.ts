import { apiDelete, apiGet, apiPost } from '@/shared/lib/api'
import type { ScrapeJob, ScrapeJobCreateInput, ScrapePreview } from '../types'

export function previewScrape(url: string): Promise<ScrapePreview> {
  return apiPost<ScrapePreview>('/api/scraping/preview', { url })
}

export function createScrapeJob(input: ScrapeJobCreateInput): Promise<ScrapeJob> {
  return apiPost<ScrapeJob>('/api/scraping/jobs', input)
}

export function listScrapeJobs(): Promise<ScrapeJob[]> {
  return apiGet<ScrapeJob[]>('/api/scraping/jobs')
}

export function getScrapeJob(jobId: string): Promise<ScrapeJob> {
  return apiGet<ScrapeJob>(`/api/scraping/jobs/${jobId}`)
}

export function cancelScrapeJob(jobId: string): Promise<ScrapeJob> {
  return apiPost<ScrapeJob>(`/api/scraping/jobs/${jobId}/cancel`)
}

export function deleteScrapeJob(jobId: string): Promise<void> {
  return apiDelete(`/api/scraping/jobs/${jobId}`)
}

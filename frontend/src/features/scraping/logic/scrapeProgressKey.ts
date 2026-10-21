import type { ScrapeJob } from '../types'

/** Stable progress fingerprint — changes when status or chapters_done move. */
export function scrapeProgressKey(jobs: ScrapeJob[]): string {
  return jobs.map((job) => `${job.id}:${job.status}:${job.chapters_done}`).join('|')
}

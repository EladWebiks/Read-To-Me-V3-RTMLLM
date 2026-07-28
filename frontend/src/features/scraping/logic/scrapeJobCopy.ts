/** Short subtitle for a scrape job row (never dump stack traces). */
export function scrapeJobSubtitle(job: {
  error: string | null
  message: string
  start_url: string
  status: string
}): string {
  if (job.error || job.status === 'failed') return 'An error occurred'
  if (job.message) return job.message
  return job.start_url
}

export function scrapeJobIsBusy(status: string): boolean {
  return status === 'pending' || status === 'running'
}

export function scrapeJobIsTerminal(status: string): boolean {
  return status === 'complete' || status === 'failed' || status === 'cancelled'
}

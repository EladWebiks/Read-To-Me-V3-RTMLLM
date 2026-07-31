import { useQuery } from '@tanstack/react-query'
import { fetchDownloadJobs, fetchScrapingJobs } from '@/features/admin/api/jobs'

export function useScrapingJobs(status: string, limit: number, offset: number) {
  return useQuery({
    queryKey: ['admin', 'jobs', 'scraping', status, limit, offset],
    queryFn: () => fetchScrapingJobs(status, limit, offset),
  })
}

export function useDownloadJobs(status: string, limit: number, offset: number) {
  return useQuery({
    queryKey: ['admin', 'jobs', 'downloads', status, limit, offset],
    queryFn: () => fetchDownloadJobs(status, limit, offset),
  })
}

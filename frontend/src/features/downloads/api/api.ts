import { apiDelete, apiGet, apiPost } from '@/shared/lib/api'
import type {
  DownloadCleanResult,
  DownloadCreateInput,
  DownloadJob,
  DownloadUrl,
} from '@/features/downloads/types'

export function createDownload(input: DownloadCreateInput): Promise<DownloadJob> {
  return apiPost<DownloadJob>('/api/downloads', input)
}

export function listDownloads(bookId?: string): Promise<DownloadJob[]> {
  const query = bookId ? `?book_id=${encodeURIComponent(bookId)}` : ''
  return apiGet<DownloadJob[]>(`/api/downloads${query}`)
}

export function getDownload(jobId: string): Promise<DownloadJob> {
  return apiGet<DownloadJob>(`/api/downloads/${jobId}`)
}

export function deleteDownload(jobId: string): Promise<void> {
  return apiDelete(`/api/downloads/${jobId}`)
}

export function cleanDownloads(bookId: string): Promise<DownloadCleanResult> {
  return apiDelete<DownloadCleanResult>(
    `/api/downloads?book_id=${encodeURIComponent(bookId)}`,
  )
}

export function getDownloadUrl(jobId: string): Promise<DownloadUrl> {
  return apiGet<DownloadUrl>(`/api/downloads/${jobId}/url`)
}

export function getChapterDownloadUrl(
  jobId: string,
  chapterNumber: number,
): Promise<DownloadUrl> {
  return apiGet<DownloadUrl>(`/api/downloads/${jobId}/chapters/${chapterNumber}/url`)
}

import { ApiError, apiGet, apiPut } from '@/shared/lib/api'
import type { ProgressUpsertInput, ReadingProgress } from '@/features/reader/types'

export async function getProgress(bookId: string): Promise<ReadingProgress | null> {
  try {
    return await apiGet<ReadingProgress>(`/api/library/books/${bookId}/progress`)
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null
    }
    throw error
  }
}

export function getContinueReading(): Promise<ReadingProgress | null> {
  return apiGet<ReadingProgress | null>('/api/library/reading/continue')
}

export function saveProgress(
  bookId: string,
  input: ProgressUpsertInput,
): Promise<ReadingProgress> {
  return apiPut<ReadingProgress>(`/api/library/books/${bookId}/progress`, input)
}

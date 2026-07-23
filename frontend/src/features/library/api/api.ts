import { apiDelete, apiGet, apiPost, apiPostForm, apiPut } from '@/shared/lib/api'
import type {
  Book,
  BookCreateInput,
  Chapter,
  ChapterCreateInput,
  ChapterSummary,
} from '@/features/library/types'

export function listBooks(): Promise<Book[]> {
  return apiGet<Book[]>('/api/library/books')
}

export function getBook(bookId: string): Promise<Book> {
  return apiGet<Book>(`/api/library/books/${bookId}`)
}

export function createBook(input: BookCreateInput): Promise<Book> {
  return apiPost<Book>('/api/library/books', input)
}

export function deleteBook(bookId: string): Promise<void> {
  return apiDelete(`/api/library/books/${bookId}`)
}

export function listChapters(bookId: string): Promise<ChapterSummary[]> {
  return apiGet<ChapterSummary[]>(`/api/library/books/${bookId}/chapters`)
}

export function createChapter(
  bookId: string,
  input: ChapterCreateInput,
): Promise<Chapter> {
  return apiPost<Chapter>(`/api/library/books/${bookId}/chapters`, input)
}

export function getChapter(chapterId: string): Promise<Chapter> {
  return apiGet<Chapter>(`/api/chapters/${chapterId}`)
}

export function updateChapter(
  chapterId: string,
  input: Partial<ChapterCreateInput>,
): Promise<Chapter> {
  return apiPut<Chapter>(`/api/chapters/${chapterId}`, input)
}

export function deleteChapter(chapterId: string): Promise<void> {
  return apiDelete(`/api/chapters/${chapterId}`)
}

export function uploadCover(bookId: string, file: File): Promise<Book> {
  const form = new FormData()
  form.append('file', file)
  return apiPostForm<Book>(`/api/library/books/${bookId}/cover`, form)
}

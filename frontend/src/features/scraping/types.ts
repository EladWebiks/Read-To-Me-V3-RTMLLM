export type ScrapePreview = {
  source: string
  book_url: string | null
  title: string
  author: string
  cover_url: string
  first_chapter_url: string
}

export type ScrapeJob = {
  id: string
  book_id: string | null
  start_url: string
  mode: string
  chapter_from: number | null
  chapter_to: number | null
  max_chapters: number | null
  status: string
  chapters_done: number
  message: string
  error: string | null
  created_at: string
  updated_at: string
}

export type ScrapeJobCreateInput = {
  url: string
  book_url?: string | null
  mode?: 'full' | 'range'
  chapter_from?: number | null
  chapter_to?: number | null
  max_chapters?: number | null
  starting_chapter?: number | null
}

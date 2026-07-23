export type Book = {
  id: string
  title: string
  author: string
  description: string
  language: string
  cover_object_key: string | null
  cover_url?: string | null
  starting_chapter_number: number
  status: string
  created_at: string
  updated_at: string
  chapter_count: number
  last_read_chapter_number?: number | null
  last_read_at?: string | null
}

export type BookCreateInput = {
  title: string
  author?: string
  description?: string
  language?: string
  starting_chapter_number?: number
}

export type ChapterSummary = {
  id: string
  book_id: string
  chapter_number: number
  title: string
  word_count: number
  created_at: string
  updated_at: string
}

export type Chapter = ChapterSummary & {
  content: string
}

export type ChapterCreateInput = {
  title?: string
  content: string
  chapter_number?: number
}

export type LibrarySort = 'read' | 'added' | 'name' | 'chapters'

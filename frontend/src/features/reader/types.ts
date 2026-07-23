export type ReadingProgress = {
  book_id: string
  chapter_id: string
  chapter_number: number
  paragraph_index: number
  word_index: number
  updated_at: string
}

export type ProgressUpsertInput = {
  chapter_id: string
  chapter_number: number
  paragraph_index: number
  word_index: number
}

export type ReaderCursor = {
  paragraphIndex: number
  wordIndex: number
}

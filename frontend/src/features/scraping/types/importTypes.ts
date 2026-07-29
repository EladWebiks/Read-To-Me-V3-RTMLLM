export type EpubImportFileSummary = {
  name: string
  chapters: number
}

export type EpubImportResult = {
  book_id: string
  book_title: string
  author: string
  chapters_imported: number
  files: EpubImportFileSummary[]
  starting_chapter: number
}

export type ImportJob = {
  job_id: string
  status: 'running' | 'completed' | 'failed' | 'cancelled'
  chapters_imported: number
  total_chapters: number | null
  files_total: number
  files_parsed: number
  current_file: string
  book_title: string
  message: string
  result: EpubImportResult | null
}

export type EpubImportOptions = {
  title?: string
  author?: string
  startingChapter?: number
}

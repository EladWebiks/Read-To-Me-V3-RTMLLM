export type DownloadProvider = 'edge' | 'sapi'

export type DownloadJob = {
  id: string
  book_id: string
  chapter_from: number
  chapter_to: number
  provider: string
  voice: string
  rate: string
  status: string
  ready_count: number
  total_count: number
  object_key: string | null
  error: string | null
  expires_at: string | null
  created_at: string
  updated_at: string
}

export type DownloadCreateInput = {
  book_id: string
  chapter_from: number
  chapter_to: number
  provider: DownloadProvider
  voice?: string | null
  rate?: number
}

export type DownloadUrl = {
  url: string
  filename: string
  expires_at: string
}

export type DownloadCleanResult = {
  deleted: number
}

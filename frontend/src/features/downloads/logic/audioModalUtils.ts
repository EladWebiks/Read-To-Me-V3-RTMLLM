import type { ChapterSummary } from '@/features/library/types'
import type { DownloadProvider } from '@/features/downloads/types'

export type AudioFormState = {
  from: number
  to: number
  provider: DownloadProvider
  voice: string
  rate: number
}

export function sortedChapters(chapters: ChapterSummary[]): ChapterSummary[] {
  return [...chapters].sort((a, b) => a.chapter_number - b.chapter_number)
}

export function defaultVoice(
  provider: DownloadProvider,
  serverVoice: string | null,
): string {
  if (provider === 'sapi') {
    return 'Microsoft Zira Desktop'
  }
  return serverVoice ?? 'en-US-JennyNeural'
}

export function chapterCount(from: number, to: number): number {
  return Math.max(0, to - from + 1)
}

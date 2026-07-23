import type { ChapterSummary } from '@/features/library/types'

export type ListenControlsProps = {
  jobId: string
  jobStatus: string | undefined
  readyCount: number
  totalCount: number
  current: ChapterSummary | undefined
  chapterReady: boolean
  status: 'idle' | 'loading' | 'playing' | 'paused'
  error: string | null
  canPrev: boolean
  canNext: boolean
  currentTime: number
  duration: number
  onClose: () => void
  onPrev: () => void
  onNext: () => void
  onPause: () => void
  onResume: () => void
  onSeekBack: () => void
  onSeekForward: () => void
  onSeekTo: (seconds: number) => void
}

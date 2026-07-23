import type { ChapterSummary } from '@/features/library/types'

type PlayStatus = 'idle' | 'loading' | 'playing' | 'paused'

export type AudioTimeHandlers = {
  onTime: (current: number, duration: number) => void
}

export async function playChapterAudio(
  jobId: string,
  chapterNumber: number,
  audioRef: { current: HTMLAudioElement | null },
  setStatus: (status: PlayStatus) => void,
  setError: (message: string | null) => void,
  onEnded: () => void,
  fetchUrl: (jobId: string, chapterNumber: number) => Promise<{ url: string }>,
  time?: AudioTimeHandlers,
) {
  setStatus('loading')
  setError(null)
  try {
    const data = await fetchUrl(jobId, chapterNumber)
    audioRef.current?.pause()
    const audio = new Audio(data.url)
    audioRef.current = audio
    audio.ontimeupdate = () => {
      time?.onTime(
        audio.currentTime,
        Number.isFinite(audio.duration) ? audio.duration : 0,
      )
    }
    audio.onloadedmetadata = () => {
      time?.onTime(
        audio.currentTime,
        Number.isFinite(audio.duration) ? audio.duration : 0,
      )
    }
    audio.onended = onEnded
    audio.onerror = () => setError('audio playback failed')
    await audio.play()
    setStatus('playing')
  } catch (err: unknown) {
    setError(err instanceof Error ? err.message : 'Failed to load chapter audio')
    setStatus('idle')
  }
}

export function resumeOrPlay(args: {
  status: PlayStatus
  jobId: string | null
  current: ChapterSummary | undefined
  readyCount: number
  index: number
  rangeLength: number
  audioRef: { current: HTMLAudioElement | null }
  setStatus: (status: PlayStatus) => void
  setError: (message: string | null) => void
  setIndex: (updater: (prev: number) => number) => void
  fetchUrl: (jobId: string, chapterNumber: number) => Promise<{ url: string }>
  time?: AudioTimeHandlers
}) {
  if (args.status === 'paused' && args.audioRef.current) {
    void args.audioRef.current.play().then(() => args.setStatus('playing'))
    return
  }
  if (!args.jobId || !args.current || args.index >= args.readyCount) return
  void playChapterAudio(
    args.jobId,
    args.current.chapter_number,
    args.audioRef,
    args.setStatus,
    args.setError,
    () => {
      args.setStatus('idle')
      args.setIndex((prev) => (prev + 1 < args.rangeLength ? prev + 1 : prev))
    },
    args.fetchUrl,
    args.time,
  )
}

export function seekAudio(
  audioRef: { current: HTMLAudioElement | null },
  deltaSec: number,
): void {
  const audio = audioRef.current
  if (!audio) return
  const max = Number.isFinite(audio.duration)
    ? audio.duration
    : audio.currentTime + deltaSec
  audio.currentTime = Math.max(0, Math.min(max, audio.currentTime + deltaSec))
}

export function seekAudioTo(
  audioRef: { current: HTMLAudioElement | null },
  seconds: number,
): void {
  const audio = audioRef.current
  if (!audio) return
  const max = Number.isFinite(audio.duration) ? audio.duration : seconds
  audio.currentTime = Math.max(0, Math.min(max, seconds))
}

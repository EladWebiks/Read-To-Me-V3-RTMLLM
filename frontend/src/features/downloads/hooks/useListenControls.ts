import { useCallback } from 'react'
import type { ChapterSummary } from '@/features/library/types'
import { getChapterDownloadUrl } from '@/features/downloads/api'
import {
  resumeOrPlay,
  seekAudio,
  seekAudioTo,
} from '@/features/downloads/logic/listenPlayback'

const SEEK_STEP = 20
type PlayStatus = 'idle' | 'loading' | 'playing' | 'paused'
type AudioRef = { current: HTMLAudioElement | null }

type PlaybackState = {
  index: number
  status: PlayStatus
  setStatus: (status: PlayStatus) => void
  setError: (message: string | null) => void
  setIndex: (updater: (prev: number) => number) => void
  onTime: (time: number, total: number) => void
  resetChapter: () => void
}

export function useSeekControls(audioRef: AudioRef) {
  return {
    seekBack: useCallback(() => seekAudio(audioRef, -SEEK_STEP), [audioRef]),
    seekForward: useCallback(() => seekAudio(audioRef, SEEK_STEP), [audioRef]),
    seekTo: useCallback((seconds: number) => seekAudioTo(audioRef, seconds), [audioRef]),
  }
}

export function usePlayControls(
  audioRef: AudioRef,
  state: PlaybackState,
  jobId: string | null,
  current: ChapterSummary | undefined,
  readyCount: number,
  rangeLength: number,
) {
  const pause = useCallback(() => {
    audioRef.current?.pause()
    state.setStatus('paused')
  }, [audioRef, state])

  const resume = useCallback(() => {
    resumeOrPlay({
      status: state.status,
      jobId,
      current,
      readyCount,
      index: state.index,
      rangeLength,
      audioRef,
      setStatus: state.setStatus,
      setError: state.setError,
      setIndex: state.setIndex,
      fetchUrl: getChapterDownloadUrl,
      time: { onTime: state.onTime },
    })
  }, [audioRef, state, jobId, current, readyCount, rangeLength])

  const prev = useCallback(() => {
    audioRef.current?.pause()
    state.resetChapter()
    state.setIndex((i) => Math.max(0, i - 1))
  }, [audioRef, state])

  const next = useCallback(() => {
    audioRef.current?.pause()
    state.resetChapter()
    state.setIndex((i) => Math.min(rangeLength - 1, i + 1))
  }, [audioRef, state, rangeLength])

  return { pause, resume, prev, next }
}

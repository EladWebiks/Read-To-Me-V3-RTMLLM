import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ChapterSummary } from '@/features/library/types'
import { sortedChapters } from '@/features/downloads/logic/audioModalUtils'
import { stopListenAudio } from '@/features/downloads/logic/listenAudioUtils'
import { useDownloadJob } from '@/features/downloads/hooks'
import { usePlayControls, useSeekControls } from './useListenControls'
import type { DownloadJob } from '@/features/downloads/types'

export type ListenConfig = {
  job: DownloadJob
  chapterFrom: number
  chapterTo: number
}

type PlayStatus = 'idle' | 'loading' | 'playing' | 'paused'

export function useListenOffline(
  open: boolean,
  config: ListenConfig | null,
  chapters: ChapterSummary[],
) {
  const jobId = open && config ? config.job.id : null
  const job = useDownloadJob(jobId).data ?? config?.job
  const range = useMemo(() => filterRange(chapters, config), [chapters, config])
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const state = useChapterPlayback()
  const current = range[state.index]
  const readyCount = job?.ready_count ?? 0
  const seek = useSeekControls(audioRef)
  const play = usePlayControls(audioRef, state, jobId, current, readyCount, range.length)
  const { setStatus } = state
  const stop = useCallback(() => {
    stopListenAudio(audioRef)
    setStatus('idle')
  }, [setStatus])
  useEffect(() => () => stopListenAudio(audioRef), [])
  return {
    job,
    range,
    current,
    readyCount,
    chapterReady: Boolean(current && state.index < readyCount),
    index: state.index,
    status: state.status,
    error: state.error,
    currentTime: state.currentTime,
    duration: state.duration,
    stop,
    ...seek,
    ...play,
  }
}

function useChapterPlayback() {
  const [index, setIndex] = useState(0)
  const [status, setStatus] = useState<PlayStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const onTime = useCallback((time: number, total: number) => {
    setCurrentTime(time)
    setDuration(total)
  }, [])
  const resetChapter = useCallback(() => {
    setStatus('idle')
    setCurrentTime(0)
    setDuration(0)
  }, [])
  return {
    index,
    setIndex,
    status,
    setStatus,
    error,
    setError,
    currentTime,
    duration,
    onTime,
    resetChapter,
  }
}

function filterRange(chapters: ChapterSummary[], config: ListenConfig | null) {
  if (!config) return [] as ChapterSummary[]
  return sortedChapters(chapters).filter(
    (ch) =>
      ch.chapter_number >= config.chapterFrom && ch.chapter_number <= config.chapterTo,
  )
}

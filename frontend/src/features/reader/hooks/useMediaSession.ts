import { useEffect } from 'react'
import type { SpeechStatus } from './useSpeech'

type MediaSessionArgs = {
  title: string
  artist: string
  status: SpeechStatus
  onPlayPause: () => void
  onStop: () => void
  onSkipPrev: () => void
  onSkipNext: () => void
}

export function useMediaSession(args: MediaSessionArgs) {
  const { title, artist, status, onPlayPause, onStop, onSkipPrev, onSkipNext } = args
  useEffect(() => {
    if (!('mediaSession' in navigator)) return
    navigator.mediaSession.metadata = new MediaMetadata({ title, artist })
    navigator.mediaSession.setActionHandler('play', () => onPlayPause())
    navigator.mediaSession.setActionHandler('pause', () => onPlayPause())
    navigator.mediaSession.setActionHandler('stop', () => onStop())
    navigator.mediaSession.setActionHandler('previoustrack', () => onSkipPrev())
    navigator.mediaSession.setActionHandler('nexttrack', () => onSkipNext())
  }, [title, artist, onPlayPause, onStop, onSkipPrev, onSkipNext])

  useEffect(() => {
    if (!('mediaSession' in navigator)) return
    navigator.mediaSession.playbackState =
      status === 'playing' ? 'playing' : status === 'paused' ? 'paused' : 'none'
  }, [status])
}

export function useWakeLock(active: boolean) {
  useEffect(() => {
    if (!active || !('wakeLock' in navigator)) return
    let lock: WakeLockSentinel | null = null
    void navigator.wakeLock.request('screen').then((sentinel) => {
      lock = sentinel
    })
    return () => {
      void lock?.release()
    }
  }, [active])
}
